import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from starlette.middleware.cors import CORSMiddleware

from app.core.logging import init_logging, correlation_id_var
from app.core.config import settings

init_logging(settings.ENVIRONMENT, settings.LOG_LEVEL)
logger = logging.getLogger(__name__)

from app.api.routes.user_routes import user_router
from app.api.routes.auth_routes import auth_router
from app.api.routes.admin_routes import admin_router
from app.api.routes.health_routes import health_router
from app.database.session import SessionLocal
from app.repositories.pending_action_repository import cleanup_expired_actions
from app.core.redis import init_redis, close_redis


"""
@asynccontextmanager: Code before yield → runs at startup, Code after yield → runs at shutdown
"""

@asynccontextmanager
async def lifespan(app: FastAPI):
    db = SessionLocal()
    try:
        cleanup_expired_actions(db)
    finally:
        db.close()
    await init_redis()
    yield # app runs here. when it shutsdown it runs the line below
    await close_redis()


app = FastAPI(lifespan=lifespan)

from app.api.exception_handlers import register_exception_handlers
register_exception_handlers(app)

origins = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_logging_middleware(request: Request, call_next) -> Response:
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    token = correlation_id_var.set(request_id)
    request.state.correlation_id = request_id
    start = time.perf_counter()
    try:
        response: Response = await call_next(request)
        duration_ms = round((time.perf_counter() - start) * 1000, 1)
        response.headers["X-Request-ID"] = request_id
        if request.url.path != "/health":
            logger.info(
                "%s %s %s %.1fms",
                request.method,
                request.url.path,
                response.status_code,
                duration_ms,
            )
        return response
    finally:
        correlation_id_var.reset(token)


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

if settings.ENVIRONMENT != "production":
    from app.api.routes.dev_routes import dev_router
    app.include_router(dev_router, prefix="/api")



"""
middleware:
    client sends http request --> rate_limit_headers_middleware --> runs code until call_next --> 
    request_logging_middleware --> runs code untill call_next --> route handler --> auth_Services -->
    repositories --> db --> ... --> request_logging_middleware runs the code after call_next --> logs duration, sets X-Request-ID 
    --> rate_limit_headers_middleware runs code after call_next --> sets X-RateLimit-* headers
"""



"""
headers:
  X-Request-ID — A correlation ID (UUID) to trace a single request through logs. If the client sends one, the app reuses it,  
  otherwise it generates one. Useful for debugging across services.

  X-RateLimit-Limit — The max number of requests allowed in the window (e.g., 10).

  X-RateLimit-Remaining — How many requests the client has left (e.g., 7).

  X-RateLimit-Reset — When the rate limit window resets (typically a Unix timestamp).
"""