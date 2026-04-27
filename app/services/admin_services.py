from fastapi import HTTPException
from sqlalchemy.orm import Session
from app.enums import UserRole
from datetime import datetime, timezone, timedelta
from app.repositories.user_repository import find_user_by_id, find_user_by_id_for_update, find_user_by_email, update_user_role, update_user_disabled_status, create_invited_user
from app.repositories.pending_action_repository import upsert_action, find_action_by_user_and_type
from app.repositories.token_blacklist_repository import add_to_blacklist
from app.utils.email import send_password_reset_email, send_invite_email
from app.core.config import settings
from app.services.auth_services import (
    jwt_gen, ACTION_PASSWORD_RESET_JTI, ACTION_PASSWORD_RESET_CODE, ACTION_INVITE,
)
import uuid
import logging
import requests as http_requests

logger = logging.getLogger(__name__)


def change_user_role(db: Session, user_id: uuid.UUID, new_role: str) -> None:
    if new_role not in [r.value for r in UserRole]:
        raise HTTPException(status_code=400, detail=f"Invalid role: {new_role}")

    user = find_user_by_id(db, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    if user.role == new_role:
        raise HTTPException(status_code=400, detail=f"User already has role '{new_role}'")

    old_role = user.role
    update_user_role(db, user, new_role)
    logger.info("audit: event=role_changed user_id=%s old_role=%s new_role=%s", user_id, old_role, new_role)


def disable_user(db: Session, user_id: uuid.UUID, current_admin_id: uuid.UUID) -> None:
    if user_id == current_admin_id:
        raise HTTPException(status_code=400, detail="Cannot disable your own account")

    user = find_user_by_id_for_update(db, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    if user.is_disabled:
        raise HTTPException(status_code=400, detail="User is already disabled")

    user.password_changed_at = datetime.now(timezone.utc)
    update_user_disabled_status(db, user, True)
    logger.info("audit: event=account_disabled user_id=%s", user_id)


def enable_user(db: Session, user_id: uuid.UUID) -> None:
    user = find_user_by_id_for_update(db, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    if not user.is_disabled:
        raise HTTPException(status_code=400, detail="User is not disabled")

    update_user_disabled_status(db, user, False)
    logger.info("audit: event=account_enabled user_id=%s", user_id)


def invite_user(db: Session, email: str) -> None:
    existing = find_user_by_email(db, email)

    if existing is not None:
        # pending invite — resend
        if existing.password_hash == "!invited" and not existing.is_verified:
            user = existing
        else:
            raise HTTPException(status_code=409, detail="A user with that email already exists.")
    else:
        user = create_invited_user(db, email)

    code = str(uuid.uuid4())
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.INVITE_EXPIRE_MINUTES)
    upsert_action(db, user.id, ACTION_INVITE, code, expires_at)

    try:
        send_invite_email(email, code)
    except http_requests.RequestException as exc:
        logger.error("Failed to send invite email: %s", exc)
        raise HTTPException(status_code=503, detail="Unable to send email. Please try again later.")

    logger.info("audit: event=user_invited user_id=%s email=%s", user.id, email)


async def force_password_reset(db: Session, user_id: uuid.UUID) -> None:
    user = find_user_by_id_for_update(db, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

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

    upsert_action(db, user.id, ACTION_PASSWORD_RESET_JTI, new_jti, new_jti_expires_at, commit=False)
    upsert_action(db, user.id, ACTION_PASSWORD_RESET_CODE, code, expires_at, commit=False)
    user.password_changed_at = datetime.now(timezone.utc)
    db.commit()

    try:
        send_password_reset_email(user.email, code)
    except http_requests.RequestException as exc:
        logger.error("Failed to send password reset email: %s", exc)
        raise HTTPException(status_code=503, detail="Unable to send email. Please try again later.")

    logger.info("audit: event=force_password_reset user_id=%s email=%s", user.id, user.email)
