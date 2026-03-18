from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from datetime import datetime, timezone
import uuid
from app.models.user import User
from app.schemas.users_schema import UserCreate, UserRead
from app.utils.security import hash_password
from app.exceptions import DuplicateEmailError
from typing import Optional, Sequence


def create_user(db: Session, user_in: UserCreate) -> User:
    user = User(
        first_name=user_in.first_name,
        last_name=user_in.last_name,
        email=user_in.email,
        password_hash=hash_password(user_in.password),
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise DuplicateEmailError("A user with that email already exists.")
    db.refresh(user)
    return user


def find_user_by_email(db: Session, email_in: str) -> Optional[User]:
    return db.query(User).filter(User.email == email_in).first()


def find_user_by_id(db: Session, id_in: uuid.UUID) -> Optional[User]:
    return db.query(User).filter(User.id == id_in).first()


def find_user_by_id_for_update(db: Session, id_in: uuid.UUID) -> Optional[User]:
    return db.query(User).filter(User.id == id_in).with_for_update().first()


def update_password(db: Session, user: User, new_hash: str, commit: bool = True) -> None:
    user.password_hash = new_hash
    user.password_changed_at = datetime.now(timezone.utc)
    if commit:
        db.commit()
    else:
        db.flush()


def verify_user(db: Session, user: User, commit: bool = True) -> None:
    user.is_verified = True
    if commit:
        db.commit()
    else:
        db.flush()


def update_user_role(db: Session, user: User, new_role: str) -> None:
    user.role = new_role
    user.role_changed_at = datetime.now(timezone.utc)
    db.commit()


def update_user_profile(db: Session, user: User, first_name: Optional[str] = None, last_name: Optional[str] = None) -> None:
    if first_name is not None:
        user.first_name = first_name
    if last_name is not None:
        user.last_name = last_name
    db.commit()


def list_users(
    db: Session,
    role_filter: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
) -> Sequence[User]:
    query = db.query(User)
    if role_filter is not None:
        query = query.filter(User.role == role_filter)
    return query.offset(skip).limit(limit).all()
