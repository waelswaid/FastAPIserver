# app/models/task.py

import uuid
from sqlalchemy import BigInteger, Column, String, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from app.models.base import Base


class Task(Base):
    __tablename__ = "tasks"

    id = Column(BigInteger, primary_key=True)
    task = Column(String(200), nullable=False)
    completed = Column(Boolean, nullable=False, default=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)



