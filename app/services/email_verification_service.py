import logging
import uuid
from datetime import datetime, timezone, timedelta

from fastapi import HTTPException
from sqlalchemy.orm import Session
import requests as http_requests

from app.repositories.user_repository import find_user_by_email, find_user_by_id_for_update, verify_user
from app.repositories.pending_action_repository import (
    upsert_action, find_user_by_action_code_for_update, delete_action,
)
from app.repositories.token_blacklist_repository import is_blacklisted, add_to_blacklist
from app.exceptions import TokenError
from app.models.user import User
from app.services.auth_services import jwt_gen
from app.utils.email import send_verification_email

logger = logging.getLogger(__name__)

ACTION_EMAIL_VERIFICATION_CODE = "email_verification_code"


def send_verification_email_for_user(db: Session, user: User) -> None:
    code = str(uuid.uuid4())
    expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=jwt_gen.config.email_verification_token_expiry_minutes
    )
    send_verification_email(user.email, code)
    upsert_action(db, user.id, ACTION_EMAIL_VERIFICATION_CODE, code, expires_at)


def resend_verification_email(db: Session, email: str) -> None:
    user = find_user_by_email(db, email)
    if user is None or user.is_verified:
        return

    try:
        send_verification_email_for_user(db, user)
    except http_requests.RequestException as exc:
        logger.error("Failed to send verification email: %s", exc)
        raise HTTPException(status_code=503, detail="Unable to send email. Please try again later.")


async def verify_email_token(db: Session, token: str) -> None:
    try:
        payload = jwt_gen.decode_email_verification_token(token)
    except TokenError:
        raise HTTPException(status_code=400, detail="Invalid or expired verification token")

    jti = payload.get("jti")
    if jti is None or await is_blacklisted(jti):
        raise HTTPException(status_code=400, detail="Verification link has already been used")

    sub = payload.get("sub")
    if sub is None:
        raise HTTPException(status_code=400, detail="Invalid verification token")

    try:
        user_id = uuid.UUID(sub)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid verification token")

    user = find_user_by_id_for_update(db, user_id)
    if user is None:
        raise HTTPException(status_code=400, detail="User not found")

    if user.is_verified:
        raise HTTPException(status_code=400, detail="Invalid or expired verification link")

    exp = payload.get("exp")
    expires_at = datetime.fromtimestamp(exp, tz=timezone.utc)
    await add_to_blacklist(jti, expires_at)
    verify_user(db, user, commit=False)
    db.commit()
    logger.info("audit: event=email_verified user_id=%s email=%s", user_id, user.email)


def verify_email_code(db: Session, code: str) -> None:
    result = find_user_by_action_code_for_update(db, code, ACTION_EMAIL_VERIFICATION_CODE)
    if result is None:
        raise HTTPException(status_code=400, detail="Invalid or expired verification link")

    action, user = result

    if user.is_verified:
        raise HTTPException(status_code=400, detail="Invalid or expired verification link")

    if action.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Invalid or expired verification link")

    delete_action(db, action, commit=False)
    verify_user(db, user, commit=False)
    db.commit()
    logger.info("audit: event=email_verified user_id=%s email=%s", user.id, user.email)
