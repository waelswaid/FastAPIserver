from fastapi import Depends, APIRouter
from app.database.session import get_db
from sqlalchemy.orm import Session
from app.schemas.users_schema import UserCreate, UserRead, UserUpdate
from app.services.user_services import user_create
from app.api.dependencies.auth_dependency import get_current_user
from app.api.dependencies.rate_limiter import registration_limiter
from app.repositories.user_repository import update_user_profile
from app.models.user import User
import logging

logger = logging.getLogger(__name__)


user_router = APIRouter(tags=["users"])


@user_router.post("/users/create", response_model=UserRead, dependencies=[Depends(registration_limiter)])
def signup(user: UserCreate, db: Session = Depends(get_db)):
    return user_create(db, user)


@user_router.get("/users/me", response_model=UserRead)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@user_router.patch("/users/me", response_model=UserRead)
def update_me(body: UserUpdate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    update_user_profile(db, current_user, first_name=body.first_name, last_name=body.last_name)
    logger.info("audit: event=profile_updated user_id=%s", current_user.id)
    db.refresh(current_user)
    return current_user
