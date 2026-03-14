from fastapi import FastAPI
from app.api.routes.task_routes import tasks_router
from app.api.routes.user_routes import user_router

app = FastAPI()


app.include_router(tasks_router, prefix="/api")
app.include_router(user_router, prefix="/api")





