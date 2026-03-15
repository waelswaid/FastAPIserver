from fastapi.security import OAuth2PasswordBearer
from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.models.user import User
import uuid
from app.services.auth_services import jwt_gen
from app.repositories.user_repository import find_user_by_id
from app.repositories.token_blacklist_repository import is_blacklisted


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    credentials_error = HTTPException(status_code=401, detail="Invalid credentials")

    try:
        payload = jwt_gen.decode_access_token(token)
    except ValueError:
        raise credentials_error

    jti = payload.get("jti")
    if jti is None or is_blacklisted(db, jti):
        raise credentials_error

    sub = payload.get("sub")
    if sub is None:
        raise credentials_error

    try:
        user_id = uuid.UUID(sub)
    except ValueError:
        raise credentials_error

    user = find_user_by_id(db, user_id)
    if user is None:
        raise credentials_error

    return user