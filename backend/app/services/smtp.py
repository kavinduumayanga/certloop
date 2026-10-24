import smtplib
import socket
import ssl
import hashlib
import logging
import re
import time
from dataclasses import dataclass
from email.message import EmailMessage
from pathlib import Path


logger = logging.getLogger("certificate.smtp")


class DefiniteSendError(Exception):
    """The message was definitely not accepted and can be reviewed/retried safely."""


class TransientSendError(Exception):
    """The server definitely rejected the attempt temporarily; bounded retry is safe."""

    def __init__(self, message: str, smtp_code: int | None = None, rate_limited: bool = False, retry_after: int | None = None):
        super().__init__(message)
        self.smtp_code = smtp_code
        self.rate_limited = rate_limited
        self.retry_after = retry_after


class UncertainSendError(Exception):
    """The connection failed during submission, so acceptance cannot be ruled out."""


@dataclass(frozen=True)
class SMTPIdentity:
    email: str
    aliases: list[str]


def _smtp_response_error(exc: smtplib.SMTPResponseException) -> Exception:
    detail = exc.smtp_error.decode(errors="replace") if isinstance(exc.smtp_error, bytes) else str(exc.smtp_error)
    if 400 <= exc.smtp_code < 500:
        normalized = detail.casefold()
        rate_limited = exc.smtp_code in {421, 452} or any(token in normalized for token in ("rate", "quota", "limit", "too many"))
        retry_match = re.search(r"(?:retry|try again)[^0-9]{0,20}(\d{1,5})\s*(?:s|sec|second)", normalized)
        return TransientSendError(
            f"SMTP temporary rejection ({exc.smtp_code}); retry is safe",
            smtp_code=exc.smtp_code,
            rate_limited=rate_limited,
            retry_after=int(retry_match.group(1)) if retry_match else None,
        )
    return DefiniteSendError(f"SMTP rejected the message ({exc.smtp_code})")


def _job_reference(idempotency_key: str) -> str:
    return hashlib.sha256(idempotency_key.encode("utf-8")).hexdigest()[:12]


def message_id_for(idempotency_key: str, sender_email: str) -> str:
    domain = sender_email.rsplit("@", 1)[-1]
    return f"<{idempotency_key}@{domain}>"


def _response_error(code: int, reply: bytes | str = b"") -> Exception:
    if code == 0:
        return TransientSendError("SMTP server returned no response; retry is safe")
    return _smtp_response_error(smtplib.SMTPResponseException(code, reply))


def _require_reply(stage: str, response: tuple[int, bytes] | None, accepted: set[int]) -> None:
    if not response or response[0] not in accepted:
        code, reply = response if response else (0, b"No SMTP response")
        logger.warning("smtp_event=rejected stage=%s code=%s", stage, code)
        raise _response_error(code, reply)


class SMTPClient:
    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        app_password: str,
        sender_email: str,
        aliases: list[str] | None = None,
        timeout: float = 30,
        data_timeout: float = 300,
        connection_reuse: bool = True,
        max_messages_per_connection: int = 25,
        smtp_factory=smtplib.SMTP,
    ):
        self.host = host
        self.port = port
        self.username = username
        self.app_password = app_password.replace(" ", "")
        self.sender_email = sender_email.casefold()
        self.aliases = [alias.casefold() for alias in aliases or []]
        self.timeout = timeout
        self.data_timeout = data_timeout
        self.connection_reuse = connection_reuse
        self.max_messages_per_connection = max(1, max_messages_per_connection)
        self.smtp_factory = smtp_factory
        self._smtp = None
        self._messages_sent = 0

    def identity(self) -> SMTPIdentity:
        return SMTPIdentity(self.sender_email, self.aliases)

    def _discard_connection(self) -> None:
        smtp, self._smtp = self._smtp, None
        self._messages_sent = 0
        if smtp:
            try:
                smtp.close()
            except Exception:
                pass

    def close(self) -> None:
        """Close the reusable SMTP session without changing any send outcome."""
        smtp, self._smtp = self._smtp, None
        self._messages_sent = 0
        if not smtp:
            return
        try:
            smtp.quit()
        except Exception:
            try:
                smtp.close()
            except Exception:
                pass

    def _connect(self, job_ref: str):
        stage = "connect"
        connect_started = time.perf_counter()
        smtp = None
        try:
            logger.info("smtp_event=starting stage=connect job=%s host=%s port=%s", job_ref, self.host, self.port)
            smtp = self.smtp_factory(self.host, self.port, timeout=self.timeout)
            logger.info("smtp_event=completed stage=connect job=%s duration_ms=%s", job_ref, round((time.perf_counter() - connect_started) * 1000, 1))
            stage = "ehlo"
            stage_started = time.perf_counter()
            _require_reply(stage, smtp.ehlo(), {250})
            logger.info("smtp_event=completed stage=ehlo job=%s duration_ms=%s", job_ref, round((time.perf_counter() - stage_started) * 1000, 1))
            if not smtp.has_extn("starttls"):
                raise DefiniteSendError("SMTP server did not advertise STARTTLS")
            stage = "starttls"
            stage_started = time.perf_counter()
            _require_reply(stage, smtp.starttls(context=ssl.create_default_context()), {220})
            logger.info("smtp_event=completed stage=starttls job=%s duration_ms=%s", job_ref, round((time.perf_counter() - stage_started) * 1000, 1))
            stage = "ehlo_after_tls"
            _require_reply(stage, smtp.ehlo(), {250})
            if not smtp.has_extn("auth"):
                raise DefiniteSendError("SMTP server did not advertise authentication after STARTTLS")
            stage = "authentication"
            stage_started = time.perf_counter()
            _require_reply(stage, smtp.login(self.username, self.app_password), {235, 503})
            self._smtp = smtp
            self._messages_sent = 0
            logger.info("smtp_event=authenticated job=%s tls=true duration_ms=%s", job_ref, round((time.perf_counter() - stage_started) * 1000, 1))
            return smtp
        except smtplib.SMTPAuthenticationError as exc:
            if smtp:
                try:
                    smtp.close()
                except Exception:
                    pass
            logger.warning("smtp_event=failed stage=authentication job=%s code=%s", job_ref, exc.smtp_code)
            raise DefiniteSendError("Google rejected the SMTP username or App Password") from exc
        except smtplib.SMTPResponseException as exc:
            if smtp:
                try:
                    smtp.close()
                except Exception:
                    pass
            logger.warning("smtp_event=failed stage=%s job=%s code=%s", stage, job_ref, exc.smtp_code)
            raise _smtp_response_error(exc) from exc
        except (DefiniteSendError, TransientSendError):
            if smtp:
                try:
                    smtp.close()
                except Exception:
                    pass
            logger.warning("smtp_event=failed stage=%s job=%s category=configuration", stage, job_ref)
            raise
        except (smtplib.SMTPException, socket.timeout, TimeoutError, OSError) as exc:
            if smtp:
                try:
                    smtp.close()
                except Exception:
                    pass
            logger.warning("smtp_event=failed stage=%s job=%s category=connection exception=%s", stage, job_ref, type(exc).__name__)
            raise TransientSendError(f"SMTP {stage} failed before message submission; retry is safe") from exc

    def _connection(self, job_ref: str):
        if self._smtp and self._messages_sent >= self.max_messages_per_connection:
            logger.info("smtp_event=recycling job=%s messages=%s", job_ref, self._messages_sent)
            self.close()
        return self._smtp or self._connect(job_ref)

    @staticmethod
    def _set_socket_timeout(smtp, timeout: float) -> None:
        sock = getattr(smtp, "sock", None)
        if sock and hasattr(sock, "settimeout"):
            sock.settimeout(timeout)

    def send(self, sender: str, recipient: str, subject: str, body: str, attachment: Path, idempotency_key: str) -> str:
        send_started = time.perf_counter()
        job_ref = _job_reference(idempotency_key)
        if sender.casefold() not in set(self.aliases + [self.sender_email]):
            raise DefiniteSendError("Sender is not the configured Gmail account or an allowed alias")
        try:
            attachment_started = time.perf_counter()
            payload = attachment.read_bytes()
        except OSError as exc:
            raise DefiniteSendError("Certificate attachment is missing") from exc
        logger.info("smtp_event=attachment_loaded job=%s bytes=%s duration_ms=%s", job_ref, len(payload), round((time.perf_counter() - attachment_started) * 1000, 1))

        mime_started = time.perf_counter()
        message_id = message_id_for(idempotency_key, self.sender_email)
        message = EmailMessage()
        message["To"] = recipient
        message["From"] = sender
        message["Subject"] = subject
        message["Message-ID"] = message_id
        message["X-Certificate-Delivery-ID"] = idempotency_key
        message.set_content(body)
        message.add_attachment(payload, maintype="application", subtype="pdf", filename=attachment.name)
        raw_message = message.as_bytes()
        logger.info("smtp_event=mime_ready job=%s bytes=%s duration_ms=%s", job_ref, len(raw_message), round((time.perf_counter() - mime_started) * 1000, 1))

        connection_started = time.perf_counter()
        smtp = self._connection(job_ref)
        logger.info("smtp_event=connection_ready job=%s reused=%s duration_ms=%s", job_ref, self._messages_sent > 0, round((time.perf_counter() - connection_started) * 1000, 1))

        stage = "mail_from"
        try:
            mail_options = [f"SIZE={len(raw_message)}"] if smtp.has_extn("size") else []
            _require_reply(stage, smtp.mail(sender, options=mail_options), {250})
            stage = "recipient"
            _require_reply(stage, smtp.rcpt(recipient), {250, 251, 252})
            stage = "data"
            self._set_socket_timeout(smtp, self.data_timeout)
            logger.info("smtp_event=submitting stage=data job=%s bytes=%s timeout_seconds=%s", job_ref, len(raw_message), self.data_timeout)
            data_started = time.perf_counter()
            response = smtp.data(raw_message)
            _require_reply(stage, response, {250})
            self._set_socket_timeout(smtp, self.timeout)
            self._messages_sent += 1
            logger.info("smtp_event=accepted stage=data job=%s code=%s data_ms=%s total_ms=%s", job_ref, response[0], round((time.perf_counter() - data_started) * 1000, 1), round((time.perf_counter() - send_started) * 1000, 1))
        except smtplib.SMTPResponseException as exc:
            logger.warning("smtp_event=rejected stage=%s job=%s code=%s", stage, job_ref, exc.smtp_code)
            # A 421 closes the channel. Other explicit replies are definite, but
            # discarding also avoids carrying an unknown transaction state forward.
            self._discard_connection()
            raise _smtp_response_error(exc) from exc
        except (DefiniteSendError, TransientSendError):
            self._discard_connection()
            raise
        except (smtplib.SMTPServerDisconnected, smtplib.SMTPException, socket.timeout, TimeoutError, OSError) as exc:
            logger.warning("smtp_event=interrupted stage=%s job=%s exception=%s", stage, job_ref, type(exc).__name__)
            self._discard_connection()
            if stage == "data":
                if isinstance(exc, (socket.timeout, TimeoutError)):
                    raise UncertainSendError(f"SMTP DATA upload or final acknowledgment timed out after {self.data_timeout:g} seconds; Gmail acceptance is unknown") from exc
                raise UncertainSendError("SMTP connection ended before the final DATA acknowledgment; Gmail acceptance is unknown") from exc
            raise TransientSendError(f"SMTP connection ended during {stage} before DATA submission; retry is safe") from exc
        if not self.connection_reuse:
            self.close()
        return message_id

