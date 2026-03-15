from app.schemas.users_schema import UserCreate
from sqlalchemy.orm import Session
from app.repositories import user_repository
from app.services.auth_services import send_verification_email_for_user


def user_create(db: Session, user: UserCreate):
    new_user = user_repository.create_user(db=db, user_in=user)
    send_verification_email_for_user(str(new_user.id), new_user.email)
    return new_user

