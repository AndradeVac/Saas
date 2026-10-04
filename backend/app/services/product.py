from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.models.product import Product
from app.models.user import User
from app.repositories.category import CategoryRepository
from app.repositories.product import ProductRepository
from app.schemas.product import ProductCreate, ProductUpdate
from app.services.audit import record_audit


class ProductService:

    def __init__(self, db: Session, tenant_id: UUID):
        self.repository = ProductRepository(db, tenant_id)
        self.category_repository = CategoryRepository(db, tenant_id)
        self.tenant_id = tenant_id
        self.db = db

    def _validate_category(self, category_id: UUID) -> None:
        if self.category_repository.get_by_id(category_id) is None:
            raise NotFoundError("Categoria não encontrada ou inativa.")

    def create(self, data: ProductCreate, actor: User | None = None) -> Product:
        self._validate_category(data.category_id)
        product = Product(
            category_id=data.category_id,
            name=data.name,
            description=data.description,
            image_url=data.image_url,
            price=data.price,
            featured=data.featured,
        )
        self.repository.create(product)
        record_audit(self.db, self.tenant_id, actor, "PRODUCT_CREATED", "PRODUCT", product.id, product.name)
        self.db.commit()
        return product

    def get_by_id(self, product_id: UUID) -> Product:
        product = self.repository.get_by_id_any_status(product_id)
        if product is None:
            raise NotFoundError("Produto não encontrado.")
        return product

    def get_all(self) -> list[Product]:
        return self.repository.get_all()

    def update(self, product_id: UUID, data: ProductUpdate, actor: User | None = None) -> Product:
        product = self.get_by_id(product_id)

        if data.category_id is not None:
            self._validate_category(data.category_id)
            product.category_id = data.category_id
        if data.name is not None:
            product.name = data.name
        if "description" in data.model_fields_set:
            product.description = data.description
        if "image_url" in data.model_fields_set:
            product.image_url = data.image_url
        if data.price is not None:
            product.price = data.price
        if data.featured is not None:
            product.featured = data.featured
        if data.active is not None:
            product.active = data.active

        self.repository.update(product)
        record_audit(self.db, self.tenant_id, actor, "PRODUCT_UPDATED", "PRODUCT", product.id, product.name)
        self.db.commit()
        return product

    def delete(self, product_id: UUID, actor: User | None = None) -> Product:
        product = self.get_by_id(product_id)
        self.repository.delete(product)
        record_audit(self.db, self.tenant_id, actor, "PRODUCT_REMOVED", "PRODUCT", product.id, product.name)
        self.db.commit()
        return product
