from app.schemas.task_model import Task
from sqlalchemy.orm import Session
from app.repositories import task_repository



def return_task(db : Session):
    tasks = task_repository.get_all_tasks(db)
    return tasks


def create_task(db : Session, task: Task):
    new_task = task_repository.create_task(db=db, task_name=task.title, completed = False)
    return new_task


def set_complete(task_name : Task, db : Session):
    return task_repository.set_complete(task_name = task_name.title, db=db)
