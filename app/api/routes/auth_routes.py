from fastapi import APIRouter, Depends, Response, Cookie, HTTPException
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.schemas.login_request import LoginRequest
from app.schemas.token_response import TokenResponse
from app.schemas.password_reset_schema import ForgotPasswordRequest, ResetPasswordRequest
from app.services.auth_services import user_login, refresh_access_token, logout, jwt_gen, request_password_reset, reset_password, verify_email_token
from app.api.dependencies.auth_dependency import oauth2_scheme
from app.core.config import settings
from typing import Optional


auth_router = APIRouter(prefix="/auth", tags=["auth"])


@auth_router.post("/login", response_model=TokenResponse)
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


@auth_router.post("/refresh", response_model=TokenResponse)
def route_refresh_token(refresh_token: Optional[str] = Cookie(None), db: Session = Depends(get_db)) -> TokenResponse:
    if refresh_token is None:
        raise HTTPException(status_code=401, detail="No refresh token provided")
    return refresh_access_token(db, refresh_token)


@auth_router.post("/logout", status_code=204)
def route_logout(response: Response, token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    logout(db, token)
    response.delete_cookie("refresh_token")


@auth_router.post("/forgot-password", status_code=200)
def route_forgot_password(body: ForgotPasswordRequest, db: Session = Depends(get_db)):
    request_password_reset(db, body.email)
    return {"message": "If that email is registered, a reset link has been sent."}


@auth_router.post("/reset-password", status_code=200)
def route_reset_password(body: ResetPasswordRequest, db: Session = Depends(get_db)):
    reset_password(db, body.token, body.new_password)
    return {"message": "Password updated successfully."}


@auth_router.get("/verify-email", status_code=200)
def route_verify_email(token: str, db: Session = Depends(get_db)):
    verify_email_token(db, token)
    return {"message": "Email verified successfully. You can now log in."}