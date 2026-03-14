from fastapi import Depends, APIRouter
from app.database.session import get_db
from sqlalchemy.orm import Session
from app.schemas.users_schema import UserCreate, UserRead
from app.services.user_services import user_create



user_router = APIRouter(tags = ["users"])


@user_router.post("/users/create", response_model=UserRead)
def signup(user : UserCreate, db : Session = Depends(get_db)):
    return user_create(db, user)
