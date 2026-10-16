import logging
from dataclasses import dataclass
from email.message import EmailMessage as MimeMessage
from functools import lru_cache
from typing import Protocol

import aiosmtplib

from app.core.config import settings
from app.core.logging import log_fields

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class EmailMessage:
    to: str
    subject: str
    body: str
    template: str  # logged instead of the address


class EmailSender(Protocol):
    async def send(self, message: EmailMessage) -> None: ...


class SmtpEmailSender:
    def __init__(self, host: str, port: int, sender: str, starttls: bool) -> None:
        self._host = host
        self._port = port
        self._sender = sender
        self._starttls = starttls

    async def send(self, message: EmailMessage) -> None:
        mime = MimeMessage()
        mime["From"] = self._sender
        mime["To"] = message.to
        mime["Subject"] = message.subject
        mime.set_content(message.body)
        await aiosmtplib.send(
            mime, hostname=self._host, port=self._port, start_tls=self._starttls, timeout=10
        )
        logger.info("email.sent", extra=log_fields(template=message.template))


@lru_cache(maxsize=1)
def get_email_sender() -> EmailSender:
    return SmtpEmailSender(
        settings.smtp_host, settings.smtp_port, settings.mail_from, settings.smtp_starttls
    )


async def send_safely(sender: EmailSender, message: EmailMessage) -> None:
    """A failed email must not fail the request; the user can ask for it again."""
    try:
        await sender.send(message)
    except (aiosmtplib.SMTPException, OSError):
        logger.exception("email.failed", extra=log_fields(template=message.template))


def verification_email(to: str, token: str) -> EmailMessage:
    link = f"{settings.app_base_url}/verify-email?token={token}"
    return EmailMessage(
        to=to,
        subject="Confirm your email address",
        body=f"Confirm your email address to finish creating your account:\n\n{link}\n\n"
        "The link expires in 24 hours. If you didn't sign up, ignore this email.",
        template="verify_email",
    )


def account_exists_email(to: str) -> EmailMessage:
    return EmailMessage(
        to=to,
        subject="You already have an account",
        body="Someone tried to create an account with this email address, "
        "but you already have one.\n\n"
        f"Sign in: {settings.app_base_url}/sign-in\n"
        f"Forgot your password? {settings.app_base_url}/forgot-password\n\n"
        "If this wasn't you, you can ignore this email.",
        template="account_exists",
    )


def reset_password_email(to: str, token: str) -> EmailMessage:
    link = f"{settings.app_base_url}/reset-password?token={token}"
    return EmailMessage(
        to=to,
        subject="Reset your password",
        body=f"Use this link to choose a new password:\n\n{link}\n\n"
        "The link expires in 30 minutes and works once. "
        "If you didn't ask for this, ignore this email; your password stays the same.",
        template="reset_password",
    )
