from app.schemas.users_schema import UserCreate
from sqlalchemy.orm import Session
from app.repositories import user_repository
from app.repositories.user_repository import find_user_by_id_for_update, delete_user
from app.services.auth_services import jwt_gen
from app.services.email_verification_service import send_verification_email_for_user
from app.services._token_helpers import blacklist_jwt
from app.utils.security.password_hash import verify_password
from app.exceptions import TokenError
from app.models.user import User
from fastapi import HTTPException
import requests
import logging

logger = logging.getLogger(__name__)


def user_create(db: Session, user: UserCreate):
    new_user = user_repository.create_user(db=db, user_in=user)
    logger.info("audit: event=registration user_id=%s email=%s", new_user.id, new_user.email)
    try:
        send_verification_email_for_user(db, new_user)
    except requests.RequestException:
        raise HTTPException(
            status_code=500,
            detail="Account created but verification email could not be sent. Please contact support.",
        )
    return new_user


async def delete_own_account(db: Session, user: User, password: str, access_token: str, refresh_token: str | None = None) -> None:
    if user.password_hash == "!oauth":
        raise HTTPException(status_code=400, detail="OAuth accounts cannot be deleted with a password. Contact an administrator.")
    if not verify_password(password, user.password_hash):
        raise HTTPException(status_code=400, detail="Incorrect password")

    locked_user = find_user_by_id_for_update(db, user.id)
    if locked_user is None:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    try:
        payload = jwt_gen.decode_access_token(access_token)
        jti = payload.get("jti")
        exp = payload.get("exp")
        if jti and exp:
            await blacklist_jwt(payload)
    except TokenError:
        pass

    if refresh_token is not None:
        try:
            rt_payload = jwt_gen.decode_refresh_token(refresh_token)
            rt_jti = rt_payload.get("jti")
            rt_exp = rt_payload.get("exp")
            if rt_jti and rt_exp:
                await blacklist_jwt(rt_payload)
        except TokenError:
            pass

    user_id = locked_user.id
    delete_user(db, locked_user)
    logger.info("audit: event=account_deleted user_id=%s", user_id)

