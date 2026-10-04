from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import admin_only
from app.models.user import User
from app.schemas.user import UserCreate, UserResponse, UserStatusUpdate
from app.services.user import UserService

router = APIRouter(prefix="/users", tags=["Users"])


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(data: UserCreate, db: Session = Depends(get_db), actor: User = Depends(admin_only)):
    return UserService(db, actor.tenant_id).create(data, actor)


@router.get("", response_model=list[UserResponse])
def get_users(db: Session = Depends(get_db), actor: User = Depends(admin_only)):
    return UserService(db, actor.tenant_id).get_all()


@router.patch("/{user_id}/status", response_model=UserResponse)
def update_user_status(
    user_id: UUID,
    data: UserStatusUpdate,
    db: Session = Depends(get_db),
    actor: User = Depends(admin_only),
):
    return UserService(db, actor.tenant_id).update_status(user_id, data, actor)
