from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from fastapi import HTTPException
import uuid
from app.models.user import User
from app.schemas.users_schema import UserCreate, UserRead
from app.utils.security import hash_password
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
        raise HTTPException(status_code=409, detail="A user with that email already exists.")
    db.refresh(user)
    return user



# finds user by email
def find_user_by_email(db: Session, email_in: str) -> Optional[User]:
    return db.query(User).filter(User.email == email_in).first()

# find user by id
def find_user_by_id(db: Session, id_in: uuid.UUID) -> Optional[User]:
    return db.query(User).filter(User.id == id_in).first()


