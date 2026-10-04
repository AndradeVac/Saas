from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import admin_only, staff_only
from app.models.user import User
from app.schemas.category import CategoryCreate, CategoryResponse, CategoryUpdate
from app.services.category import CategoryService

router = APIRouter(prefix="/categories", tags=["Categories"])


@router.post("", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED)
def create_category(data: CategoryCreate, db: Session = Depends(get_db), actor: User = Depends(admin_only)):
    return CategoryService(db, actor.tenant_id).create(data, actor)


@router.get("", response_model=list[CategoryResponse])
def get_categories(db: Session = Depends(get_db), actor: User = Depends(staff_only)):
    return CategoryService(db, actor.tenant_id).get_all()


@router.patch("/{category_id}", response_model=CategoryResponse)
def update_category(
    category_id: UUID,
    data: CategoryUpdate,
    db: Session = Depends(get_db),
    actor: User = Depends(admin_only),
):
    return CategoryService(db, actor.tenant_id).update(category_id, data, actor)


@router.delete("/{category_id}", response_model=CategoryResponse)
def delete_category(category_id: UUID, db: Session = Depends(get_db), actor: User = Depends(admin_only)):
    return CategoryService(db, actor.tenant_id).delete(category_id, actor)
