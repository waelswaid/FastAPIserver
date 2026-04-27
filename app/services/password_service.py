import logging
import uuid
from datetime import datetime, timezone, timedelta

from fastapi import HTTPException
from sqlalchemy.orm import Session
import requests as http_requests

from app.repositories.user_repository import (
    find_user_by_email, find_user_by_id_for_update, update_password,
)
from app.repositories.pending_action_repository import (
    upsert_action, find_action_by_user_and_type,
    find_user_by_action_code_for_update, delete_actions_for_user,
)
from app.repositories.token_blacklist_repository import is_blacklisted, add_to_blacklist
from app.exceptions import TokenError
from app.models.user import User
from app.services.auth_services import jwt_gen
from app.utils.email import send_password_reset_email
from app.utils.security.password_hash import verify_password, hash_password

logger = logging.getLogger(__name__)

ACTION_PASSWORD_RESET_JTI = "password_reset_jti"
ACTION_PASSWORD_RESET_CODE = "password_reset_code"

ALL_RESET_ACTIONS = [ACTION_PASSWORD_RESET_JTI, ACTION_PASSWORD_RESET_CODE]


def upsert_reset_pair(
    db: Session,
    user_id: uuid.UUID,
    jti: str,
    jti_expires_at: datetime,
    code: str,
    code_expires_at: datetime,
) -> None:
    """Upsert the JTI + code pending actions for a password reset.
    Caller is responsible for db.commit()."""
    upsert_action(db, user_id, ACTION_PASSWORD_RESET_JTI, jti, jti_expires_at, commit=False)
    upsert_action(db, user_id, ACTION_PASSWORD_RESET_CODE, code, code_expires_at, commit=False)


async def request_password_reset(db: Session, email: str) -> None:
    user = find_user_by_email(db, email)
    if user is None or not user.is_verified or user.password_hash == "!oauth":
        return

    code = str(uuid.uuid4())
    expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=jwt_gen.config.password_reset_token_expiry_minutes
    )

    reset_token = jwt_gen.create_password_reset_token(str(user.id))
    new_payload = jwt_gen.decode_password_reset_token(reset_token)
    new_jti = new_payload.get("jti")
    new_jti_expires_at = datetime.fromtimestamp(new_payload["exp"], tz=timezone.utc)

    prev_jti_action = find_action_by_user_and_type(db, user.id, ACTION_PASSWORD_RESET_JTI)
    if prev_jti_action is not None:
        await add_to_blacklist(prev_jti_action.code, prev_jti_action.expires_at)

    upsert_reset_pair(db, user.id, new_jti, new_jti_expires_at, code, expires_at)
    db.commit()

    try:
        send_password_reset_email(user.email, code)
    except http_requests.RequestException as exc:
        logger.error("Failed to send password reset email: %s", exc)
        raise HTTPException(status_code=503, detail="Unable to send email. Please try again later.")

    logger.info("audit: event=password_reset_requested user_id=%s email=%s", user.id, user.email)


async def reset_password(db: Session, token: str, new_password: str) -> None:
    try:
        payload = jwt_gen.decode_password_reset_token(token)
    except TokenError:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")

    jti = payload.get("jti")
    if jti is None or await is_blacklisted(jti):
        raise HTTPException(status_code=400, detail="Reset link has already been used")

    sub = payload.get("sub")
    if sub is None:
        raise HTTPException(status_code=400, detail="Invalid reset token")

    try:
        user_id = uuid.UUID(sub)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid reset token")

    user = find_user_by_id_for_update(db, user_id)
    if user is None:
        raise HTTPException(status_code=400, detail="Invalid reset token")

    jti_action = find_action_by_user_and_type(db, user.id, ACTION_PASSWORD_RESET_JTI)
    if jti_action is None or jti_action.code != jti:
        raise HTTPException(status_code=400, detail="Reset link has already been used")

    exp = payload.get("exp")
    expires_at = datetime.fromtimestamp(exp, tz=timezone.utc)
    await add_to_blacklist(jti, expires_at)
    update_password(db, user, hash_password(new_password), commit=False)
    delete_actions_for_user(db, user.id, ALL_RESET_ACTIONS, commit=False)
    db.commit()
    logger.info("audit: event=password_reset user_id=%s email=%s", user_id, user.email)


def reset_password_via_code(db: Session, code: str, new_password: str) -> None:
    result = find_user_by_action_code_for_update(db, code, ACTION_PASSWORD_RESET_CODE)
    if result is None:
        raise HTTPException(status_code=400, detail="Invalid or expired reset link")

    action, user = result

    if action.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Invalid or expired reset link")

    update_password(db, user, hash_password(new_password), commit=False)
    delete_actions_for_user(db, user.id, ALL_RESET_ACTIONS, commit=False)
    db.commit()
    logger.info("audit: event=password_reset user_id=%s email=%s", user.id, user.email)


def validate_reset_code(db: Session, code: str) -> None:
    result = find_user_by_action_code_for_update(db, code, ACTION_PASSWORD_RESET_CODE)
    if result is None:
        raise HTTPException(status_code=400, detail="Invalid or expired reset link")

    action, user = result

    if action.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Invalid or expired reset link")


def change_password(db: Session, user: User, current_password: str, new_password: str) -> None:
    if user.password_hash == "!oauth":
        raise HTTPException(status_code=400, detail="Password change is not available for OAuth accounts. Set a password first.")
    if not verify_password(current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    update_password(db, user, hash_password(new_password), commit=False)
    delete_actions_for_user(db, user.id, ALL_RESET_ACTIONS, commit=False)
    db.commit()
    logger.info("audit: event=password_changed user_id=%s email=%s", user.id, user.email)
