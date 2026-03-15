from fastapi import Depends, APIRouter
from app.database.session import get_db
from sqlalchemy.orm import Session
from app.schemas.users_schema import UserCreate, UserRead
from app.services.user_services import user_create
from app.api.dependencies.auth_dependency import get_current_user
from app.models.user import User


user_router = APIRouter(tags=["users"])


@user_router.post("/users/create", response_model=UserRead)
def signup(user: UserCreate, db: Session = Depends(get_db)):
    return user_create(db, user)


@user_router.get("/users/me", response_model=UserRead)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user
