from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models.coupon import Coupon


class CouponRepository:
    def __init__(self, db: Session, tenant_id: UUID):
        self.db = db
        self.tenant_id = tenant_id

    def create(self, coupon: Coupon) -> Coupon:
        coupon.tenant_id = self.tenant_id
        self.db.add(coupon)
        self.db.flush()
        self.db.refresh(coupon)
        return coupon

    def get_by_id(self, coupon_id: UUID) -> Coupon | None:
        return self.db.scalar(select(Coupon).where(Coupon.tenant_id == self.tenant_id, Coupon.id == coupon_id))

    def get_by_code(self, code: str) -> Coupon | None:
        return self.db.scalar(select(Coupon).where(Coupon.tenant_id == self.tenant_id, Coupon.code == code))

    def get_all(self) -> list[Coupon]:
        return list(self.db.scalars(
            select(Coupon).where(Coupon.tenant_id == self.tenant_id).order_by(Coupon.created_at.desc())
        ).all())

    def update(self, coupon: Coupon) -> Coupon:
        self.db.flush()
        self.db.refresh(coupon)
        return coupon

    def delete(self, coupon: Coupon) -> None:
        self.db.delete(coupon)
        self.db.flush()

    def consume(self, coupon_id: UUID) -> bool:
        """Atomically takes one use; False when the coupon just ran out (two customers racing for the last use)."""
        result = self.db.execute(
            update(Coupon)
            .where(
                Coupon.id == coupon_id,
                Coupon.tenant_id == self.tenant_id,
                (Coupon.max_uses.is_(None)) | (Coupon.used_count < Coupon.max_uses),
            )
            .values(used_count=Coupon.used_count + 1)
        )
        return result.rowcount == 1

    def release(self, coupon_id: UUID) -> None:
        self.db.execute(
            update(Coupon)
            .where(Coupon.id == coupon_id, Coupon.tenant_id == self.tenant_id, Coupon.used_count > 0)
            .values(used_count=Coupon.used_count - 1)
        )
