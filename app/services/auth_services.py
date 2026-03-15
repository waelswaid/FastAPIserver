from app.repositories.user_repository import find_user_by_email, find_user_by_id
from app.repositories.token_blacklist_repository import add_to_blacklist
from app.utils.security.password_hash import verify_password
from app.utils.tokens import JWTConfig, JWTUtility
from app.core.config import settings
from app.schemas.token_response import TokenResponse
from app.schemas.login_request import LoginRequest
from fastapi import HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timezone
import uuid


jwt_config = JWTConfig(

secret_key = settings.JWT_SECRET_KEY,
algorithm = settings.JWT_ALGORITHM,
access_token_expiry_minutes = settings.ACCESS_TOKEN_EXPIRE_MINUTES

)

jwt_gen = JWTUtility(jwt_config)


def user_login(db: Session, login_data: LoginRequest) -> tuple[str, str]:
    user = find_user_by_email(db, login_data.email)
    if not user or not verify_password(login_data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid Credentials")

    access_token = jwt_gen.create_access_token(str(user.id))
    refresh_token = jwt_gen.create_refresh_token(str(user.id))
    return access_token, refresh_token


def refresh_access_token(db: Session, refresh_token: str) -> TokenResponse:
    try:
        payload = jwt_gen.decode_refresh_token(refresh_token)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    sub = payload.get("sub")
    if sub is None:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    try:
        user_id = uuid.UUID(sub)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    user = find_user_by_id(db, user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    access_token = jwt_gen.create_access_token(str(user.id))
    return TokenResponse(access_token=access_token, token_type="bearer")


def logout(db: Session, token: str) -> None:
    try:
        payload = jwt_gen.decode_access_token(token)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid token")

    jti = payload.get("jti")
    exp = payload.get("exp")
    if jti is None or exp is None:
        raise HTTPException(status_code=401, detail="Invalid token")

    expires_at = datetime.fromtimestamp(exp, tz=timezone.utc)
    add_to_blacklist(db, jti, expires_at)

        
    