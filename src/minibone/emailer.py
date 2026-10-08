"""Email sender with background queue processing (thread-based).

Queue items are frozen slotted dataclasses. The queue is a bounded deque
with O(1) popleft/appendleft. Each on_process call opens one SMTP
connection and sends up to `chunk` emails over it. Transient failures are
requeued with a bounded retry count; permanent failures are discarded.
"""

from __future__ import annotations

import contextlib
import logging
import re
import smtplib
import time
from collections import deque
from dataclasses import dataclass
from dataclasses import replace
from email import utils
from email.message import EmailMessage

from minibone.daemon import Daemon


_RESPONSE_4XX: int = 400
_RESPONSE_5XX: int = 500
_RESPONSE_6XX: int = 600

_EMAIL_RE = re.compile(r"^[^@\s<>]+@[^@\s<>]+\.[^@\s<>]+$")


def _validate_addresses(addrs: tuple[str, ...], field: str) -> None:
    for addr in addrs:
        if not _EMAIL_RE.match(addr):
            raise ValueError(f"Invalid {field} address: {addr}")


@dataclass(slots=True, frozen=True)
class Email:
    """Immutable queued email. Use dataclasses.replace() to update."""

    from_address: str
    to: tuple[str, ...]
    subject: str
    content_txt: str | None = None
    content_html: str | None = None
    cc: tuple[str, ...] = ()
    bcc: tuple[str, ...] = ()
    replyto: str | None = None
    retry_count: int = 0

    @property
    def envelope_recipients(self) -> list[str]:
        """All envelope RCPT TO addresses (To + Cc + Bcc)."""
        return [*self.to, *self.cc, *self.bcc]


class Emailer(Daemon):
    """Send emails over SMTP with a background queue.

    Features:
    - Frozen slotted dataclass queue items
    - Bounded deque (O(1) pop/append; appendleft for retries)
    - Chunked sends over a single SMTP connection per batch
    - Transient (4xx) vs permanent (5xx) failure classification
    - Bounded retries with drop-after-max
    - Bcc handled at envelope level, never as a header
    - Queue capacity limit
    - Graceful drain on stop() with a deadline
    """

    def __init__(
        self,
        host: str,
        port: int,
        ssl: bool,
        *,
        username: str | None = None,
        password: str | None = None,
        interval: float = 1,
        sleep: float = 0.5,
        chunk: int = 10,
        max_retries: int = 3,
        timeout: float = 10.0,
        max_queue_size: int = 10_000,
        drain_timeout: float = 30.0,
    ):
        assert isinstance(host, str)
        assert isinstance(port, int)
        assert isinstance(ssl, bool)
        assert not username or isinstance(username, str)
        assert not password or isinstance(password, str)
        assert chunk >= 1
        assert max_retries >= 0
        assert timeout > 0
        assert max_queue_size >= 1
        assert drain_timeout > 0

        super().__init__(name="Emailer", interval=interval, sleep=sleep)

        self._logger = logging.getLogger(self.__class__.__name__)

        self._host = host
        self._port = port
        self._ssl = ssl
        self._username = username
        self._password = password

        self._chunk = chunk
        self._max_retries = max_retries
        self._timeout = timeout
        self._max_queue_size = max_queue_size
        self._drain_timeout = drain_timeout

        self._queue: deque[Email] = deque()

    # -- Read-only state --------------------------------------------------

    @property
    def host(self) -> str:
        return self._host

    @property
    def port(self) -> int:
        return self._port

    @property
    def ssl(self) -> bool:
        return self._ssl

    @property
    def queued(self) -> int:
        with self.lock:
            return len(self._queue)

    # -- Public API -------------------------------------------------------

    def queue(
        self,
        from_address: str,
        to: str | list[str],
        subject: str,
        content_txt: str | None = None,
        content_html: str | None = None,
        cc: str | list[str] | None = None,
        bcc: str | list[str] | None = None,
        replyto: str | None = None,
    ) -> None:
        """Add a new email to the queue.

        Raises:
            ValueError: invalid address.
            RuntimeError: queue is full.
        """
        assert isinstance(from_address, str)
        assert isinstance(to, str | list)
        assert isinstance(subject, str)
        assert not content_txt or isinstance(content_txt, str)
        assert not content_html or isinstance(content_html, str)
        assert not cc or isinstance(cc, str | list)
        assert not bcc or isinstance(bcc, str | list)
        assert not replyto or isinstance(replyto, str)

        to_t = (to,) if isinstance(to, str) else tuple(to)
        cc_t = (cc,) if isinstance(cc, str) else tuple(cc or ())
        bcc_t = (bcc,) if isinstance(bcc, str) else tuple(bcc or ())

        if not to_t:
            raise ValueError("At least one 'to' address is required")

        _validate_addresses((from_address,), "from")
        _validate_addresses(to_t, "to")
        _validate_addresses(cc_t, "cc")
        _validate_addresses(bcc_t, "bcc")
        if replyto:
            _validate_addresses((replyto,), "reply-to")

        item = Email(
            from_address=from_address,
            to=to_t,
            subject=subject,
            content_txt=content_txt,
            content_html=content_html,
            cc=cc_t,
            bcc=bcc_t,
            replyto=replyto,
        )

        with self.lock:
            if len(self._queue) >= self._max_queue_size:
                raise RuntimeError(f"Email queue is full ({self._max_queue_size} items)")
            self._queue.append(item)

    # -- Daemon hook ------------------------------------------------------

    def on_process(self) -> None:
        """Send up to `chunk` emails over a single SMTP connection."""
        batch = self._pop_batch()
        if not batch:
            return

        remaining = list(batch)

        try:
            smtp = self._connect()
        except Exception as e:
            # Cannot even connect. Infrastructure problem, not recipient.
            # Requeue without incrementing retry_count.
            self._logger.error("SMTP connection failed: %s", e)
            self._requeue_untouched(remaining)
            return

        try:
            while remaining:
                item = remaining[0]
                try:
                    self._send_one(smtp, item)
                except smtplib.SMTPServerDisconnected as e:
                    # Connection died mid-batch. Requeue the rest untouched
                    # so a fresh connection retries them next interval.
                    self._logger.error(
                        "SMTP disconnected while sending [%s] to %s: %s",
                        item.subject,
                        item.to,
                        e,
                    )
                    self._requeue_untouched(remaining)
                    return
                except smtplib.SMTPException as e:
                    self._handle_message_failure(item, e)
                except Exception as e:
                    self._logger.error(
                        "Unexpected error sending [%s] to %s: %s",
                        item.subject,
                        item.to,
                        e,
                    )
                    self._handle_transient(item, e)
                remaining.pop(0)
        finally:
            self._close_quietly(smtp)

    # -- Internals --------------------------------------------------------

    def _pop_batch(self) -> list[Email]:
        with self.lock:
            batch: list[Email] = []
            while self._queue and len(batch) < self._chunk:
                batch.append(self._queue.popleft())
            return batch

    def _connect(self) -> smtplib.SMTP:
        if self._ssl:
            smtp: smtplib.SMTP = smtplib.SMTP_SSL(host=self._host, port=self._port, timeout=self._timeout)
        else:
            smtp = smtplib.SMTP(host=self._host, port=self._port, timeout=self._timeout)
        if self._username or self._password:
            smtp.login(user=self._username, password=self._password)
        return smtp

    def _close_quietly(self, smtp: smtplib.SMTP) -> None:
        try:
            smtp.quit()
        except Exception:
            with contextlib.suppress(Exception):
                smtp.close()

    def _send_one(self, smtp: smtplib.SMTP, item: Email) -> None:
        msg = EmailMessage()
        msg["Date"] = utils.formatdate()
        msg["From"] = item.from_address
        msg["To"] = ", ".join(item.to)
        msg["Subject"] = item.subject

        if item.cc:
            msg["Cc"] = ", ".join(item.cc)
        if item.replyto:
            msg["Reply-To"] = item.replyto

        # Bcc is deliberately NOT a header. It only goes in the envelope
        # via to_addrs below, so recipients cannot see it.

        if item.content_txt:
            msg.set_content(item.content_txt)
            if item.content_html:
                msg.add_alternative(item.content_html, subtype="html")
        elif item.content_html:
            msg.set_content(item.content_html, subtype="html")

        smtp.send_message(
            msg,
            from_addr=item.from_address,
            to_addrs=item.envelope_recipients,
        )

        self._logger.info(
            "Sent [%s] to %s (retry=%d)",
            item.subject,
            item.to,
            item.retry_count,
        )

    def _handle_message_failure(self, item: Email, exc: smtplib.SMTPException) -> None:
        if self._is_transient(exc):
            self._handle_transient(item, exc)
        else:
            self._logger.error(
                "Permanent failure [%s] to %s: %s (discarding)",
                item.subject,
                item.to,
                exc,
            )

    def _handle_transient(self, item: Email, exc: Exception) -> None:
        if item.retry_count >= self._max_retries:
            self._logger.error(
                "Giving up on [%s] to %s after %d retries: %s",
                item.subject,
                item.to,
                item.retry_count,
                exc,
            )
            return

        retried = replace(item, retry_count=item.retry_count + 1)
        with self.lock:
            self._queue.appendleft(retried)
        self._logger.warning(
            "Requeued [%s] to %s (retry %d/%d): %s",
            item.subject,
            item.to,
            retried.retry_count,
            self._max_retries,
            exc,
        )

    def _requeue_untouched(self, items: list[Email]) -> None:
        """Put items back at the front without bumping retry_count.

        Used for connection-level failures, which are our fault, not the
        recipient's.
        """
        with self.lock:
            for item in reversed(items):
                self._queue.appendleft(item)

    @staticmethod
    def _is_transient(exc: smtplib.SMTPException) -> bool:
        # SMTPRecipientsRefused carries {recipient: (code, message)}.
        recipients = getattr(exc, "recipients", None)
        if recipients:
            codes = [c for c, _ in recipients.values()]
            # Any 5xx -> permanent. Otherwise treat as transient.
            return not any(_RESPONSE_5XX <= c < _RESPONSE_6XX for c in codes)

        code = getattr(exc, "smtp_code", None)
        if code is None:
            # Unknown error type: be conservative, retry.
            return True
        return _RESPONSE_4XX <= code < _RESPONSE_5XX

    def stop(self) -> None:
        """Stop the thread, then drain what's left with a deadline."""
        super().stop()

        if not self._queue:
            return

        self._logger.info("Draining %d pending emails before stop", len(self._queue))
        deadline = time.monotonic() + self._drain_timeout

        while self._queue and time.monotonic() < deadline:
            try:
                self.on_process()
            except Exception as e:
                self._logger.error("Error during drain: %s", e)
                break

        leftover = len(self._queue)
        if leftover:
            self._logger.warning("Drain deadline reached with %d emails still queued", leftover)
