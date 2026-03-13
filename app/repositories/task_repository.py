from sqlalchemy.orm import Session
from app.models.task import Task


# select * from tasks
def get_all_tasks(db: Session):
    return db.query(Task).all()



def create_task(db: Session, task_name: str, completed: bool = False):
    task = Task(
        task=task_name,
        completed=completed
    )

    db.add(task)
    db.commit()
    db.refresh(task)

    return task

def set_complete(task_name : str, db : Session):
    task = db.query(Task).filter(Task.task == task_name).first()
    task.completed = True
    db.commit()