from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.api.dependencies.auth_dependency import require_role
from app.schemas.admin_schema import ChangeRoleRequest
from app.schemas.users_schema import UserRead
from app.services.admin_services import change_user_role
from app.repositories.user_repository import list_users
from app.models.user import User
from typing import Optional
import uuid
import logging

logger = logging.getLogger(__name__)

admin_router = APIRouter(prefix="/users", tags=["admin"])

admin_dependency = require_role("admin")


@admin_router.patch("/{user_id}/role")
def route_change_user_role(
    user_id: uuid.UUID,
    body: ChangeRoleRequest,
    current_user: User = Depends(admin_dependency),
    db: Session = Depends(get_db),
):
    change_user_role(db, user_id, body.role)
    return {"message": "Role updated successfully"}


@admin_router.get("/", response_model=list[UserRead])
def route_list_users(
    role: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(admin_dependency),
    db: Session = Depends(get_db),
):
    return list_users(db, role_filter=role, skip=skip, limit=limit)
