from pydantic import BaseModel, EmailStr, Field

class LoginBase(BaseModel):
    email: EmailStr
    password: str = Field(min_length = 8, max_length = 128)

class LoginRequest(LoginBase):
    pass

