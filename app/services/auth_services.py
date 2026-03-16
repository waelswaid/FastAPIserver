from app.repositories.user_repository import (
    find_user_by_email, find_user_by_id, find_user_by_id_for_update,
    update_password, update_password_via_code, verify_user,
    set_password_reset_jti, set_email_verification_code, set_password_reset_code,
    find_user_by_verification_code_for_update, find_user_by_reset_code_for_update,
)
from app.repositories.token_blacklist_repository import add_to_blacklist, is_blacklisted
from app.utils.security.password_hash import verify_password, hash_password
from app.utils.tokens import JWTConfig, JWTUtility
from app.utils.email import send_password_reset_email, send_verification_email
from app.core.config import settings
from app.schemas.token_response import TokenResponse
from app.schemas.login_request import LoginRequest
from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from datetime import datetime, timezone, timedelta
import uuid
import logging
import requests as http_requests

logger = logging.getLogger(__name__)


jwt_config = JWTConfig(
    secret_key=settings.JWT_SECRET_KEY,
    algorithm=settings.JWT_ALGORITHM,
    access_token_expiry_minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES,
    password_reset_token_expiry_minutes=settings.PASSWORD_RESET_EXPIRE_MINUTES,
    email_verification_token_expiry_minutes=settings.EMAIL_VERIFICATION_EXPIRE_MINUTES,
)

jwt_gen = JWTUtility(jwt_config)


def user_login(db: Session, login_data: LoginRequest) -> tuple[str, str]:
    user = find_user_by_email(db, login_data.email)
    if not user or not verify_password(login_data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid Credentials")

    if not user.is_verified:
        raise HTTPException(status_code=403, detail="Please verify your email before logging in.")

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

    jti = payload.get("jti")
    if jti is None or is_blacklisted(db, jti):
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    # reject refresh tokens issued before the last password change
    iat = payload.get("iat")
    if iat is not None and user.password_changed_at is not None:
        if datetime.fromtimestamp(iat, tz=timezone.utc) < user.password_changed_at:
            raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    access_token = jwt_gen.create_access_token(str(user.id))
    return TokenResponse(access_token=access_token, token_type="bearer")


def logout(db: Session, token: str, refresh_token: str | None = None) -> None:
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

    if refresh_token is not None:
        try:
            rt_payload = jwt_gen.decode_refresh_token(refresh_token)
            rt_jti = rt_payload.get("jti")
            rt_exp = rt_payload.get("exp")
            if rt_jti is not None and rt_exp is not None:
                rt_expires_at = datetime.fromtimestamp(rt_exp, tz=timezone.utc)
                try:
                    add_to_blacklist(db, rt_jti, rt_expires_at)
                except IntegrityError:
                    db.rollback()
        except ValueError:
            pass  # invalid refresh token — access token was already blacklisted, proceed


def request_password_reset(db: Session, email: str) -> None:
    # always return without error to avoid leaking whether the email exists
    user = find_user_by_email(db, email)
    if user is None or not user.is_verified:
        return

    # generate an opaque code for the email link (never expose the JWT in the URL)
    code = str(uuid.uuid4())
    expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=jwt_gen.config.password_reset_token_expiry_minutes
    )

    # generate the JWT for server-side use (POST endpoint)
    reset_token = jwt_gen.create_password_reset_token(str(user.id))
    new_payload = jwt_gen.decode_password_reset_token(reset_token)
    new_jti = new_payload.get("jti")
    new_jti_expires_at = datetime.fromtimestamp(new_payload["exp"], tz=timezone.utc)

    # attempt email first — only commit state changes if it succeeds
    try:
        send_password_reset_email(user.email, code)
    except http_requests.RequestException as exc:
        logger.error("Failed to send password reset email: %s", exc)
        raise HTTPException(status_code=503, detail="Unable to send email. Please try again later.")

    # blacklist the previous pending reset token if one exists
    if user.password_reset_jti is not None and user.password_reset_jti_expires_at is not None:
        add_to_blacklist(db, user.password_reset_jti, user.password_reset_jti_expires_at)

    set_password_reset_jti(db, user, new_jti, new_jti_expires_at)
    set_password_reset_code(db, user, code, expires_at)


def send_verification_email_for_user(db: Session, user: "User") -> None:
    code = str(uuid.uuid4())
    expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=jwt_gen.config.email_verification_token_expiry_minutes
    )
    send_verification_email(user.email, code)
    set_email_verification_code(db, user, code, expires_at)


def resend_verification_email(db: Session, email: str) -> None:
    # always return without error to avoid leaking whether the email exists
    user = find_user_by_email(db, email)
    if user is None or user.is_verified:
        return

    try:
        send_verification_email_for_user(db, user)
    except http_requests.RequestException as exc:
        logger.error("Failed to send verification email: %s", exc)
        raise HTTPException(status_code=503, detail="Unable to send email. Please try again later.")


def verify_email_token(db: Session, token: str) -> None:
    try:
        payload = jwt_gen.decode_email_verification_token(token)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid or expired verification token")

    jti = payload.get("jti")
    if jti is None or is_blacklisted(db, jti):
        raise HTTPException(status_code=400, detail="Verification link has already been used")

    sub = payload.get("sub")
    if sub is None:
        raise HTTPException(status_code=400, detail="Invalid verification token")

    try:
        user_id = uuid.UUID(sub)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid verification token")

    user = find_user_by_id_for_update(db, user_id)
    if user is None:
        raise HTTPException(status_code=400, detail="User not found")

    if user.is_verified:
        raise HTTPException(status_code=400, detail="Email is already verified")

    exp = payload.get("exp")
    expires_at = datetime.fromtimestamp(exp, tz=timezone.utc)
    add_to_blacklist(db, jti, expires_at, commit=False)
    verify_user(db, user)


def reset_password(db: Session, token: str, new_password: str) -> None:
    try:
        payload = jwt_gen.decode_password_reset_token(token)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")

    jti = payload.get("jti")
    if jti is None or is_blacklisted(db, jti):
        raise HTTPException(status_code=400, detail="Reset link has already been used")

    sub = payload.get("sub")
    if sub is None:
        raise HTTPException(status_code=400, detail="Invalid reset token")

    try:
        user_id = uuid.UUID(sub)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid reset token")

    user = find_user_by_id_for_update(db, user_id)
    if user is None:
        raise HTTPException(status_code=400, detail="Invalid reset token")

    if user.password_reset_jti != jti:
        raise HTTPException(status_code=400, detail="Reset link has already been used")

    exp = payload.get("exp")
    expires_at = datetime.fromtimestamp(exp, tz=timezone.utc)
    add_to_blacklist(db, jti, expires_at, commit=False)
    update_password(db, user, hash_password(new_password))


def verify_email_code(db: Session, code: str) -> None:
    user = find_user_by_verification_code_for_update(db, code)
    if user is None:
        raise HTTPException(status_code=400, detail="Invalid or expired verification link")

    if user.is_verified:
        raise HTTPException(status_code=400, detail="Email is already verified")

    if user.email_verification_code_expires_at is None or user.email_verification_code_expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Verification link has expired")

    verify_user(db, user)


def reset_password_via_code(db: Session, code: str, new_password: str) -> None:
    user = find_user_by_reset_code_for_update(db, code)
    if user is None:
        raise HTTPException(status_code=400, detail="Invalid or expired reset link")

    if user.password_reset_code_expires_at is None or user.password_reset_code_expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Reset link has expired")

    update_password_via_code(db, user, hash_password(new_password))


def validate_reset_code(db: Session, code: str) -> None:
    user = find_user_by_reset_code_for_update(db, code)
    if user is None:
        raise HTTPException(status_code=400, detail="Invalid or expired reset link")

    if user.password_reset_code_expires_at is None or user.password_reset_code_expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Reset link has expired")
