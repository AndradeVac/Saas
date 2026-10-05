from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.core.plans import ensure_can_add_product
from app.models.product import Product
from app.models.tenant import Tenant
from app.models.user import User
from app.repositories.category import CategoryRepository
from app.repositories.product import ProductRepository
from app.schemas.product import ProductCreate, ProductUpdate
from app.services.audit import record_audit
from app.services.media import MediaService


def _dump_options(groups) -> list[dict]:
    return [group.model_dump(mode="json") for group in groups]


class ProductService:

    def __init__(self, db: Session, tenant_id: UUID):
        self.repository = ProductRepository(db, tenant_id)
        self.category_repository = CategoryRepository(db, tenant_id)
        self.media = MediaService(db, tenant_id)
        self.tenant_id = tenant_id
        self.db = db

    def _validate_category(self, category_id: UUID) -> None:
        if self.category_repository.get_by_id(category_id) is None:
            raise NotFoundError("Categoria não encontrada ou inativa.")

    def _tenant(self) -> Tenant:
        return self.db.get(Tenant, self.tenant_id)

    def create(self, data: ProductCreate, actor: User | None = None) -> Product:
        self._validate_category(data.category_id)
        ensure_can_add_product(self.db, self._tenant())
        product = Product(
            category_id=data.category_id,
            name=data.name,
            description=data.description,
            image_url=data.image_url,
            price=data.price,
            featured=data.featured,
            available=data.available,
            sort_order=data.sort_order,
            options=_dump_options(data.options),
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
        previous_image = product.image_url

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
        if data.available is not None:
            product.available = data.available
        if data.active is not None:
            if data.active and not product.active:
                ensure_can_add_product(self.db, self._tenant())
            product.active = data.active
        if data.sort_order is not None:
            product.sort_order = data.sort_order
        if data.options is not None:
            product.options = _dump_options(data.options)

        self.repository.update(product)
        if product.image_url != previous_image:
            self.media.release_if_orphan(previous_image)
        record_audit(self.db, self.tenant_id, actor, "PRODUCT_UPDATED", "PRODUCT", product.id, product.name)
        self.db.commit()
        return product

    def delete(self, product_id: UUID, actor: User | None = None) -> Product:
        product = self.get_by_id(product_id)
        self.repository.delete(product)
        record_audit(self.db, self.tenant_id, actor, "PRODUCT_REMOVED", "PRODUCT", product.id, product.name)
        self.db.commit()
        return product
