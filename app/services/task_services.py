from app.schemas.task_model import TaskCreate, TaskComplete
from sqlalchemy.orm import Session
from app.repositories import task_repository


def return_task(db: Session):
    return task_repository.get_all_tasks(db)


def create_task(db: Session, task: TaskCreate):
    return task_repository.create_task(db=db, task_name=task.task, user_id=task.user_id)


def set_complete(task: TaskComplete, db: Session):
    return task_repository.set_complete(task_id=task.id, db=db)
