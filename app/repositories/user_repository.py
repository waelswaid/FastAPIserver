from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from datetime import datetime, timezone
import uuid
from app.models.user import User
from app.schemas.users_schema import UserCreate, UserRead
from app.utils.security import hash_password
from app.exceptions import DuplicateEmailError
from typing import Optional

# creates a new user
def create_user(db: Session, user_in: UserCreate) -> User:
    user = User(
        name=user_in.name,
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



# finds user by email
def find_user_by_email(db: Session, email_in: str) -> Optional[User]:
    return db.query(User).filter(User.email == email_in).first()

# find user by id
def find_user_by_id(db: Session, id_in: uuid.UUID) -> Optional[User]:
    return db.query(User).filter(User.id == id_in).first()

# find user by id with row-level lock (SELECT ... FOR UPDATE)
def find_user_by_id_for_update(db: Session, id_in: uuid.UUID) -> Optional[User]:
    return db.query(User).filter(User.id == id_in).with_for_update().first()


# update a user's password hash, record the time of change, and clear any pending reset token
def update_password(db: Session, user: User, new_hash: str) -> None:
    user.password_hash = new_hash
    user.password_changed_at = datetime.now(timezone.utc)
    user.password_reset_jti = None
    user.password_reset_jti_expires_at = None
    db.commit()


# mark a user's email as verified and clear the verification code
def verify_user(db: Session, user: User) -> None:
    user.is_verified = True
    user.email_verification_code = None
    user.email_verification_code_expires_at = None
    db.commit()


# store the JTI and expiration of the most recently issued password reset token
def set_password_reset_jti(db: Session, user: User, jti: str, expires_at: datetime) -> None:
    user.password_reset_jti = jti
    user.password_reset_jti_expires_at = expires_at
    db.commit()


# store an opaque email verification code on the user
def set_email_verification_code(db: Session, user: User, code: str, expires_at: datetime) -> None:
    user.email_verification_code = code
    user.email_verification_code_expires_at = expires_at
    db.commit()


# store an opaque password reset code on the user
def set_password_reset_code(db: Session, user: User, code: str, expires_at: datetime) -> None:
    user.password_reset_code = code
    user.password_reset_code_expires_at = expires_at
    db.commit()


# find user by email verification code with row-level lock
def find_user_by_verification_code_for_update(db: Session, code: str) -> Optional[User]:
    return db.query(User).filter(User.email_verification_code == code).with_for_update().first()


# find user by password reset code with row-level lock
def find_user_by_reset_code_for_update(db: Session, code: str) -> Optional[User]:
    return db.query(User).filter(User.password_reset_code == code).with_for_update().first()


# update a user's password hash via reset code, clear reset state
def update_password_via_code(db: Session, user: User, new_hash: str) -> None:
    user.password_hash = new_hash
    user.password_changed_at = datetime.now(timezone.utc)
    user.password_reset_jti = None
    user.password_reset_jti_expires_at = None
    user.password_reset_code = None
    user.password_reset_code_expires_at = None
    db.commit()



