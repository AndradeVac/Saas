from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.product import Product


class ProductRepository:
    def __init__(self, db: Session, tenant_id: UUID):
        self.db = db
        self.tenant_id = tenant_id

    def create(self, product: Product) -> Product:
        product.tenant_id = self.tenant_id
        self.db.add(product)
        self.db.flush()
        self.db.refresh(product)
        return product

    def get_by_id(self, product_id: UUID) -> Product | None:
        """Active products only (what can be sold)."""
        return self.db.scalar(select(Product).where(
            Product.tenant_id == self.tenant_id,
            Product.id == product_id,
            Product.active.is_(True),
        ))

    def get_by_id_any_status(self, product_id: UUID) -> Product | None:
        return self.db.scalar(select(Product).where(
            Product.tenant_id == self.tenant_id,
            Product.id == product_id,
        ))

    def get_all(self, only_active: bool = False) -> list[Product]:
        statement = select(Product).where(Product.tenant_id == self.tenant_id)
        if only_active:
            statement = statement.where(Product.active.is_(True))
        return list(self.db.scalars(statement.order_by(Product.name)).all())

    def update(self, product: Product) -> Product:
        self.db.flush()
        self.db.refresh(product)
        return product

    def delete(self, product: Product) -> Product:
        product.active = False
        return self.update(product)
