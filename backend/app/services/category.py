from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.models.category import Category
from app.models.user import User
from app.repositories.category import CategoryRepository
from app.schemas.category import CategoryCreate, CategoryUpdate
from app.services.audit import record_audit
from app.services.media import MediaService


class CategoryService:

    def __init__(self, db: Session, tenant_id: UUID):
        self.repository = CategoryRepository(db, tenant_id)
        self.media = MediaService(db, tenant_id)
        self.tenant_id = tenant_id
        self.db = db

    def create(self, data: CategoryCreate, actor: User | None = None) -> Category:
        # Re-creating a name that was removed brings the old category back.
        existing = self.repository.get_by_name(data.name)
        if existing is not None and not existing.active:
            existing.active = True
            existing.image_url = data.image_url or existing.image_url
            existing.sort_order = data.sort_order
            self.repository.update(existing)
            self.db.commit()
            return existing

        category = Category(name=data.name, image_url=data.image_url, sort_order=data.sort_order)
        self.repository.create(category)
        record_audit(self.db, self.tenant_id, actor, "CATEGORY_CREATED", "CATEGORY", category.id, data.name)
        self.db.commit()
        return category

    def get_by_id(self, category_id: UUID) -> Category:
        category = self.repository.get_by_id(category_id)
        if category is None:
            raise NotFoundError("Categoria não encontrada.")
        return category

    def get_all(self) -> list[Category]:
        return self.repository.get_all()

    def update(self, category_id: UUID, data: CategoryUpdate, actor: User | None = None) -> Category:
        category = self.repository.get_by_id_any_status(category_id)
        if category is None:
            raise NotFoundError("Categoria não encontrada.")

        previous_image = category.image_url
        if data.name is not None:
            category.name = data.name
        if "image_url" in data.model_fields_set:
            category.image_url = data.image_url
        if data.sort_order is not None:
            category.sort_order = data.sort_order
        if data.active is not None:
            category.active = data.active

        self.repository.update(category)
        if category.image_url != previous_image:
            self.media.release_if_orphan(previous_image)
        record_audit(self.db, self.tenant_id, actor, "CATEGORY_UPDATED", "CATEGORY", category.id, category.name)
        self.db.commit()
        return category

    def delete(self, category_id: UUID, actor: User | None = None) -> Category:
        category = self.get_by_id(category_id)
        self.repository.delete(category)
        record_audit(self.db, self.tenant_id, actor, "CATEGORY_REMOVED", "CATEGORY", category.id, category.name)
        self.db.commit()
        return category
