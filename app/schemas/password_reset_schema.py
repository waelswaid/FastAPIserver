from pydantic import BaseModel, EmailStr
from app.schemas.users_schema import UserBase


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str
