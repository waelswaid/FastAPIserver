from fastapi import APIRouter, Depends, Response, Cookie, HTTPException
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.schemas.login_request import LoginRequest
from app.schemas.token_response import TokenResponse
from app.schemas.password_reset_schema import ForgotPasswordRequest, ResetPasswordRequest, VerifyEmailRequest, ChangePasswordRequest
from app.services.auth_services import (
    user_login, refresh_access_token, logout, jwt_gen,
    request_password_reset, reset_password, verify_email_token, resend_verification_email,
    verify_email_code, reset_password_via_code, validate_reset_code, change_password,
)
from app.api.dependencies.auth_dependency import oauth2_scheme, get_current_user
from app.models.user import User
from app.api.dependencies.rate_limiter import (
    forgot_password_limiter, resend_verification_limiter, reset_password_limiter,
    login_limiter, login_global_limiter, refresh_limiter,
    verify_email_limiter, validate_reset_code_limiter, change_password_limiter,
)
from app.core.config import settings
from typing import Optional


auth_router = APIRouter(prefix="/auth", tags=["auth"])


@auth_router.get("/validate-token")
def validate_token(current_user: User = Depends(get_current_user)):
    return {
        "user_id": str(current_user.id),
        "email": current_user.email,
        "first_name": current_user.first_name,
        "last_name": current_user.last_name,
        "is_verified": current_user.is_verified,
        "role": current_user.role,
    }


@auth_router.post("/login", response_model=TokenResponse, dependencies=[Depends(login_limiter), Depends(login_global_limiter)])
def route_login_request(login_data: LoginRequest, response: Response, db: Session = Depends(get_db)) -> TokenResponse:
    access_token, refresh_token = user_login(db, login_data)
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
def route_refresh_token(refresh_token: Optional[str] = Cookie(None), db: Session = Depends(get_db)) -> TokenResponse:
    if refresh_token is None:
        raise HTTPException(status_code=401, detail="No refresh token provided")
    return refresh_access_token(db, refresh_token)


@auth_router.post("/logout", status_code=204)
def route_logout(response: Response, token: str = Depends(oauth2_scheme), refresh_token: Optional[str] = Cookie(None), db: Session = Depends(get_db)):
    logout(db, token, refresh_token)
    response.delete_cookie("refresh_token")


@auth_router.post("/forgot-password", status_code=200, dependencies=[Depends(forgot_password_limiter)])
def route_forgot_password(body: ForgotPasswordRequest, db: Session = Depends(get_db)):
    request_password_reset(db, body.email)
    return {"message": "If that email is registered, a reset link has been sent."}


@auth_router.get("/reset-password", status_code=200, dependencies=[Depends(validate_reset_code_limiter)])
def route_validate_reset_code(code: str, db: Session = Depends(get_db)):
    validate_reset_code(db, code)
    return {"message": "Code is valid.", "code": code}


@auth_router.post("/reset-password", status_code=200, dependencies=[Depends(reset_password_limiter)])
def route_reset_password(body: ResetPasswordRequest, db: Session = Depends(get_db)):
    if body.code:
        reset_password_via_code(db, body.code, body.new_password)
    else:
        reset_password(db, body.token, body.new_password)
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
def route_verify_email(body: VerifyEmailRequest, db: Session = Depends(get_db)):
    verify_email_token(db, body.token)
    return {"message": "Email verified successfully. You can now log in."}


@auth_router.post("/change-password", status_code=200, dependencies=[Depends(change_password_limiter)])
def route_change_password(body: ChangePasswordRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    change_password(db, current_user, body.current_password, body.new_password)
    return {"message": "Password changed successfully."}