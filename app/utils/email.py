import requests
from app.core.config import settings


def send_password_reset_email(to_email: str, code: str) -> None:
    reset_link = f"{settings.APP_BASE_URL}/api/auth/reset-password?code={code}"

    response = requests.post(
        f"https://api.mailgun.net/v3/{settings.MAILGUN_DOMAIN}/messages",
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


def send_verification_email(to_email: str, code: str) -> None:
    verification_link = f"{settings.APP_BASE_URL}/api/auth/verify-email?code={code}"

    response = requests.post(
        f"https://api.mailgun.net/v3/{settings.MAILGUN_DOMAIN}/messages",
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
