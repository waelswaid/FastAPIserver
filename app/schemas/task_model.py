import uuid
from pydantic import BaseModel, ConfigDict


class TaskCreate(BaseModel):
    task: str
    user_id: uuid.UUID


class TaskComplete(BaseModel):
    id: int


class TaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    task: str
    completed: bool
    user_id: uuid.UUID