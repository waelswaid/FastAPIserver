from pydantic import BaseModel, EmailStr, ConfigDict, Field
from datetime import datetime
import uuid

class UserBase(BaseModel):
    name: str
    email: EmailStr

# input for post requests
class UserCreate(UserBase):
    password: str = Field(min_length = 8, max_length = 128)

# response model
class UserRead(UserBase):
    model_config = ConfigDict(from_attributes=True)
    id : uuid.UUID
    created_at: datetime

    





