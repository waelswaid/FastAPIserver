import logging
from urllib.parse import urlencode

import requests as http_requests
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.user import User
from app.repositories.oauth_account_repository import (
    find_by_provider_and_provider_user_id,
    create_oauth_account,
)
from app.repositories.user_repository import find_user_by_email
from app.services.auth_services import jwt_gen

logger = logging.getLogger(__name__)

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"

PROVIDER_GOOGLE = "google"


def get_google_auth_url(state: str) -> str:
    if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_REDIRECT_URI:
        raise HTTPException(status_code=503, detail="Google OAuth is not configured")

    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "state": state,
        "prompt": "select_account",
    }
    return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"


def _exchange_code_for_tokens(code: str) -> dict:
    resp = http_requests.post(
        GOOGLE_TOKEN_URL,
        data={
            "code": code,
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "redirect_uri": settings.GOOGLE_REDIRECT_URI,
            "grant_type": "authorization_code",
        },
        timeout=10,
    )
    if resp.status_code != 200:
        logger.warning("audit: event=oauth_token_exchange_failed provider=google status=%s", resp.status_code)
        raise HTTPException(status_code=400, detail="Failed to exchange authorization code")
    return resp.json()


def _fetch_google_user_info(access_token: str) -> dict:
    resp = http_requests.get(
        GOOGLE_USERINFO_URL,
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=10,
    )
    if resp.status_code != 200:
        logger.warning("audit: event=oauth_userinfo_failed provider=google status=%s", resp.status_code)
        raise HTTPException(status_code=400, detail="Failed to fetch user info from Google")
    return resp.json()


def _issue_tokens(user: User) -> tuple[str, str]:
    claims = {"role": user.role, "email": user.email}
    access_token = jwt_gen.create_access_token(str(user.id), additional_claims=claims)
    refresh_token = jwt_gen.create_refresh_token(str(user.id), additional_claims=claims)
    return access_token, refresh_token


def google_callback(db: Session, code: str) -> tuple[str, str]:
    if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
        raise HTTPException(status_code=503, detail="Google OAuth is not configured")

    token_data = _exchange_code_for_tokens(code)
    google_access_token = token_data.get("access_token")
    if not google_access_token:
        raise HTTPException(status_code=400, detail="No access token received from Google")

    user_info = _fetch_google_user_info(google_access_token)
    google_sub = user_info.get("sub")
    email = user_info.get("email")
    if not google_sub or not email:
        raise HTTPException(status_code=400, detail="Incomplete user info from Google")

    # 1. Check if OAuth account already linked
    oauth_account = find_by_provider_and_provider_user_id(db, PROVIDER_GOOGLE, google_sub)
    if oauth_account is not None:
        user = db.query(User).filter(User.id == oauth_account.user_id).first()
        if user is None:
            raise HTTPException(status_code=400, detail="Linked user account not found")
        if user.is_disabled:
            logger.warning("audit: event=oauth_login_failed_disabled provider=google email=%s", email)
            raise HTTPException(status_code=403, detail="Your account has been disabled. Contact an administrator.")
        logger.info("audit: event=oauth_login provider=google user_id=%s email=%s", user.id, user.email)
        return _issue_tokens(user)

    # 2. Check if user with same email exists — link the OAuth account
    user = find_user_by_email(db, email)
    if user is not None:
        if user.is_disabled:
            logger.warning("audit: event=oauth_login_failed_disabled provider=google email=%s", email)
            raise HTTPException(status_code=403, detail="Your account has been disabled. Contact an administrator.")
        create_oauth_account(db, user.id, PROVIDER_GOOGLE, google_sub)
        if not user.is_verified:
            user.is_verified = True
            db.commit()
        logger.info("audit: event=oauth_account_linked provider=google user_id=%s email=%s", user.id, user.email)
        return _issue_tokens(user)

    # 3. New user — create account + OAuth link
    first_name = user_info.get("given_name", "")
    last_name = user_info.get("family_name", "")
    new_user = User(
        first_name=first_name or "",
        last_name=last_name or "",
        email=email,
        password_hash="!oauth",
        is_verified=True,
    )
    db.add(new_user)
    db.flush()
    create_oauth_account(db, new_user.id, PROVIDER_GOOGLE, google_sub, commit=False)
    db.commit()
    db.refresh(new_user)
    logger.info("audit: event=oauth_registration provider=google user_id=%s email=%s", new_user.id, new_user.email)
    return _issue_tokens(new_user)
