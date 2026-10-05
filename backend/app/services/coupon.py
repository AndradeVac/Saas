from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import BusinessRuleError, NotFoundError
from app.core.plans import COUPONS, has_feature
from app.models.coupon import Coupon, CouponKind
from app.models.tenant import Tenant
from app.models.user import User
from app.repositories.coupon import CouponRepository
from app.schemas.coupon import CouponCreate, CouponUpdate
from app.services.audit import record_audit

_CENTS = Decimal("0.01")


def compute_discount(coupon: Coupon, subtotal: Decimal) -> Decimal:
    if coupon.kind is CouponKind.PERCENT:
        amount = (subtotal * coupon.value / 100).quantize(_CENTS, rounding=ROUND_HALF_UP)
    else:
        amount = coupon.value
    return min(amount, subtotal)


class CouponService:
    def __init__(self, db: Session, tenant_id: UUID):
        self.repository = CouponRepository(db, tenant_id)
        self.tenant_id = tenant_id
        self.db = db

    # -- customer side --------------------------------------------------------------------
    def validate(self, code: str, subtotal: Decimal) -> tuple[Coupon, Decimal]:
        """Checks a code against the current order subtotal. Does not consume a use."""
        tenant = self.db.get(Tenant, self.tenant_id)
        coupon = self.repository.get_by_code("".join(code.split()).upper()) if has_feature(tenant, COUPONS) else None
        if coupon is None or not coupon.active:
            raise BusinessRuleError("Cupom inválido.")
        if coupon.expires_at is not None and coupon.expires_at <= datetime.now(timezone.utc):
            raise BusinessRuleError("Este cupom expirou.")
        if coupon.max_uses is not None and coupon.used_count >= coupon.max_uses:
            raise BusinessRuleError("Este cupom já foi totalmente utilizado.")
        if subtotal < coupon.min_order:
            raise BusinessRuleError(f"Pedido mínimo de R$ {coupon.min_order:.2f} para usar este cupom.".replace(".", ",", 1))
        return coupon, compute_discount(coupon, subtotal)

    def consume(self, coupon: Coupon) -> None:
        if not self.repository.consume(coupon.id):
            raise BusinessRuleError("Este cupom já foi totalmente utilizado.")

    def release(self, code: str | None) -> None:
        coupon = self.repository.get_by_code(code) if code else None
        if coupon is not None:
            self.repository.release(coupon.id)

    # -- admin ----------------------------------------------------------------------------
    def get_all(self) -> list[Coupon]:
        return self.repository.get_all()

    def create(self, data: CouponCreate, actor: User) -> Coupon:
        if self.repository.get_by_code(data.code) is not None:
            raise BusinessRuleError("Já existe um cupom com esse código.")
        coupon = Coupon(**data.model_dump())
        self.repository.create(coupon)
        record_audit(self.db, self.tenant_id, actor, "COUPON_CREATED", "COUPON", coupon.id, coupon.code)
        self.db.commit()
        return coupon

    def update(self, coupon_id: UUID, data: CouponUpdate, actor: User) -> Coupon:
        coupon = self.repository.get_by_id(coupon_id)
        if coupon is None:
            raise NotFoundError("Cupom não encontrado.")
        for field in data.model_fields_set:
            setattr(coupon, field, getattr(data, field))
        if coupon.kind is CouponKind.PERCENT and coupon.value > 100:
            raise BusinessRuleError("O desconto percentual não pode passar de 100%.")
        self.repository.update(coupon)
        record_audit(self.db, self.tenant_id, actor, "COUPON_UPDATED", "COUPON", coupon.id, coupon.code)
        self.db.commit()
        return coupon

    def delete(self, coupon_id: UUID, actor: User) -> None:
        coupon = self.repository.get_by_id(coupon_id)
        if coupon is None:
            raise NotFoundError("Cupom não encontrado.")
        record_audit(self.db, self.tenant_id, actor, "COUPON_DELETED", "COUPON", coupon.id, coupon.code)
        self.repository.delete(coupon)
        self.db.commit()
