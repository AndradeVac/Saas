from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.category import Category


class CategoryRepository:
    def __init__(self, db: Session, tenant_id: UUID):
        self.db = db
        self.tenant_id = tenant_id

    def create(self, category: Category) -> Category:
        category.tenant_id = self.tenant_id
        self.db.add(category)
        self.db.flush()
        self.db.refresh(category)
        return category

    def get_by_id(self, category_id: UUID) -> Category | None:
        """Active categories only."""
        return self.db.scalar(select(Category).where(
            Category.tenant_id == self.tenant_id,
            Category.id == category_id,
            Category.active.is_(True),
        ))

    def get_by_id_any_status(self, category_id: UUID) -> Category | None:
        return self.db.scalar(select(Category).where(
            Category.tenant_id == self.tenant_id,
            Category.id == category_id,
        ))

    def get_by_name(self, name: str) -> Category | None:
        return self.db.scalar(select(Category).where(
            Category.tenant_id == self.tenant_id,
            Category.name == name,
        ))

    def get_all(self, only_active: bool = False) -> list[Category]:
        statement = select(Category).where(Category.tenant_id == self.tenant_id)
        if only_active:
            statement = statement.where(Category.active.is_(True))
        return list(self.db.scalars(statement.order_by(Category.sort_order, Category.name)).all())

    def update(self, category: Category) -> Category:
        self.db.flush()
        self.db.refresh(category)
        return category

    def delete(self, category: Category) -> Category:
        category.active = False
        return self.update(category)
