import logging
import secrets
from typing import Optional

from fastapi import APIRouter, Depends, Response, Cookie, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.schemas.login_request import LoginRequest
from app.schemas.token_response import TokenResponse
from app.schemas.password_reset_schema import ForgotPasswordRequest, ResetPasswordRequest, VerifyEmailRequest, ChangePasswordRequest
from app.services.auth_services import (
    user_login, refresh_access_token, logout, jwt_gen,
    request_password_reset, reset_password, verify_email_token, resend_verification_email,
    verify_email_code, reset_password_via_code, validate_reset_code, change_password,
    accept_invite, validate_invite_code,
)
from app.services.oauth_service import get_google_auth_url, google_callback
from app.schemas.admin_schema import AcceptInviteRequest
from app.api.dependencies.auth_dependency import oauth2_scheme, get_current_user
from app.models.user import User
from app.api.dependencies.rate_limiter import (
    forgot_password_limiter, resend_verification_limiter, reset_password_limiter,
    login_limiter, login_global_limiter, refresh_limiter,
    verify_email_limiter, validate_reset_code_limiter, change_password_limiter,
    lockout_limiter, accept_invite_limiter, oauth_limiter,
)
from app.core.config import settings

logger = logging.getLogger(__name__)

auth_router = APIRouter(prefix="/auth", tags=["auth"])

# service-to-service endpoint for token validation
@auth_router.get("/validate-token")
async def validate_token(current_user: User = Depends(get_current_user)):
    return {
        "user_id": str(current_user.id),
        "email": current_user.email,
        "first_name": current_user.first_name,
        "last_name": current_user.last_name,
        "is_verified": current_user.is_verified,
        "role": current_user.role,
    }

# validates user data, if everything is ok, stores refresh token in httponly cookie and returns JWT access token
@auth_router.post("/login", response_model=TokenResponse, dependencies=[Depends(login_limiter), Depends(login_global_limiter), Depends(lockout_limiter)])
async def route_login_request(login_data: LoginRequest, response: Response, db: Session = Depends(get_db)) -> TokenResponse:
    try:
        access_token, refresh_token = user_login(db, login_data) # user_login returns access and refresh tokens (logs in user)
    except HTTPException as exc:
        if exc.status_code == 401:
            # +1 log in attempts (account locks at 10)
            await lockout_limiter.record_failure(login_data.email)
        raise
    # logged in successfully? reset lockout limits on this email
    await lockout_limiter.clear(login_data.email)
    # stores the refresh token as a browser cookie instead of sending it in the JSON body
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=settings.ENVIRONMENT == "production",
        samesite="strict",
        max_age=jwt_gen.config.refresh_token_expiry_days * 86400,
    )
    return TokenResponse(access_token=access_token, token_type="bearer")


@auth_router.post("/refresh", response_model=TokenResponse, dependencies=[Depends(refresh_limiter)])
async def route_refresh_token(response: Response, refresh_token: Optional[str] = Cookie(None), db: Session = Depends(get_db)) -> TokenResponse:
    if refresh_token is None:
        raise HTTPException(status_code=401, detail="No refresh token provided")
    access_token, new_refresh_token = await refresh_access_token(db, refresh_token)
    response.set_cookie(
        key="refresh_token",
        value=new_refresh_token,
        httponly=True,
        secure=settings.ENVIRONMENT == "production",
        samesite="strict",
        max_age=jwt_gen.config.refresh_token_expiry_days * 86400,
    )
    return TokenResponse(access_token=access_token, token_type="bearer")


@auth_router.post("/logout", status_code=204)
async def route_logout(response: Response, token: str = Depends(oauth2_scheme), refresh_token: Optional[str] = Cookie(None)):
    await logout(token, refresh_token)
    response.delete_cookie("refresh_token")


@auth_router.post("/forgot-password", status_code=200, dependencies=[Depends(forgot_password_limiter)])
async def route_forgot_password(body: ForgotPasswordRequest, db: Session = Depends(get_db)):
    await request_password_reset(db, body.email)
    return {"message": "If that email is registered, a reset link has been sent."}


@auth_router.get("/reset-password", status_code=200, dependencies=[Depends(validate_reset_code_limiter)])
def route_validate_reset_code(code: str, db: Session = Depends(get_db)):
    validate_reset_code(db, code)
    return {"message": "Code is valid.", "code": code}


@auth_router.post("/reset-password", status_code=200, dependencies=[Depends(reset_password_limiter)])
async def route_reset_password(body: ResetPasswordRequest, db: Session = Depends(get_db)):
    if body.code:
        reset_password_via_code(db, body.code, body.new_password)
    else:
        await reset_password(db, body.token, body.new_password)
    return {"message": "Password updated successfully."}


@auth_router.post("/resend-verification", status_code=200, dependencies=[Depends(resend_verification_limiter)])
def route_resend_verification(body: ForgotPasswordRequest, db: Session = Depends(get_db)):
    resend_verification_email(db, body.email)
    return {"message": "If that email is registered and unverified, a new verification link has been sent."}


@auth_router.get("/verify-email", status_code=200, dependencies=[Depends(verify_email_limiter)])
def route_verify_email_via_link(code: str, db: Session = Depends(get_db)):
    verify_email_code(db, code)
    return {"message": "Email verified successfully. You can now log in."}


@auth_router.post("/verify-email", status_code=200, dependencies=[Depends(verify_email_limiter)])
async def route_verify_email(body: VerifyEmailRequest, db: Session = Depends(get_db)):
    await verify_email_token(db, body.token)
    return {"message": "Email verified successfully. You can now log in."}


@auth_router.post("/change-password", status_code=200, dependencies=[Depends(change_password_limiter)])
async def route_change_password(body: ChangePasswordRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    change_password(db, current_user, body.current_password, body.new_password)
    return {"message": "Password changed successfully."}


@auth_router.get("/accept-invite", status_code=200, dependencies=[Depends(accept_invite_limiter)])
def route_validate_invite_code(code: str, db: Session = Depends(get_db)):
    validate_invite_code(db, code)
    return {"message": "Invite code is valid.", "code": code}


@auth_router.post("/accept-invite", status_code=200, dependencies=[Depends(accept_invite_limiter)])
def route_accept_invite(body: AcceptInviteRequest, db: Session = Depends(get_db)):
    accept_invite(db, body.code, body.first_name, body.last_name, body.password)
    return {"message": "Account activated. You can now log in."}


@auth_router.get("/google", dependencies=[Depends(oauth_limiter)])
def route_google_login():
    state = secrets.token_urlsafe(32)
    url = get_google_auth_url(state)
    response = RedirectResponse(url=url)
    response.set_cookie(
        key="oauth_state",
        value=state,
        httponly=True,
        secure=settings.ENVIRONMENT == "production",
        samesite="lax",
        max_age=600,
    )
    return response


@auth_router.get("/google/callback")
def route_google_callback(code: str, state: str, oauth_state: Optional[str] = Cookie(None), db: Session = Depends(get_db)):
    if oauth_state is None or state != oauth_state:
        raise HTTPException(status_code=400, detail="Invalid OAuth state")
    access_token, refresh_token = google_callback(db, code)
    frontend_url = settings.OAUTH_FRONTEND_REDIRECT_URL or settings.CORS_ORIGINS.split(",")[0].strip()
    redirect_url = f"{frontend_url}/oauth-callback?token={access_token}"
    response = RedirectResponse(url=redirect_url)
    response.delete_cookie("oauth_state")
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=settings.ENVIRONMENT == "production",
        samesite="strict",
        max_age=jwt_gen.config.refresh_token_expiry_days * 86400,
    )
    return response
