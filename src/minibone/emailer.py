import email.utils as utils
import logging
import smtplib
from email.message import EmailMessage

from minibone.daemon import Daemon


class Emailer(Daemon):
    """Class to send emails using a SMTP server

    This class allows to send emails using a queue in a thread as underground task.
    The queue will be processed as FIFO (first in first out)
    Currently only text and html content are supported (not attachments)

    Usage:
    ------
    intance Emailer, call start, call queue to send emails, call stop at the end of your program
    note stop finishes until all queued emails were sent

    Example
    -------
    import Emailer
    import timer

    # use your own server configuration
    emailer = Emailer(host, port, ssl=True, username="user", password="1234")
    emailer.start()
    emailer.queue(
        from_address="me@domain.com",
        to="you@domain.com",
        subject="Notification",
        content_txt="This is a text notification"
        content_html="This is a <b>html</b> notification"
    )

    # your logic

    # sleep to simulate more logic, emails were send in the background in the meantime
    time.sleep(20)

    emailer.stop()
    """

    def __init__(self, host: str, port: int, ssl: bool, username: str = None, password: str = None):
        """
        Arguments
        ---------
        host:       str     host to conenct to
        port:       int     the port number to connect to
        ssl:        bool    True to use SSL encryption (must be supported by the server)
                            Set to False for plain connection (And may God have mercy on your poor soul!)
        username:   str     The username to login to the server
        password:   str     The password to login to the server
        """
        assert isinstance(host, str)
        assert isinstance(port, int)
        assert isinstance(ssl, bool)
        assert not username or isinstance(username, str)
        assert not password or isinstance(password, str)

        super().__init__(name="Emailer", interval=1)

        self._logger = logging.getLogger(__class__.__name__)

        self._host = host
        self._port = port
        self._ssl = ssl
        self._username = username
        self._password = password

        self._queue = []
        self._timeout = 10

    @property
    def host(self) -> str:
        """The host to connect to"""
        return self._host

    @property
    def port(self) -> int:
        """The port to connect to"""
        return self._port

    @property
    def ssl(self) -> bool:
        """The ssl flag using to connect to (True/False)"""
        return self._ssl

    @property
    def queued(self) -> int:
        """Number of emails pending to be delivered"""
        return len(self._queue)

    def queue(
        self,
        from_address: str,
        to: str | list,
        subject: str,
        content_txt: str = None,
        content_html: str = None,
        cc: str = None,
        bcc: str = None,
        replyto: str = None,
    ):
        """Add a new email to the queue to be delivered

        Arguments
        ---------
        from_address:   str     Address to use as email's from
        to:             str     Address to send email to (can be a list of str addresses)
        subject:        str     Email's subject
        content_txt:    str     Emails's content in text format
        content_html:   str     Emails's content in html format
        cc:             str     Address to cc this email to (can be a list of str addresses)
        bcc:            str     Address to bcc this email to (can be a list of str addresses)
        replyto:        str     Addres to get reply if diferrent from from_address
        """
        assert isinstance(from_address, str)
        assert isinstance(to, (str, list))
        assert isinstance(subject, str)
        assert not content_txt or isinstance(content_txt, str)
        assert not content_html or isinstance(content_html, str)
        assert not cc or isinstance(cc, (str, list))
        assert not bcc or isinstance(bcc, (str, list))
        assert not replyto or isinstance(replyto, str)

        if isinstance(to, str):
            to = [to]

        if isinstance(cc, str):
            cc = [cc]

        if isinstance(bcc, str):
            bcc = [bcc]

        # RFC 5322                Internet Message Format             October 2008
        # https://datatracker.ietf.org/doc/html/rfc5322.html
        #
        # fields =   *(trace
        #     *optional-field /
        #     *(resent-date /
        #     resent-from /
        #     resent-sender /
        #     resent-to /
        #     resent-cc /
        #     resent-bcc /
        #     resent-msg-id))
        # *(orig-date /
        # from /
        # sender /
        # reply-to /
        # to /
        # cc /
        # bcc /
        # message-id /
        # in-reply-to /
        # references /
        # subject /
        # comments /
        # keywords /
        # optional-field)

        self.lock.acquire()
        self._queue.append({
            "from": from_address,
            "to": to,
            "subject": subject,
            "text": content_txt,
            "html": content_html,
            "cc": cc,
            "bcc": bcc,
            "replyto": replyto,
        })
        self.lock.release()

    def on_process(self):
        self.lock.acquire()

        if len(self._queue) > 0:
            item = self._queue[0]
            try:
                msg = EmailMessage()

                msg["Date"] = utils.formatdate()
                msg["From"] = item["from"]
                msg["To"] = item["to"]
                msg["Subject"] = item["subject"]

                if item["text"]:
                    msg.set_content(item["text"])
                if item["html"]:
                    msg.add_alternative(item["html"], subtype="html")

                if item["cc"]:
                    msg["Cc"] = item["cc"]

                if item["bcc"]:
                    msg["Bcc"] = item["bcc"]

                if item["replyto"]:
                    msg["Reply-To"] = item["replyto"]

                if self.ssl:
                    s = smtplib.SMTP_SSL(host=self.host, port=self.port, timeout=self._timeout)
                else:
                    s = smtplib.SMTP(host=self.host, port=self.port, timeout=self._timeout)

                if self._username or self._password:
                    s.login(user=self._username, password=self._password)

                s.send_message(msg)
                s.quit()

                item = self._queue.pop(0)

                self._logger.info("Dispatched [{}] to {}".format(item["subject"], item["to"]))

            except Exception as e:
                self._logger.error("Error sending email to %s  %s", item["to"], e)

        self.lock.release()

    def stop(self):
        super().stop()

        if len(self._queue) > 0:
            self._logger.info("Dispaching %d pending emails before stop", len(self._queue))
            while len(self._queue) > 0:
                self._do_process()
                self._logger.info("Dispaching %d pending emails before stop", len(self._queue))
