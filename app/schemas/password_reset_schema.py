from typing import Optional
from pydantic import BaseModel, EmailStr, Field, model_validator


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: Optional[str] = None
    code: Optional[str] = None
    new_password: str = Field(min_length=8, max_length=128)

    @model_validator(mode="after")
    def require_token_or_code(self):
        if not self.token and not self.code:
            raise ValueError("Either 'token' or 'code' must be provided")
        return self


class VerifyEmailRequest(BaseModel):
    token: str
