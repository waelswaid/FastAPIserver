import logging

import requests
from app.core.config import settings

logger = logging.getLogger(__name__)


def send_password_reset_email(to_email: str, code: str) -> None:
    base = settings.PASSWORD_RESET_URL or f"{settings.APP_BASE_URL}/api/auth/reset-password"
    reset_link = f"{base}?code={code}"

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
