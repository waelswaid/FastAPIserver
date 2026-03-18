from sqlalchemy.orm import Session
from datetime import datetime, timezone
from typing import Optional, Sequence
import uuid

from app.models.pending_action import PendingAction
from app.models.user import User


def upsert_action(
    db: Session,
    user_id: uuid.UUID,
    action_type: str,
    code: str,
    expires_at: datetime,
    commit: bool = True,
) -> PendingAction:
    existing = (
        db.query(PendingAction)
        .filter(PendingAction.user_id == user_id, PendingAction.action_type == action_type)
        .with_for_update()
        .first()
    )
    if existing:
        existing.code = code
        existing.expires_at = expires_at
    else:
        existing = PendingAction(
            user_id=user_id,
            action_type=action_type,
            code=code,
            expires_at=expires_at,
        )
        db.add(existing)
    if commit:
        db.commit()
        db.refresh(existing)
    else:
        db.flush()
    return existing


def find_action_by_user_and_type(
    db: Session, user_id: uuid.UUID, action_type: str
) -> Optional[PendingAction]:
    return (
        db.query(PendingAction)
        .filter(PendingAction.user_id == user_id, PendingAction.action_type == action_type)
        .first()
    )


def find_user_by_action_code_for_update(
    db: Session, code: str, action_type: str
) -> Optional[tuple[PendingAction, User]]:
    result = (
        db.query(PendingAction, User)
        .join(User, PendingAction.user_id == User.id)
        .filter(PendingAction.code == code, PendingAction.action_type == action_type)
        .with_for_update()
        .first()
    )
    return result


def delete_action(db: Session, action: PendingAction, commit: bool = True) -> None:
    db.delete(action)
    if commit:
        db.commit()
    else:
        db.flush()


def delete_actions_for_user(
    db: Session,
    user_id: uuid.UUID,
    action_types: Sequence[str],
    commit: bool = True,
) -> None:
    db.query(PendingAction).filter(
        PendingAction.user_id == user_id,
        PendingAction.action_type.in_(action_types),
    ).delete(synchronize_session="fetch")
    if commit:
        db.commit()
    else:
        db.flush()


def cleanup_expired_actions(db: Session) -> None:
    db.query(PendingAction).filter(
        PendingAction.expires_at < datetime.now(timezone.utc)
    ).delete(synchronize_session="fetch")
    db.commit()
