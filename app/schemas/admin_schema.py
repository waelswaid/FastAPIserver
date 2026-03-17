from pydantic import BaseModel
from typing import Literal


class ChangeRoleRequest(BaseModel):
    role: Literal["user", "admin"]
