from app.schemas.users_schema import UserCreate
from sqlalchemy.orm import Session
from app.repositories import user_repository
from app.services.auth_services import send_verification_email_for_user
from app.exceptions import DuplicateEmailError
from fastapi import HTTPException
import requests


def user_create(db: Session, user: UserCreate):
    try:
        new_user = user_repository.create_user(db=db, user_in=user)
    except DuplicateEmailError as e:
        raise HTTPException(status_code=409, detail=str(e))
    try:
        send_verification_email_for_user(db, new_user)
    except requests.RequestException:
        raise HTTPException(
            status_code=500,
            detail="Account created but verification email could not be sent. Please contact support.",
        )
    return new_user

