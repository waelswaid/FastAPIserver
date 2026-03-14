import uuid
from fastapi import HTTPException
from sqlalchemy.orm import Session
from app.models.task import Task


def get_all_tasks(db: Session):
    return db.query(Task).all()


def create_task(db: Session, task_name: str, user_id: uuid.UUID):
    task = Task(
        task=task_name,
        completed=False,
        user_id=user_id,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def set_complete(task_id: int, db: Session):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found.")
    task.completed = True
    db.commit()