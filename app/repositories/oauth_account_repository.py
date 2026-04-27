import uuid
from typing import Optional, Sequence

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.exceptions import DuplicateOAuthAccountError
from app.models.oauth_account import OAuthAccount


def find_by_provider_and_provider_user_id(
    db: Session, provider: str, provider_user_id: str
) -> Optional[OAuthAccount]:
    return (
        db.query(OAuthAccount)
        .filter(
            OAuthAccount.provider == provider,
            OAuthAccount.provider_user_id == provider_user_id,
        )
        .first()
    )


def create_oauth_account(
    db: Session,
    user_id: uuid.UUID,
    provider: str,
    provider_user_id: str,
    commit: bool = True,
) -> OAuthAccount:
    account = OAuthAccount(
        user_id=user_id,
        provider=provider,
        provider_user_id=provider_user_id,
    )
    db.add(account)
    try:
        if commit:
            db.commit()
            db.refresh(account)
        else:
            db.flush()
    except IntegrityError:
        db.rollback()
        raise DuplicateOAuthAccountError(
            "This account is already linked to another user."
        )
    return account


def find_by_user_id(db: Session, user_id: uuid.UUID) -> Sequence[OAuthAccount]:
    return db.query(OAuthAccount).filter(OAuthAccount.user_id == user_id).all()
