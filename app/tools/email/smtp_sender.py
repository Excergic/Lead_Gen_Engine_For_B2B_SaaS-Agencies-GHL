"""
SMTP email sender — pure stdlib, no extra dependencies.

Supports:
  - STARTTLS on port 587  (Gmail, SendGrid, Mailgun, Brevo, etc.)
  - SSL on port 465       (set use_ssl=True)
  - Plain / local relay   (use_tls=False, use_ssl=False)

Usage:
    config = SmtpConfig(
        host="smtp.gmail.com",
        port=587,
        username="you@gmail.com",
        password="your-app-password",  # NOT your Google account password
        from_email="you@gmail.com",
        from_name="Your Name",
    )
    sender = SmtpEmailSender(config)
    sender.test_connection()    # raises if credentials are wrong
    result = sender.send(to="prospect@example.com", subject="…", body="…")
"""
from __future__ import annotations

import logging
import smtplib
import ssl
from dataclasses import dataclass, field
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class SmtpConfig:
    host: str
    port: int
    username: str
    password: str
    from_email: str
    from_name: str = ""
    reply_to: str | None = None
    use_tls: bool = True   # STARTTLS (port 587 standard)
    use_ssl: bool = False  # Implicit SSL (port 465); takes priority over use_tls


class SmtpSendError(RuntimeError):
    """Raised when an email fails to send."""


class SmtpConnectionError(RuntimeError):
    """Raised when SMTP connection/auth fails."""


class SmtpEmailSender:
    """
    Thin, testable wrapper around smtplib.

    Keeps one logical connection per send (no long-lived connection pool
    needed for outbound prospecting volumes).
    """

    def __init__(self, config: SmtpConfig) -> None:
        self._cfg = config

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def send(
        self,
        *,
        to: str,
        subject: str,
        body: str,
        reply_to: str | None = None,
    ) -> dict[str, Any]:
        """
        Send a single plain-text email.

        Returns a result dict on success.  Raises SmtpSendError on failure.
        """
        msg = self._build_message(to=to, subject=subject, body=body, reply_to=reply_to)
        try:
            with self._connect() as smtp:
                smtp.sendmail(self._cfg.from_email, [to], msg.as_string())
        except smtplib.SMTPException as exc:
            raise SmtpSendError(f"SMTP send failed to {to}: {exc}") from exc
        except OSError as exc:
            raise SmtpSendError(f"Network error sending to {to}: {exc}") from exc

        logger.info(
            "email_sent to=%s subject=%s from=%s",
            to,
            subject,
            self._cfg.from_email,
        )
        return {
            "sent": True,
            "dry_run": False,
            "to": to,
            "from": self._cfg.from_email,
            "subject": subject,
        }

    def test_connection(self) -> dict[str, Any]:
        """
        Verify SMTP credentials without sending anything.

        Returns {"ok": True, "message": "…"} or raises SmtpConnectionError.
        """
        try:
            with self._connect() as smtp:
                status = smtp.noop()  # (250, b'OK')
        except smtplib.SMTPAuthenticationError as exc:
            raise SmtpConnectionError(
                f"SMTP authentication failed for {self._cfg.username}@{self._cfg.host}. "
                "Check USERNAME, PASSWORD (use an app-password for Gmail), and HOST."
            ) from exc
        except (smtplib.SMTPConnectError, smtplib.SMTPException, OSError) as exc:
            raise SmtpConnectionError(
                f"Cannot connect to SMTP server {self._cfg.host}:{self._cfg.port} — {exc}"
            ) from exc

        logger.info(
            "smtp_connection_ok host=%s port=%s user=%s",
            self._cfg.host,
            self._cfg.port,
            self._cfg.username,
        )
        return {
            "ok": True,
            "host": self._cfg.host,
            "port": self._cfg.port,
            "from_email": self._cfg.from_email,
            "message": f"SMTP connection verified ({self._cfg.host}:{self._cfg.port})",
        }

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _connect(self) -> smtplib.SMTP | smtplib.SMTP_SSL:
        cfg = self._cfg
        if cfg.use_ssl:
            ctx = ssl.create_default_context()
            smtp: smtplib.SMTP | smtplib.SMTP_SSL = smtplib.SMTP_SSL(
                cfg.host, cfg.port, context=ctx
            )
        else:
            smtp = smtplib.SMTP(cfg.host, cfg.port)
            if cfg.use_tls:
                smtp.starttls(context=ssl.create_default_context())
        smtp.login(cfg.username, cfg.password)
        return smtp

    def _build_message(
        self,
        *,
        to: str,
        subject: str,
        body: str,
        reply_to: str | None,
    ) -> MIMEMultipart:
        cfg = self._cfg
        from_header = f"{cfg.from_name} <{cfg.from_email}>" if cfg.from_name else cfg.from_email

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = from_header
        msg["To"] = to
        effective_reply_to = reply_to or cfg.reply_to
        if effective_reply_to:
            msg["Reply-To"] = effective_reply_to

        msg.attach(MIMEText(body, "plain", "utf-8"))
        return msg


# ---------------------------------------------------------------------------
# Factory helper — build from Settings
# ---------------------------------------------------------------------------

def smtp_sender_from_settings(settings: Any) -> SmtpEmailSender | None:
    """
    Build an SmtpEmailSender from app Settings.
    Returns None if SMTP is not configured (all SMTP fields optional).
    """
    host = getattr(settings, "smtp_host", None)
    if not host:
        return None

    def _secret(val: Any) -> str:
        return val.get_secret_value() if hasattr(val, "get_secret_value") else str(val)

    cfg = SmtpConfig(
        host=host,
        port=getattr(settings, "smtp_port", 587),
        username=_secret(settings.smtp_username),
        password=_secret(settings.smtp_password),
        from_email=getattr(settings, "email_from_address", ""),
        from_name=getattr(settings, "email_from_name", ""),
        reply_to=getattr(settings, "email_reply_to", None),
        use_tls=getattr(settings, "smtp_use_tls", True),
        use_ssl=getattr(settings, "smtp_use_ssl", False),
    )
    return SmtpEmailSender(cfg)
