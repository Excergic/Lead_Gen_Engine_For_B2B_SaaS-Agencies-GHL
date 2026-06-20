"""
Tests for SmtpEmailSender and SendEmailTool.

All network calls are mocked — no real SMTP server needed.

Covers:
  1.  SmtpEmailSender.send  — happy path (STARTTLS)
  2.  SmtpEmailSender.send  — SSL path
  3.  SmtpEmailSender.send  — network error raises SmtpSendError
  4.  SmtpEmailSender.send  — SMTP auth error raises SmtpSendError
  5.  SmtpEmailSender.test_connection — success
  6.  SmtpEmailSender.test_connection — auth failure → SmtpConnectionError
  7.  SmtpEmailSender.test_connection — connect failure → SmtpConnectionError
  8.  SendEmailTool dry-run — does NOT call smtp, returns dry_run=True
  9.  SendEmailTool live send — calls smtp.send, returns sent=True
  10. SendEmailTool live without smtp — raises RuntimeError
  11. SendEmailTool unapproved draft — raises PermissionError
  12. SendEmailTool missing email — raises ValueError
  13. smtp_sender_from_settings — returns None when SMTP_HOST not set
  14. smtp_sender_from_settings — returns SmtpEmailSender when fully configured
  15. From-header includes name when from_name is set
  16. Reply-To header set correctly
"""
from __future__ import annotations

import smtplib
import uuid
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch, call

import pytest

from app.tools.email.smtp_sender import (
    SmtpConfig,
    SmtpConnectionError,
    SmtpEmailSender,
    SmtpSendError,
    smtp_sender_from_settings,
)
from app.tools.personalize.models import OutreachDraft, ProspectSignals, SignalType
from app.tools.personalize.send_email import SendEmailTool


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _config(**overrides) -> SmtpConfig:
    defaults = dict(
        host="smtp.example.com",
        port=587,
        username="user@example.com",
        password="secret",
        from_email="user@example.com",
        from_name="Test Sender",
        use_tls=True,
        use_ssl=False,
    )
    defaults.update(overrides)
    return SmtpConfig(**defaults)


def _approved_draft(email: str = "prospect@example.com") -> OutreachDraft:
    return OutreachDraft(
        id=str(uuid.uuid4()),
        lead_id=str(uuid.uuid4()),
        contact_name="Alice",
        company_name="Acme",
        email=email,
        subject="Quick question",
        body="Hi Alice, I noticed…",
        hook="recent launch",
        signal_used="Product launch",
        signal_type=SignalType.PRODUCT_LAUNCH,
        signals=ProspectSignals(confidence=0.8),
        status="approved",
    )


def _pending_draft() -> OutreachDraft:
    d = _approved_draft()
    d.status = "pending_review"
    return d


# ---------------------------------------------------------------------------
# 1. Send — happy path (STARTTLS)
# ---------------------------------------------------------------------------

def test_send_starttls():
    mock_smtp_inst = MagicMock()
    mock_smtp_inst.__enter__ = lambda s: s
    mock_smtp_inst.__exit__ = MagicMock(return_value=False)

    with patch("smtplib.SMTP", return_value=mock_smtp_inst):
        sender = SmtpEmailSender(_config(use_tls=True, use_ssl=False))
        result = sender.send(to="bob@example.com", subject="Hello", body="World")

    assert result["sent"] is True
    assert result["dry_run"] is False
    assert result["to"] == "bob@example.com"
    mock_smtp_inst.starttls.assert_called_once()
    mock_smtp_inst.login.assert_called_once_with("user@example.com", "secret")
    mock_smtp_inst.sendmail.assert_called_once()


# ---------------------------------------------------------------------------
# 2. Send — SSL path
# ---------------------------------------------------------------------------

def test_send_ssl():
    mock_smtp_inst = MagicMock()
    mock_smtp_inst.__enter__ = lambda s: s
    mock_smtp_inst.__exit__ = MagicMock(return_value=False)

    with patch("smtplib.SMTP_SSL", return_value=mock_smtp_inst):
        sender = SmtpEmailSender(_config(use_ssl=True, use_tls=False, port=465))
        result = sender.send(to="bob@example.com", subject="Hi", body="Body")

    assert result["sent"] is True
    mock_smtp_inst.login.assert_called_once()


# ---------------------------------------------------------------------------
# 3. Send — network error → SmtpSendError
# ---------------------------------------------------------------------------

def test_send_network_error_raises():
    mock_smtp_inst = MagicMock()
    mock_smtp_inst.__enter__ = lambda s: s
    mock_smtp_inst.__exit__ = MagicMock(return_value=False)
    mock_smtp_inst.sendmail.side_effect = OSError("Connection reset")

    with patch("smtplib.SMTP", return_value=mock_smtp_inst):
        sender = SmtpEmailSender(_config())
        with pytest.raises(SmtpSendError, match="Network error"):
            sender.send(to="bob@example.com", subject="Hi", body="Body")


# ---------------------------------------------------------------------------
# 4. Send — SMTP exception → SmtpSendError
# ---------------------------------------------------------------------------

def test_send_smtp_exception_raises():
    mock_smtp_inst = MagicMock()
    mock_smtp_inst.__enter__ = lambda s: s
    mock_smtp_inst.__exit__ = MagicMock(return_value=False)
    mock_smtp_inst.sendmail.side_effect = smtplib.SMTPRecipientsRefused({})

    with patch("smtplib.SMTP", return_value=mock_smtp_inst):
        sender = SmtpEmailSender(_config())
        with pytest.raises(SmtpSendError, match="SMTP send failed"):
            sender.send(to="bad@example.com", subject="Hi", body="Body")


# ---------------------------------------------------------------------------
# 5. test_connection — success
# ---------------------------------------------------------------------------

def test_connection_success():
    mock_smtp_inst = MagicMock()
    mock_smtp_inst.__enter__ = lambda s: s
    mock_smtp_inst.__exit__ = MagicMock(return_value=False)
    mock_smtp_inst.noop.return_value = (250, b"OK")

    with patch("smtplib.SMTP", return_value=mock_smtp_inst):
        sender = SmtpEmailSender(_config())
        result = sender.test_connection()

    assert result["ok"] is True
    assert "smtp.example.com" in result["message"]
    mock_smtp_inst.noop.assert_called_once()


# ---------------------------------------------------------------------------
# 6. test_connection — auth failure → SmtpConnectionError
# ---------------------------------------------------------------------------

def test_connection_auth_failure():
    mock_smtp_inst = MagicMock()
    mock_smtp_inst.__enter__ = lambda s: s
    mock_smtp_inst.__exit__ = MagicMock(return_value=False)
    mock_smtp_inst.login.side_effect = smtplib.SMTPAuthenticationError(535, b"Auth failed")

    with patch("smtplib.SMTP", return_value=mock_smtp_inst):
        sender = SmtpEmailSender(_config())
        with pytest.raises(SmtpConnectionError, match="authentication failed"):
            sender.test_connection()


# ---------------------------------------------------------------------------
# 7. test_connection — connect failure → SmtpConnectionError
# ---------------------------------------------------------------------------

def test_connection_connect_failure():
    with patch("smtplib.SMTP", side_effect=smtplib.SMTPConnectError(111, b"Refused")):
        sender = SmtpEmailSender(_config())
        with pytest.raises(SmtpConnectionError, match="Cannot connect"):
            sender.test_connection()


# ---------------------------------------------------------------------------
# 8. SendEmailTool — dry-run does NOT send
# ---------------------------------------------------------------------------

def test_send_email_tool_dry_run():
    smtp = MagicMock()
    tool = SendEmailTool(dry_run=True, smtp=smtp)
    draft = _approved_draft()

    result = tool.run(draft=draft)

    assert result["sent"] is False
    assert result["dry_run"] is True
    smtp.send.assert_not_called()


# ---------------------------------------------------------------------------
# 9. SendEmailTool — live send calls smtp.send
# ---------------------------------------------------------------------------

def test_send_email_tool_live_send():
    smtp = MagicMock()
    smtp.send.return_value = {
        "sent": True,
        "dry_run": False,
        "to": "prospect@example.com",
        "from": "user@example.com",
        "subject": "Quick question",
    }
    tool = SendEmailTool(dry_run=False, smtp=smtp)
    draft = _approved_draft()

    result = tool.run(draft=draft)

    assert result["sent"] is True
    assert result["draft_id"] == draft.id
    smtp.send.assert_called_once_with(
        to=draft.email,
        subject=draft.subject,
        body=draft.body,
    )


# ---------------------------------------------------------------------------
# 10. SendEmailTool — live mode but no smtp → RuntimeError
# ---------------------------------------------------------------------------

def test_send_email_tool_live_no_smtp():
    tool = SendEmailTool(dry_run=False, smtp=None)
    draft = _approved_draft()
    with pytest.raises(RuntimeError, match="SMTP is not configured"):
        tool.run(draft=draft)


# ---------------------------------------------------------------------------
# 11. SendEmailTool — unapproved draft → PermissionError
# ---------------------------------------------------------------------------

def test_send_email_tool_unapproved_raises():
    tool = SendEmailTool(dry_run=False, smtp=MagicMock())
    with pytest.raises(PermissionError, match="HITL gate"):
        tool.run(draft=_pending_draft())


# ---------------------------------------------------------------------------
# 12. SendEmailTool — approved but no email → ValueError
# ---------------------------------------------------------------------------

def test_send_email_tool_no_email_raises():
    tool = SendEmailTool(dry_run=False, smtp=MagicMock())
    draft = _approved_draft(email="")
    draft.email = None  # no email address
    with pytest.raises(ValueError, match="No email"):
        tool.run(draft=draft)


# ---------------------------------------------------------------------------
# 13. smtp_sender_from_settings — None when SMTP_HOST not set
# ---------------------------------------------------------------------------

def test_smtp_sender_from_settings_none():
    settings = MagicMock()
    settings.smtp_host = None
    result = smtp_sender_from_settings(settings)
    assert result is None


# ---------------------------------------------------------------------------
# 14. smtp_sender_from_settings — builds sender when fully configured
# ---------------------------------------------------------------------------

def test_smtp_sender_from_settings_full():
    settings = MagicMock()
    settings.smtp_host = "smtp.gmail.com"
    settings.smtp_port = 587
    settings.smtp_username = MagicMock()
    settings.smtp_username.get_secret_value.return_value = "you@gmail.com"
    settings.smtp_password = MagicMock()
    settings.smtp_password.get_secret_value.return_value = "app-password"
    settings.email_from_address = "you@gmail.com"
    settings.email_from_name = "You"
    settings.email_reply_to = None
    settings.smtp_use_tls = True
    settings.smtp_use_ssl = False

    result = smtp_sender_from_settings(settings)
    assert isinstance(result, SmtpEmailSender)
    assert result._cfg.host == "smtp.gmail.com"
    assert result._cfg.username == "you@gmail.com"
    assert result._cfg.from_name == "You"


# ---------------------------------------------------------------------------
# 15. From-header includes name
# ---------------------------------------------------------------------------

def test_from_header_with_name():
    mock_smtp_inst = MagicMock()
    mock_smtp_inst.__enter__ = lambda s: s
    mock_smtp_inst.__exit__ = MagicMock(return_value=False)

    with patch("smtplib.SMTP", return_value=mock_smtp_inst):
        sender = SmtpEmailSender(_config(from_name="Alice Smith", from_email="alice@example.com"))
        sender.send(to="bob@example.com", subject="Hi", body="Hello")

    raw_msg = mock_smtp_inst.sendmail.call_args[0][2]
    assert "Alice Smith <alice@example.com>" in raw_msg


# ---------------------------------------------------------------------------
# 16. Reply-To header
# ---------------------------------------------------------------------------

def test_reply_to_header():
    mock_smtp_inst = MagicMock()
    mock_smtp_inst.__enter__ = lambda s: s
    mock_smtp_inst.__exit__ = MagicMock(return_value=False)

    with patch("smtplib.SMTP", return_value=mock_smtp_inst):
        sender = SmtpEmailSender(_config(reply_to="replies@example.com"))
        sender.send(to="bob@example.com", subject="Hi", body="Hello")

    raw_msg = mock_smtp_inst.sendmail.call_args[0][2]
    assert "replies@example.com" in raw_msg
