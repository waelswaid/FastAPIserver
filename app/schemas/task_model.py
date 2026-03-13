from pydantic import BaseModel
from typing import Optional

class Task(BaseModel):
    title: str
    completed: bool = False