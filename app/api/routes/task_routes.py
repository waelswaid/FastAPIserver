from fastapi import Depends, APIRouter
from app.database.session import get_db
from sqlalchemy.orm import Session
from app.schemas.task_model import Task
from app.services.task_services import return_task, create_task, set_complete


tasks_router = APIRouter(tags=["tasks"])


@tasks_router.get("/tasks/get")
def route_task(db : Session = Depends(get_db)):
    return return_task(db)
    

@tasks_router.post("/tasks/create")
def route_create_task(task: Task, db : Session = Depends(get_db)):
    return create_task(db, task)


@tasks_router.post("/tasks/complete")
def complete(task : Task, db : Session = Depends(get_db)):
    return set_complete(task, db)