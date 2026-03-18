from pydantic import BaseModel, EmailStr, ConfigDict, Field
from datetime import datetime
from typing import Optional
import uuid

class UserBase(BaseModel):
    first_name: str
    last_name: str
    email: EmailStr

# input for post requests
class UserCreate(UserBase):
    password: str = Field(min_length = 8, max_length = 128)

# response model
class UserRead(UserBase):
    model_config = ConfigDict(from_attributes=True)
    id : uuid.UUID
    role: str
    created_at: datetime


class UserUpdate(BaseModel):
    first_name: Optional[str] = Field(None, min_length=1, max_length=255)
    last_name: Optional[str] = Field(None, min_length=1, max_length=255)
