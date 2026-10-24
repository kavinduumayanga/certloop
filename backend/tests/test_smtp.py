import smtplib
import socket
import time
from pathlib import Path

import pytest

from app.services.smtp import DefiniteSendError, SMTPClient, TransientSendError, UncertainSendError


class FakeSocket:
    def __init__(self): self.timeouts=[]
    def settimeout(self,value): self.timeouts.append(value)


class FakeSMTP:
    error = None
    auth_error = None
    instance = None
    instance_count = 0
    data_count = 0

    def __init__(self, host, port, timeout):
        self.host, self.port, self.timeout = host, port, timeout
        self.logged_in = None
        self.message = None
        self.commands = []
        self.sock = FakeSocket()
        FakeSMTP.instance = self
        FakeSMTP.instance_count += 1

    def ehlo(self): self.commands.append("EHLO");return 250,b"ok"
    def has_extn(self, name): return name.lower() in {"starttls","size","auth"}
    def starttls(self, context): self.tls = True;self.commands.append("STARTTLS");return 220,b"ready"
    def login(self, username, password):
        self.logged_in = (username, password)
        if self.auth_error: raise self.auth_error
        self.commands.append("AUTH")
        return 235,b"authenticated"
    def mail(self, sender, options=()): self.commands.append("MAIL");return 250,b"ok"
    def rcpt(self, recipient): self.commands.append("RCPT");return 250,b"ok"
    def data(self, message):
        self.message = message
        self.commands.append("DATA")
        FakeSMTP.data_count += 1
        if self.error: raise self.error
        return 250,b"queued"
    def noop(self): self.commands.append("NOOP");return 250,b"ok"
    def quit(self): pass
    def close(self): pass


def client(tmp_path: Path) -> tuple[SMTPClient, Path]:
    attachment = tmp_path / "certificate.pdf"
    attachment.write_bytes(b"%PDF-test")
    return SMTPClient("smtp.gmail.com", 587, "club@example.edu", "abcd efgh ijkl mnop", "club@example.edu", ["alias@example.edu"], smtp_factory=FakeSMTP), attachment


@pytest.fixture(autouse=True)
def reset_fake_smtp():
    FakeSMTP.error = None
    FakeSMTP.auth_error = None
    FakeSMTP.instance = None
    FakeSMTP.instance_count = 0
    FakeSMTP.data_count = 0


def test_smtp_uses_starttls_app_password_and_stable_headers(tmp_path: Path):
    smtp, attachment = client(tmp_path)
    message_id = smtp.send("alias@example.edu", "ada@example.edu", "Certificate", "Hello Ada", attachment, "cert-batch-participant")
    assert message_id == "<cert-batch-participant@example.edu>"
    assert FakeSMTP.instance.logged_in == ("club@example.edu", "abcdefghijklmnop")
    assert FakeSMTP.instance.tls is True
    assert b"X-Certificate-Delivery-ID: cert-batch-participant" in FakeSMTP.instance.message
    assert FakeSMTP.instance.commands == ["EHLO","STARTTLS","EHLO","AUTH","MAIL","RCPT","DATA"]
    assert FakeSMTP.instance.sock.timeouts == [300, 30]


def test_authenticated_connection_is_reused_for_sequential_messages(tmp_path: Path):
    smtp, attachment = client(tmp_path)
    smtp.send("club@example.edu", "one@example.edu", "One", "Body", attachment, "key-one")
    first = FakeSMTP.instance
    smtp.send("club@example.edu", "two@example.edu", "Two", "Body", attachment, "key-two")
    smtp.close()
    assert FakeSMTP.instance_count == 1
    assert first.commands.count("AUTH") == 1
    assert first.commands.count("DATA") == 2
    assert "NOOP" not in first.commands


def test_connection_is_recycled_after_configured_message_count(tmp_path: Path):
    attachment = tmp_path / "certificate.pdf"
    attachment.write_bytes(b"%PDF-test")
    smtp = SMTPClient("smtp.gmail.com", 587, "club@example.edu", "password", "club@example.edu", max_messages_per_connection=2, smtp_factory=FakeSMTP)
    for index in range(3):
        smtp.send("club@example.edu", f"user{index}@example.edu", "Subject", "Body", attachment, f"key-{index}")
    smtp.close()
    assert FakeSMTP.instance_count == 2


def test_connection_reuse_can_be_disabled_by_configuration(tmp_path: Path):
    attachment = tmp_path / "certificate.pdf"
    attachment.write_bytes(b"%PDF-test")
    smtp = SMTPClient("smtp.gmail.com", 587, "club@example.edu", "password", "club@example.edu", connection_reuse=False, smtp_factory=FakeSMTP)
    smtp.send("club@example.edu", "one@example.edu", "Subject", "Body", attachment, "key-one")
    smtp.send("club@example.edu", "two@example.edu", "Subject", "Body", attachment, "key-two")
    assert FakeSMTP.instance_count == 2


def test_200_messages_use_eight_connections_with_25_message_recycling(tmp_path: Path):
    attachment = tmp_path / "certificate.pdf"
    attachment.write_bytes(b"%PDF-test")
    smtp = SMTPClient("smtp.gmail.com", 587, "club@example.edu", "password", "club@example.edu", max_messages_per_connection=25, smtp_factory=FakeSMTP)
    started = time.perf_counter()
    for index in range(200):
        smtp.send("club@example.edu", f"user{index}@example.edu", "Subject", "Body", attachment, f"key-{index}")
    elapsed = time.perf_counter() - started
    smtp.close()
    assert FakeSMTP.data_count == 200
    assert FakeSMTP.instance_count == 8
    assert elapsed < 5


def test_disconnect_during_submission_is_uncertain(tmp_path: Path):
    smtp, attachment = client(tmp_path); FakeSMTP.error = socket.timeout("unknown outcome")
    with pytest.raises(UncertainSendError): smtp.send("club@example.edu", "ada@example.edu", "Subject", "Body", attachment, "key")
    FakeSMTP.error = None


def test_connection_closure_after_data_without_acknowledgment_is_uncertain(tmp_path: Path):
    smtp, attachment = client(tmp_path); FakeSMTP.error = smtplib.SMTPServerDisconnected("no final acknowledgment")
    with pytest.raises(UncertainSendError):
        smtp.send("club@example.edu", "ada@example.edu", "Subject", "Body", attachment, "key")


def test_temporary_data_rejection_is_safe_transient(tmp_path: Path):
    smtp, attachment = client(tmp_path); FakeSMTP.error = smtplib.SMTPDataError(451, b"try later")
    with pytest.raises(TransientSendError): smtp.send("club@example.edu", "ada@example.edu", "Subject", "Body", attachment, "key")
    FakeSMTP.error = None


def test_gmail_rate_limit_is_classified_for_safe_batch_pause(tmp_path: Path):
    smtp, attachment = client(tmp_path);FakeSMTP.error=smtplib.SMTPDataError(421,b"4.7.0 rate limit exceeded")
    with pytest.raises(TransientSendError) as caught:
        smtp.send("club@example.edu","ada@example.edu","Subject","Body",attachment,"key")
    assert caught.value.rate_limited is True and caught.value.smtp_code==421
    FakeSMTP.error=None


def test_disconnect_before_data_is_transient_and_safe_to_retry(tmp_path: Path, monkeypatch):
    smtp, attachment = client(tmp_path)
    monkeypatch.setattr(FakeSMTP, "rcpt", lambda self, recipient: (_ for _ in ()).throw(socket.timeout("before data")))
    with pytest.raises(TransientSendError, match="before DATA"):
        smtp.send("club@example.edu", "ada@example.edu", "Subject", "Body", attachment, "key")


def test_confirmed_pre_data_disconnect_reconnects_safely(tmp_path: Path):
    attempts = {"rcpt": 0}
    class FlakySMTP(FakeSMTP):
        def rcpt(self, recipient):
            attempts["rcpt"] += 1
            if attempts["rcpt"] == 1:
                raise socket.timeout("confirmed before DATA")
            return super().rcpt(recipient)
    attachment = tmp_path / "certificate.pdf"
    attachment.write_bytes(b"%PDF-test")
    smtp = SMTPClient("smtp.gmail.com", 587, "club@example.edu", "password", "club@example.edu", smtp_factory=FlakySMTP)
    with pytest.raises(TransientSendError):
        smtp.send("club@example.edu", "ada@example.edu", "Subject", "Body", attachment, "key-one")
    assert smtp.send("club@example.edu", "ada@example.edu", "Subject", "Body", attachment, "key-two") == "<key-two@example.edu>"
    assert FakeSMTP.instance_count == 2


def test_diagnostic_logs_never_contain_credentials_or_recipient(tmp_path: Path, caplog):
    smtp, attachment = client(tmp_path)
    caplog.set_level("INFO", logger="certificate.smtp")
    smtp.send("club@example.edu", "private-recipient@example.edu", "Secret subject", "Body", attachment, "key")
    output = caplog.text
    assert "abcdefghijklmnop" not in output
    assert "private-recipient@example.edu" not in output
    assert "Secret subject" not in output
    assert "stage=data" in output and "smtp_event=accepted" in output


def test_sender_spoofing_is_rejected_before_network(tmp_path: Path):
    smtp, attachment = client(tmp_path)
    with pytest.raises(DefiniteSendError): smtp.send("other@example.edu", "ada@example.edu", "Subject", "Body", attachment, "key")


def test_authentication_failure_is_definite_and_does_not_send(tmp_path: Path):
    smtp, attachment = client(tmp_path);FakeSMTP.auth_error=smtplib.SMTPAuthenticationError(535,b"bad credentials")
    with pytest.raises(DefiniteSendError,match="App Password"):
        smtp.send("club@example.edu","ada@example.edu","Subject","Body",attachment,"key")
    assert FakeSMTP.instance.message is None
    FakeSMTP.auth_error=None
