import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response

logging.basicConfig(level=logging.INFO)
from app.api.routes.user_routes import user_router
from app.api.routes.auth_routes import auth_router
from app.api.routes.admin_routes import admin_router
from app.api.routes.health_routes import health_router
from app.database.session import SessionLocal
from app.repositories.token_blacklist_repository import cleanup_expired_tokens
from app.repositories.pending_action_repository import cleanup_expired_actions
from app.core.redis import init_redis, close_redis


@asynccontextmanager
async def lifespan(app: FastAPI):
    db = SessionLocal()
    try:
        cleanup_expired_tokens(db)
        cleanup_expired_actions(db)
    finally:
        db.close()
    await init_redis()
    yield
    await close_redis()


app = FastAPI(lifespan=lifespan)


@app.middleware("http")
async def rate_limit_headers_middleware(request: Request, call_next) -> Response:
    response: Response = await call_next(request)
    limit = getattr(request.state, "rate_limit_limit", None)
    if limit is not None:
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(
            getattr(request.state, "rate_limit_remaining", 0)
        )
        response.headers["X-RateLimit-Reset"] = str(
            getattr(request.state, "rate_limit_reset", 0)
        )
    return response


app.include_router(health_router)
app.include_router(user_router, prefix="/api")
app.include_router(auth_router, prefix="/api")
app.include_router(admin_router, prefix="/api/admin")
