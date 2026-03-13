from fastapi import FastAPI
from app.api.routes.task_routes import tasks_router


app = FastAPI()


app.include_router(tasks_router, prefix="/api")






