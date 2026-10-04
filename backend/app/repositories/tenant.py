from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models.tenant import Tenant


class TenantRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, tenant: Tenant) -> Tenant:
        self.db.add(tenant)
        self.db.flush()
        self.db.refresh(tenant)
        return tenant

    def get_by_slug(self, slug: str) -> Tenant | None:
        return self.db.scalar(select(Tenant).where(Tenant.slug == slug))

    def slug_exists(self, slug: str) -> bool:
        return self.db.scalar(select(Tenant.id).where(Tenant.slug == slug)) is not None

    def update(self, tenant: Tenant) -> Tenant:
        self.db.flush()
        self.db.refresh(tenant)
        return tenant

    def next_order_number(self, tenant_id: UUID) -> int:
        """Atomically reserves the next order number. The row lock lasts until the caller commits,
        so concurrent orders of the same tenant are numbered one after the other."""
        return int(self.db.execute(
            update(Tenant)
            .where(Tenant.id == tenant_id)
            .values(order_counter=Tenant.order_counter + 1)
            .returning(Tenant.order_counter)
        ).scalar_one())
