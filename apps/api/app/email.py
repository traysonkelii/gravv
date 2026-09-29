"""Plain-text email through SMTP (Mailpit locally, SES in hosted environments)."""

import asyncio
import smtplib
from email.message import EmailMessage

import structlog

from app.config import get_settings
from app.errors import Problem

log = structlog.get_logger()


def _send_sync(to: str, subject: str, body: str) -> None:
    s = get_settings()
    msg = EmailMessage()
    msg["From"] = s.smtp_from
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)
    with smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=10) as smtp:
        if s.smtp_tls:
            smtp.starttls()
        if s.smtp_user:
            smtp.login(s.smtp_user, s.smtp_password)
        smtp.send_message(msg)


async def send_email(to: str, subject: str, body: str) -> None:
    try:
        await asyncio.to_thread(_send_sync, to, subject, body)
    except OSError as exc:
        log.warning("email_failed", to_domain=to.split("@")[-1], error=str(exc))
        raise Problem(502, "email_failed", "Email could not be sent", "The message could not be delivered. Try again in a moment.") from exc
    log.info("email_sent", subject=subject, to_domain=to.split("@")[-1])
