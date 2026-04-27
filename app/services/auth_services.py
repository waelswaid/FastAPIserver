from app.repositories.user_repository import (
    find_user_by_email, find_user_by_id, find_user_by_id_for_update,
    update_password, verify_user, set_invited_user_profile,
)
from app.exceptions import TokenError
from app.repositories.pending_action_repository import (
    upsert_action, find_action_by_user_and_type,
    find_user_by_action_code_for_update, delete_action,
    delete_actions_for_user,
)
from app.repositories.token_blacklist_repository import add_to_blacklist, is_blacklisted  # async
from app.utils.security.password_hash import verify_password, hash_password
from app.utils.tokens import JWTConfig, JWTUtility
from app.utils.email import send_password_reset_email, send_verification_email
from app.core.config import settings
from app.schemas.token_response import TokenResponse
from app.schemas.login_request import LoginRequest
from app.models.user import User
from fastapi import HTTPException
from sqlalchemy.orm import Session

from datetime import datetime, timezone, timedelta
import uuid
import logging
import requests as http_requests

logger = logging.getLogger(__name__)

ACTION_PASSWORD_RESET_JTI = "password_reset_jti"
ACTION_EMAIL_VERIFICATION_CODE = "email_verification_code"
ACTION_PASSWORD_RESET_CODE = "password_reset_code"

ALL_RESET_ACTIONS = [ACTION_PASSWORD_RESET_JTI, ACTION_PASSWORD_RESET_CODE]

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
    try:
        payload = jwt_gen.decode_refresh_token(refresh_token)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")
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
    await add_to_blacklist(jti, datetime.fromtimestamp(payload["exp"], tz=timezone.utc))

    claims = {"role": user.role, "email": user.email}
    access_token = jwt_gen.create_access_token(str(user.id), additional_claims=claims)
    new_refresh_token = jwt_gen.create_refresh_token(str(user.id), additional_claims=claims)
    logger.info("audit: event=token_refresh user_id=%s", user.id)
    return access_token, new_refresh_token

# extracts jti and expiry from access and refresh tokens and sends them to redis for blacklisting
async def logout(token: str, refresh_token: str | None = None) -> None:
    try:
        # extracts the payload from the token
        payload = jwt_gen.decode_access_token(token)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid token")

    jti = payload.get("jti")
    exp = payload.get("exp")
    if jti is None or exp is None:
        raise HTTPException(status_code=401, detail="Invalid token")

    expires_at = datetime.fromtimestamp(exp, tz=timezone.utc)
    await add_to_blacklist(jti, expires_at)
    logger.info("audit: event=logout user_id=%s", payload.get("sub"))

    if refresh_token is not None:
        try:
            rt_payload = jwt_gen.decode_refresh_token(refresh_token)
            rt_jti = rt_payload.get("jti")
            rt_exp = rt_payload.get("exp")
            if rt_jti is not None and rt_exp is not None:
                rt_expires_at = datetime.fromtimestamp(rt_exp, tz=timezone.utc)
                await add_to_blacklist(rt_jti, rt_expires_at)
        except TokenError:
            pass


async def request_password_reset(db: Session, email: str) -> None:
    user = find_user_by_email(db, email)
    if user is None or not user.is_verified or user.password_hash == "!oauth":
        return

    code = str(uuid.uuid4())
    expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=jwt_gen.config.password_reset_token_expiry_minutes
    )

    reset_token = jwt_gen.create_password_reset_token(str(user.id))
    new_payload = jwt_gen.decode_password_reset_token(reset_token)
    new_jti = new_payload.get("jti")
    new_jti_expires_at = datetime.fromtimestamp(new_payload["exp"], tz=timezone.utc)

    # blacklist the previous pending reset token if one exists
    prev_jti_action = find_action_by_user_and_type(db, user.id, ACTION_PASSWORD_RESET_JTI)
    if prev_jti_action is not None:
        await add_to_blacklist(prev_jti_action.code, prev_jti_action.expires_at)

    upsert_action(db, user.id, ACTION_PASSWORD_RESET_JTI, new_jti, new_jti_expires_at, commit=False)
    upsert_action(db, user.id, ACTION_PASSWORD_RESET_CODE, code, expires_at, commit=False)
    db.commit()

    try:
        send_password_reset_email(user.email, code)
    except http_requests.RequestException as exc:
        logger.error("Failed to send password reset email: %s", exc)
        raise HTTPException(status_code=503, detail="Unable to send email. Please try again later.")

    logger.info("audit: event=password_reset_requested user_id=%s email=%s", user.id, user.email)


def send_verification_email_for_user(db: Session, user: User) -> None:
    code = str(uuid.uuid4())
    expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=jwt_gen.config.email_verification_token_expiry_minutes
    )
    send_verification_email(user.email, code)
    upsert_action(db, user.id, ACTION_EMAIL_VERIFICATION_CODE, code, expires_at)


def resend_verification_email(db: Session, email: str) -> None:
    user = find_user_by_email(db, email)
    if user is None or user.is_verified:
        return

    try:
        send_verification_email_for_user(db, user)
    except http_requests.RequestException as exc:
        logger.error("Failed to send verification email: %s", exc)
        raise HTTPException(status_code=503, detail="Unable to send email. Please try again later.")


async def verify_email_token(db: Session, token: str) -> None:
    try:
        payload = jwt_gen.decode_email_verification_token(token)
    except TokenError:
        raise HTTPException(status_code=400, detail="Invalid or expired verification token")

    jti = payload.get("jti")
    if jti is None or await is_blacklisted(jti):
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
        raise HTTPException(status_code=400, detail="Invalid or expired verification link")

    exp = payload.get("exp")
    expires_at = datetime.fromtimestamp(exp, tz=timezone.utc)
    await add_to_blacklist(jti, expires_at)
    verify_user(db, user, commit=False)
    db.commit()
    logger.info("audit: event=email_verified user_id=%s email=%s", user_id, user.email)


async def reset_password(db: Session, token: str, new_password: str) -> None:
    try:
        payload = jwt_gen.decode_password_reset_token(token)
    except TokenError:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")

    jti = payload.get("jti")
    if jti is None or await is_blacklisted(jti):
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

    # validate JTI matches the stored pending action
    jti_action = find_action_by_user_and_type(db, user.id, ACTION_PASSWORD_RESET_JTI)
    if jti_action is None or jti_action.code != jti:
        raise HTTPException(status_code=400, detail="Reset link has already been used")

    exp = payload.get("exp")
    expires_at = datetime.fromtimestamp(exp, tz=timezone.utc)
    await add_to_blacklist(jti, expires_at)
    update_password(db, user, hash_password(new_password), commit=False)
    delete_actions_for_user(db, user.id, ALL_RESET_ACTIONS, commit=False)
    db.commit()
    logger.info("audit: event=password_reset user_id=%s email=%s", user_id, user.email)


def verify_email_code(db: Session, code: str) -> None:
    result = find_user_by_action_code_for_update(db, code, ACTION_EMAIL_VERIFICATION_CODE)
    if result is None:
        raise HTTPException(status_code=400, detail="Invalid or expired verification link")

    action, user = result

    if user.is_verified:
        raise HTTPException(status_code=400, detail="Invalid or expired verification link")

    if action.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Invalid or expired verification link")

    delete_action(db, action, commit=False)
    verify_user(db, user, commit=False)
    db.commit()
    logger.info("audit: event=email_verified user_id=%s email=%s", user.id, user.email)


def reset_password_via_code(db: Session, code: str, new_password: str) -> None:
    result = find_user_by_action_code_for_update(db, code, ACTION_PASSWORD_RESET_CODE)
    if result is None:
        raise HTTPException(status_code=400, detail="Invalid or expired reset link")

    action, user = result

    if action.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Invalid or expired reset link")

    update_password(db, user, hash_password(new_password), commit=False)
    delete_actions_for_user(db, user.id, ALL_RESET_ACTIONS, commit=False)
    db.commit()
    logger.info("audit: event=password_reset user_id=%s email=%s", user.id, user.email)


def change_password(db: Session, user: User, current_password: str, new_password: str) -> None:
    if user.password_hash == "!oauth":
        raise HTTPException(status_code=400, detail="Password change is not available for OAuth accounts. Set a password first.")
    if not verify_password(current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    update_password(db, user, hash_password(new_password), commit=False)
    delete_actions_for_user(db, user.id, ALL_RESET_ACTIONS, commit=False)
    db.commit()
    logger.info("audit: event=password_changed user_id=%s email=%s", user.id, user.email)


ACTION_INVITE = "invite"


def _get_valid_invite(db: Session, code: str):
    result = find_user_by_action_code_for_update(db, code, ACTION_INVITE)
    if result is None:
        raise HTTPException(status_code=400, detail="Invalid or expired invite code")

    action, user = result

    if action.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Invalid or expired invite code")

    if user.is_verified:
        raise HTTPException(status_code=400, detail="Invite has already been accepted")

    return action, user


def validate_invite_code(db: Session, code: str) -> None:
    _get_valid_invite(db, code)


def accept_invite(db: Session, code: str, first_name: str, last_name: str, password: str) -> None:
    action, user = _get_valid_invite(db, code)
    set_invited_user_profile(db, user, first_name, last_name, hash_password(password), commit=False)
    delete_action(db, action, commit=False)
    db.commit()
    logger.info("audit: event=invite_accepted user_id=%s email=%s", user.id, user.email)


def validate_reset_code(db: Session, code: str) -> None:
    result = find_user_by_action_code_for_update(db, code, ACTION_PASSWORD_RESET_CODE)
    if result is None:
        raise HTTPException(status_code=400, detail="Invalid or expired reset link")

    action, user = result

    if action.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Invalid or expired reset link")
