import logging
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.repositories.user_repository import set_invited_user_profile
from app.repositories.pending_action_repository import (
    find_user_by_action_code_for_update, delete_action,
)
from app.utils.security.password_hash import hash_password

logger = logging.getLogger(__name__)

ACTION_INVITE = "invite"


def _get_valid_invite(db: Session, code: str):
    result = find_user_by_action_code_for_update(db, code, ACTION_INVITE)
    if result is None:
        raise HTTPException(status_code=400, detail="Invalid or expired invite code")

    action, user = result

    if action.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Invalid or expired invite code")

    if user.is_verified:
        raise HTTPException(status_code=400, detail="Invite has already been accepted")

    return action, user


def validate_invite_code(db: Session, code: str) -> None:
    _get_valid_invite(db, code)


def accept_invite(db: Session, code: str, first_name: str, last_name: str, password: str) -> None:
    action, user = _get_valid_invite(db, code)
    set_invited_user_profile(db, user, first_name, last_name, hash_password(password), commit=False)
    delete_action(db, action, commit=False)
    db.commit()
    logger.info("audit: event=invite_accepted user_id=%s email=%s", user.id, user.email)
