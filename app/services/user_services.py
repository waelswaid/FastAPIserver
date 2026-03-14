from app.schemas.users_schema import UserCreate
from sqlalchemy.orm import Session
from app.repositories import user_repository



def user_create(db : Session, user : UserCreate):
    new_user = user_repository.create_user(db = db, user_in = user)
    return new_user

