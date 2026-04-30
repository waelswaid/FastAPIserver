import logging

import requests
from app.core.config import settings
from app.utils import dev_codes

logger = logging.getLogger(__name__)


def _is_dev_mode() -> bool:
    """In any non-production environment, skip the Mailgun call and log
    codes to the standard logger instead. See spec
    docs/superpowers/specs/2026-04-29-dev-mode-design.md."""
    return settings.ENVIRONMENT != "production"


def _log_dev_email(email_type: str, recipient: str, code: str, link: str) -> None:
    """Audit-style log line for dev-mode emails. Greppable via event=dev_email."""
    logger.info(
        "audit: event=dev_email type=%s recipient=%s code=%s link=%s",
        email_type, recipient, code, link,
    )
    dev_codes.record(email_type, recipient, code, link)


def send_password_reset_email(to_email: str, code: str) -> None:
    base = settings.PASSWORD_RESET_URL or f"{settings.APP_BASE_URL}/api/auth/reset-password"
    reset_link = f"{base}?code={code}"

    if _is_dev_mode():
        _log_dev_email("password_reset", to_email, code, reset_link)
        return

    response = requests.post(
        f"{settings.MAILGUN_API_URL}/{settings.MAILGUN_DOMAIN}/messages",
        auth=("api", settings.MAILGUN_API_KEY),
        data={
            "from": settings.MAILGUN_FROM_EMAIL,
            "to": to_email,
            "subject": "Reset your password",
            "text": (
                f"You requested a password reset.\n\n"
                f"Click the link below to set a new password. "
                f"This link expires in {settings.PASSWORD_RESET_EXPIRE_MINUTES} minutes.\n\n"
                f"{reset_link}\n\n"
                f"If you did not request this, you can safely ignore this email."
            ),
        },
    )
    response.raise_for_status()
    logger.info("Password reset email sent to=%s", to_email)


def send_verification_email(to_email: str, code: str) -> None:
    base = settings.EMAIL_VERIFY_URL or f"{settings.APP_BASE_URL}/api/auth/verify-email"
    verification_link = f"{base}?code={code}"

    if _is_dev_mode():
        _log_dev_email("email_verification", to_email, code, verification_link)
        return

    response = requests.post(
        f"{settings.MAILGUN_API_URL}/{settings.MAILGUN_DOMAIN}/messages",
        auth=("api", settings.MAILGUN_API_KEY),
        data={
            "from": settings.MAILGUN_FROM_EMAIL,
            "to": to_email,
            "subject": "Verify your email address",
            "text": (
                f"Thanks for signing up!\n\n"
                f"Click the link below to verify your email address. "
                f"This link expires in {settings.EMAIL_VERIFICATION_EXPIRE_MINUTES // 60} hours.\n\n"
                f"{verification_link}\n\n"
                f"If you did not create an account, you can safely ignore this email."
            ),
        },
    )
    response.raise_for_status()
    logger.info("Verification email sent to=%s", to_email)


def send_invite_email(to_email: str, code: str) -> None:
    base = settings.INVITE_URL or f"{settings.APP_BASE_URL}/api/auth/accept-invite"
    invite_link = f"{base}?code={code}"

    if _is_dev_mode():
        _log_dev_email("invite", to_email, code, invite_link)
        return

    response = requests.post(
        f"{settings.MAILGUN_API_URL}/{settings.MAILGUN_DOMAIN}/messages",
        auth=("api", settings.MAILGUN_API_KEY),
        data={
            "from": settings.MAILGUN_FROM_EMAIL,
            "to": to_email,
            "subject": "You've been invited",
            "text": (
                f"You have been invited to create an account.\n\n"
                f"Click the link below to set up your account. "
                f"This link expires in {settings.INVITE_EXPIRE_MINUTES // 60} hours.\n\n"
                f"{invite_link}\n\n"
                f"If you were not expecting this invitation, you can safely ignore this email."
            ),
        },
    )
    response.raise_for_status()
    logger.info("Invite email sent to=%s", to_email)
