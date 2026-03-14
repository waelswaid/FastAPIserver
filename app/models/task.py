# app/models/task.py

from sqlalchemy import Column, String, Boolean
from app.models.base import Base


class Task(Base):
    __tablename__ = "tasks"

    task = Column(String(200), primary_key = True)
    completed = Column(Boolean, default=False)



