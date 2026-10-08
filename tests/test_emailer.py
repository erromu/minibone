"""Tests for minibone.emailer.Emailer.

Uses a fake SMTP class patched over smtplib.SMTP and smtplib.SMTP_SSL so
no network is involved. Follows the style of tests/test_daemon.py.

Notable behaviors covered:
- successful send, credentials, bcc handled at the envelope level
- chunking and single-connection reuse per on_process call
- transient (4xx) vs permanent (5xx) failure classification
- bounded retries then discard
- connection-level failures requeue untouched (retry_count not bumped)
- mid-batch disconnect requeues the rest untouched
- queue capacity and address validation
- graceful drain on stop() with a deadline
"""

from __future__ import annotations

import logging
import smtplib
import time
import unittest
from unittest.mock import patch

from minibone.emailer import Emailer


# Quiet the emailer logs during tests.
logging.disable(logging.CRITICAL)


class FakeSMTP:
    """Minimal SMTP stand-in.

    Class-level knobs (reset in setUp):
    - init_exception:        raised from __init__, simulating connect failure
    - always_raise_on_send:  raised on every send_message call
    - send_plan:             per-call plan; consumed left to right. A None
                             entry means "succeed", an exception instance
                             means "raise that". Once exhausted, falls back
                             to always_raise_on_send / success.

    Per-instance:
    - sent:         list of (msg, from_addr, to_addrs) tuples
    - login_args:   the (user, password) passed to login(), or None
    - quit_called:  bool
    - close_called: bool
    """

    instances: list[FakeSMTP] = []
    init_exception: Exception | None = None
    always_raise_on_send: Exception | None = None
    send_plan: list[Exception | None] = []

    def __init__(self, host=None, port=None, timeout=None):
        if FakeSMTP.init_exception is not None:
            raise FakeSMTP.init_exception
        self.host = host
        self.port = port
        self.timeout = timeout
        self.sent: list[tuple] = []
        self.login_args: tuple | None = None
        self.quit_called = False
        self.close_called = False
        FakeSMTP.instances.append(self)

    def login(self, user=None, password=None):
        self.login_args = (user, password)

    def send_message(self, msg, from_addr=None, to_addrs=None):
        if FakeSMTP.send_plan:
            action = FakeSMTP.send_plan.pop(0)
            if action is not None:
                raise action
        elif FakeSMTP.always_raise_on_send is not None:
            raise FakeSMTP.always_raise_on_send
        self.sent.append((msg, from_addr, to_addrs))

    def quit(self):
        self.quit_called = True

    def close(self):
        self.close_called = True


def _recipients_refused(code: int, addr: str = "c@d.com") -> smtplib.SMTPRecipientsRefused:
    return smtplib.SMTPRecipientsRefused({addr: (code, b"mock")})


class TestEmailer(unittest.TestCase):
    def setUp(self) -> None:
        FakeSMTP.instances.clear()
        FakeSMTP.init_exception = None
        FakeSMTP.always_raise_on_send = None
        FakeSMTP.send_plan = []

        self._smtp_patch = patch("smtplib.SMTP", FakeSMTP)
        self._smtps_patch = patch("smtplib.SMTP_SSL", FakeSMTP)
        self._smtp_patch.start()
        self._smtps_patch.start()
        self.addCleanup(self._smtp_patch.stop)
        self.addCleanup(self._smtps_patch.stop)

    def _make_emailer(self, **kwargs) -> Emailer:
        kwargs.setdefault("host", "smtp.test")
        kwargs.setdefault("port", 587)
        kwargs.setdefault("ssl", False)
        kwargs.setdefault("interval", 3600)
        kwargs.setdefault("sleep", 0.01)
        return Emailer(**kwargs)

    # -- Happy path -------------------------------------------------------

    def test_sends_email_successfully(self):
        emailer = self._make_emailer()
        emailer.queue(
            from_address="a@b.com",
            to="c@d.com",
            subject="hi",
            content_txt="hello",
        )

        emailer.on_process()

        self.assertEqual(len(FakeSMTP.instances), 1)
        smtp = FakeSMTP.instances[0]
        self.assertEqual(len(smtp.sent), 1)
        msg, from_addr, to_addrs = smtp.sent[0]
        self.assertEqual(from_addr, "a@b.com")
        self.assertEqual(to_addrs, ["c@d.com"])
        self.assertEqual(msg["Subject"], "hi")
        self.assertTrue(smtp.quit_called)
        self.assertEqual(emailer.queued, 0)

    def test_login_called_when_credentials_provided(self):
        emailer = self._make_emailer(username="u", password="p")
        emailer.queue(from_address="a@b.com", to="c@d.com", subject="s", content_txt="x")
        emailer.on_process()
        self.assertEqual(FakeSMTP.instances[0].login_args, ("u", "p"))

    def test_no_login_when_credentials_absent(self):
        emailer = self._make_emailer()
        emailer.queue(from_address="a@b.com", to="c@d.com", subject="s", content_txt="x")
        emailer.on_process()
        self.assertIsNone(FakeSMTP.instances[0].login_args)

    def test_bcc_not_in_headers_but_in_envelope(self):
        emailer = self._make_emailer()
        emailer.queue(
            from_address="a@b.com",
            to="c@d.com",
            subject="s",
            content_txt="x",
            bcc="hidden@x.com",
            cc="cc@x.com",
        )
        emailer.on_process()

        msg, _, to_addrs = FakeSMTP.instances[0].sent[0]
        self.assertNotIn("Bcc", msg)
        self.assertIn("hidden@x.com", to_addrs)
        self.assertIn("cc@x.com", to_addrs)
        self.assertIn("cc@x.com", msg["Cc"])

    def test_uses_ssl_class_when_ssl_true(self):
        emailer = self._make_emailer(ssl=True)
        emailer.queue(from_address="a@b.com", to="c@d.com", subject="s", content_txt="x")
        emailer.on_process()
        self.assertEqual(len(FakeSMTP.instances), 1)

    # -- Chunking ---------------------------------------------------------

    def test_chunk_sends_at_most_chunk_per_process(self):
        emailer = self._make_emailer(chunk=2)
        for i in range(5):
            emailer.queue(
                from_address="a@b.com",
                to="c@d.com",
                subject=f"s{i}",
                content_txt="x",
            )

        emailer.on_process()

        self.assertEqual(len(FakeSMTP.instances), 1)
        self.assertEqual(len(FakeSMTP.instances[0].sent), 2)
        self.assertEqual(emailer.queued, 3)

    def test_chunk_reuses_single_connection_for_all_sends(self):
        emailer = self._make_emailer(chunk=5)
        for i in range(3):
            emailer.queue(
                from_address="a@b.com",
                to="c@d.com",
                subject=f"s{i}",
                content_txt="x",
            )

        emailer.on_process()

        self.assertEqual(len(FakeSMTP.instances), 1)
        self.assertEqual(len(FakeSMTP.instances[0].sent), 3)
        self.assertTrue(FakeSMTP.instances[0].quit_called)

    def test_second_process_drains_next_chunk(self):
        emailer = self._make_emailer(chunk=2)
        for i in range(3):
            emailer.queue(
                from_address="a@b.com",
                to="c@d.com",
                subject=f"s{i}",
                content_txt="x",
            )

        emailer.on_process()
        emailer.on_process()

        self.assertEqual(len(FakeSMTP.instances), 2)
        self.assertEqual(sum(len(i.sent) for i in FakeSMTP.instances), 3)
        self.assertEqual(emailer.queued, 0)

    # -- Transient vs permanent ------------------------------------------

    def test_transient_failure_requeues_with_bumped_retry(self):
        emailer = self._make_emailer(chunk=1, max_retries=3)
        emailer.queue(from_address="a@b.com", to="c@d.com", subject="s", content_txt="x")

        FakeSMTP.always_raise_on_send = _recipients_refused(450)
        emailer.on_process()

        self.assertEqual(emailer.queued, 1)
        with emailer.lock:
            item = emailer._queue[0]
        self.assertEqual(item.retry_count, 1)
        self.assertEqual(item.subject, "s")

    def test_permanent_failure_discards_immediately(self):
        emailer = self._make_emailer(chunk=1, max_retries=5)
        emailer.queue(from_address="a@b.com", to="c@d.com", subject="s", content_txt="x")

        FakeSMTP.always_raise_on_send = _recipients_refused(550)
        emailer.on_process()

        self.assertEqual(emailer.queued, 0)

    def test_max_retries_exhausted_discards(self):
        emailer = self._make_emailer(chunk=1, max_retries=2)
        emailer.queue(from_address="a@b.com", to="c@d.com", subject="s", content_txt="x")

        FakeSMTP.always_raise_on_send = _recipients_refused(450)

        emailer.on_process()  # fail -> retry_count 1
        self.assertEqual(emailer.queued, 1)
        emailer.on_process()  # fail -> retry_count 2
        self.assertEqual(emailer.queued, 1)
        emailer.on_process()  # fail -> retry_count >= max -> discard
        self.assertEqual(emailer.queued, 0)

    def test_smtp_response_4xx_is_transient(self):
        emailer = self._make_emailer(chunk=1, max_retries=3)
        emailer.queue(from_address="a@b.com", to="c@d.com", subject="s", content_txt="x")
        FakeSMTP.always_raise_on_send = smtplib.SMTPResponseException(451, b"try later")
        emailer.on_process()
        self.assertEqual(emailer.queued, 1)

    def test_smtp_response_5xx_is_permanent(self):
        emailer = self._make_emailer(chunk=1, max_retries=3)
        emailer.queue(from_address="a@b.com", to="c@d.com", subject="s", content_txt="x")
        FakeSMTP.always_raise_on_send = smtplib.SMTPResponseException(550, b"nope")
        emailer.on_process()
        self.assertEqual(emailer.queued, 0)

    # -- Connection-level failures ---------------------------------------

    def test_connect_failure_requeues_untouched(self):
        emailer = self._make_emailer(chunk=3)
        for i in range(3):
            emailer.queue(
                from_address="a@b.com",
                to="c@d.com",
                subject=f"s{i}",
                content_txt="x",
            )

        FakeSMTP.init_exception = OSError("connection refused")
        emailer.on_process()

        self.assertEqual(emailer.queued, 3)
        with emailer.lock:
            for item in emailer._queue:
                self.assertEqual(item.retry_count, 0)

    def test_disconnect_mid_batch_requeues_remaining_untouched(self):
        emailer = self._make_emailer(chunk=3)
        for i in range(3):
            emailer.queue(
                from_address="a@b.com",
                to="c@d.com",
                subject=f"s{i}",
                content_txt="x",
            )

        # First send succeeds, second disconnects, third never attempted.
        FakeSMTP.send_plan = [None, smtplib.SMTPServerDisconnected("gone")]
        emailer.on_process()

        # s0 went out; s1 and s2 back in the queue untouched.
        self.assertEqual(emailer.queued, 2)
        with emailer.lock:
            items = list(emailer._queue)
        self.assertEqual([i.subject for i in items], ["s1", "s2"])
        for item in items:
            self.assertEqual(item.retry_count, 0)

        total_sent = sum(len(inst.sent) for inst in FakeSMTP.instances)
        self.assertEqual(total_sent, 1)

    # -- Ordering ---------------------------------------------------------

    def test_failed_item_goes_back_to_front(self):
        emailer = self._make_emailer(chunk=1, max_retries=3)
        emailer.queue(from_address="a@b.com", to="c@d.com", subject="first", content_txt="x")
        emailer.queue(from_address="a@b.com", to="c@d.com", subject="second", content_txt="x")

        # Fail the first send, then let subsequent sends succeed.
        FakeSMTP.send_plan = [_recipients_refused(450), None, None]

        emailer.on_process()  # "first" fails and is requeued to front
        with emailer.lock:
            subjects = [i.subject for i in emailer._queue]
        self.assertEqual(subjects, ["first", "second"])

        emailer.on_process()  # "first" retried and succeeds
        emailer.on_process()  # "second" sent
        self.assertEqual(emailer.queued, 0)

    # -- Validation -------------------------------------------------------

    def test_invalid_from_raises(self):
        emailer = self._make_emailer()
        with self.assertRaises(ValueError):
            emailer.queue(from_address="not-an-email", to="c@d.com", subject="s")

    def test_invalid_to_raises(self):
        emailer = self._make_emailer()
        with self.assertRaises(ValueError):
            emailer.queue(from_address="a@b.com", to="not-an-email", subject="s")

    def test_empty_to_raises(self):
        emailer = self._make_emailer()
        with self.assertRaises(ValueError):
            emailer.queue(from_address="a@b.com", to=[], subject="s")

    def test_invalid_bcc_raises(self):
        emailer = self._make_emailer()
        with self.assertRaises(ValueError):
            emailer.queue(
                from_address="a@b.com",
                to="c@d.com",
                subject="s",
                bcc="nope",
            )

    def test_queue_capacity_raises(self):
        emailer = self._make_emailer(max_queue_size=2)
        emailer.queue(from_address="a@b.com", to="c@d.com", subject="1", content_txt="x")
        emailer.queue(from_address="a@b.com", to="c@d.com", subject="2", content_txt="x")
        with self.assertRaises(RuntimeError):
            emailer.queue(from_address="a@b.com", to="c@d.com", subject="3", content_txt="x")

    # -- Drain on stop() --------------------------------------------------

    def test_stop_drains_remaining_queue(self):
        emailer = self._make_emailer(chunk=1, interval=3600, drain_timeout=5)
        emailer.start()
        self.addCleanup(emailer.stop)  # double-stop is safe
        time.sleep(0.1)  # let the first (empty) on_process run and idle

        emailer.queue(from_address="a@b.com", to="c@d.com", subject="s1", content_txt="x")
        emailer.queue(from_address="a@b.com", to="c@d.com", subject="s2", content_txt="x")

        emailer.stop()

        total_sent = sum(len(inst.sent) for inst in FakeSMTP.instances)
        self.assertEqual(total_sent, 2)
        self.assertEqual(emailer.queued, 0)

    def test_stop_drain_respects_deadline(self):
        emailer = self._make_emailer(chunk=1, interval=3600, drain_timeout=0.1)
        emailer.start()
        self.addCleanup(emailer.stop)
        time.sleep(0.1)

        # Force every drain attempt to fail at connect, so the queue never
        # empties and the loop must exit on the deadline.
        FakeSMTP.init_exception = OSError("refused")
        emailer.queue(from_address="a@b.com", to="c@d.com", subject="s", content_txt="x")

        t0 = time.monotonic()
        emailer.stop()
        elapsed = time.monotonic() - t0

        self.assertGreaterEqual(elapsed, 0.05)
        self.assertLess(elapsed, 1.0)
        self.assertEqual(emailer.queued, 1)


if __name__ == "__main__":
    unittest.main()
