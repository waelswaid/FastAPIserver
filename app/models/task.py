# app/models/task.py

from sqlalchemy import Column, String, Boolean
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class Task(Base):
    __tablename__ = "tasks"

    task = Column(String(200), primary_key = True)
    completed = Column(Boolean, default=False)