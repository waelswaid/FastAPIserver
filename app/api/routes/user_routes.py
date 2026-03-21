from fastapi import Depends, APIRouter, Response, Cookie
from app.database.session import get_db
from sqlalchemy.orm import Session
from app.schemas.users_schema import UserCreate, UserRead, UserUpdate, DeleteAccountRequest
from app.services.user_services import user_create, delete_own_account
from app.api.dependencies.auth_dependency import get_current_user, oauth2_scheme
from app.api.dependencies.rate_limiter import registration_limiter, delete_account_limiter
from app.repositories.user_repository import update_user_profile
from app.models.user import User
from typing import Optional
import logging

logger = logging.getLogger(__name__)


user_router = APIRouter(tags=["users"])


@user_router.post("/users/create", response_model=UserRead, dependencies=[Depends(registration_limiter)])
def signup(user: UserCreate, db: Session = Depends(get_db)):
    return user_create(db, user)


@user_router.get("/users/me", response_model=UserRead)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@user_router.delete("/users/me", status_code=204, dependencies=[Depends(delete_account_limiter)])
async def delete_me(
    body: DeleteAccountRequest,
    response: Response,
    current_user: User = Depends(get_current_user),
    token: str = Depends(oauth2_scheme),
    refresh_token: Optional[str] = Cookie(None),
    db: Session = Depends(get_db),
):
    await delete_own_account(db, current_user, body.password, token, refresh_token)
    response.delete_cookie("refresh_token")


@user_router.patch("/users/me", response_model=UserRead)
def update_me(body: UserUpdate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    update_user_profile(db, current_user, first_name=body.first_name, last_name=body.last_name)
    logger.info("audit: event=profile_updated user_id=%s email=%s", current_user.id, current_user.email)
    db.refresh(current_user)
    return current_user
