from app.repositories.user_repository import (
    find_user_by_email, find_user_by_id,
)
from app.exceptions import TokenError
from app.repositories.token_blacklist_repository import is_blacklisted  # async
from app.utils.security.password_hash import verify_password, hash_password
from app.utils.tokens import JWTConfig, JWTUtility
from app.core.config import settings
from app.schemas.token_response import TokenResponse
from app.schemas.login_request import LoginRequest
from app.services._token_helpers import blacklist_jwt
from fastapi import HTTPException
from sqlalchemy.orm import Session

from datetime import datetime, timezone
import uuid
import logging

logger = logging.getLogger(__name__)

jwt_config = JWTConfig(
    private_key=settings.JWT_PRIVATE_KEY,
    public_key=settings.JWT_PUBLIC_KEY,
    algorithm=settings.JWT_ALGORITHM,
    access_token_expiry_minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES,
    password_reset_token_expiry_minutes=settings.PASSWORD_RESET_EXPIRE_MINUTES,
    email_verification_token_expiry_minutes=settings.EMAIL_VERIFICATION_EXPIRE_MINUTES,
)

jwt_gen = JWTUtility(jwt_config)

DUMMY_HASH = hash_password("dummy-password-for-timing")


def user_login(db: Session, login_data: LoginRequest) -> tuple[str, str]:
    user = find_user_by_email(db, login_data.email) # returns User object
    if not user: # prevents timing attacks
        verify_password(login_data.password, DUMMY_HASH)
        logger.warning("audit: event=login_failed email=%s reason=invalid_credentials", login_data.email)
        raise HTTPException(status_code=401, detail="Invalid Credentials")
    # user exists but password is incorrect
    if not verify_password(login_data.password, user.password_hash):
        logger.warning("audit: event=login_failed email=%s reason=invalid_credentials", login_data.email)
        raise HTTPException(status_code=401, detail="Invalid Credentials")

    if user.is_disabled:
        logger.warning("audit: event=login_failed_disabled email=%s reason=account_disabled", login_data.email)
        raise HTTPException(status_code=403, detail="Your account has been disabled. Contact an administrator.")

    if not user.is_verified:
        logger.warning("audit: event=login_failed_unverified email=%s reason=email_not_verified", login_data.email)
        raise HTTPException(status_code=403, detail="Please verify your email before logging in.")
    # user is ok to login
    claims = {"role": user.role, "email": user.email}
    access_token = jwt_gen.create_access_token(str(user.id), additional_claims=claims)
    refresh_token = jwt_gen.create_refresh_token(str(user.id), additional_claims=claims)
    logger.info("audit: event=login_success user_id=%s email=%s", user.id, user.email)
    return access_token, refresh_token


async def refresh_access_token(db: Session, refresh_token: str) -> tuple[str, str]:
    payload = jwt_gen.decode_refresh_token(refresh_token)
    # this is user_id but in string format
    sub = payload.get("sub")
    if sub is None:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    try:
        # user_id is stored as uuid in the db, so we cast it from string --> uuid
        user_id = uuid.UUID(sub)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    user = find_user_by_id(db, user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    # token's uuid (jti = JWT ID)
    jti = payload.get("jti")
    if jti is None or await is_blacklisted(jti):
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")
    # issued at
    iat = payload.get("iat")
    # invalidates all tokens that were issued before the user changed their password
    if iat is not None and user.password_changed_at is not None:
        if datetime.fromtimestamp(iat, tz=timezone.utc) < user.password_changed_at:
            raise HTTPException(status_code=401, detail="Invalid or expired refresh token")
    # invalidates all tokens issued before user changed role
    if iat is not None and user.role_changed_at is not None:
        if datetime.fromtimestamp(iat, tz=timezone.utc) < user.role_changed_at:
            raise HTTPException(status_code=401, detail="Invalid or expired refresh token")
    # blacklists the current token
    await blacklist_jwt(payload)

    claims = {"role": user.role, "email": user.email}
    access_token = jwt_gen.create_access_token(str(user.id), additional_claims=claims)
    new_refresh_token = jwt_gen.create_refresh_token(str(user.id), additional_claims=claims)
    logger.info("audit: event=token_refresh user_id=%s", user.id)
    return access_token, new_refresh_token

# extracts jti and expiry from access and refresh tokens and sends them to redis for blacklisting
async def logout(token: str, refresh_token: str | None = None) -> None:
    payload = jwt_gen.decode_access_token(token)

    jti = payload.get("jti")
    exp = payload.get("exp")
    if jti is None or exp is None:
        raise HTTPException(status_code=401, detail="Invalid token")

    await blacklist_jwt(payload)
    logger.info("audit: event=logout user_id=%s", payload.get("sub"))

    if refresh_token is not None:
        try:
            rt_payload = jwt_gen.decode_refresh_token(refresh_token)
            rt_jti = rt_payload.get("jti")
            rt_exp = rt_payload.get("exp")
            if rt_jti is not None and rt_exp is not None:
                await blacklist_jwt(rt_payload)
        except TokenError:
            pass
