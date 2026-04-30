from fastapi import APIRouter, HTTPException

from app.core.config import settings
from app.schemas.dev_schema import DevCodeRead
from app.utils import dev_codes

dev_router = APIRouter(prefix="/dev", tags=["dev"])


def _ensure_dev() -> None:
    if settings.ENVIRONMENT == "production":
        raise HTTPException(status_code=404)


@dev_router.get("/codes", response_model=list[DevCodeRead])
def route_list_dev_codes():
    _ensure_dev()
    return dev_codes.snapshot()


@dev_router.delete("/codes", status_code=204)
def route_clear_dev_codes():
    _ensure_dev()
    dev_codes.clear()
