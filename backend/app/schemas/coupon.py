from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.coupon import CouponKind


def _clean_code(value: str) -> str:
    code = "".join(value.split()).upper()
    if not code.replace("-", "").replace("_", "").isalnum():
        raise ValueError("O código deve ter só letras, números, hífen ou sublinhado.")
    return code


class CouponCreate(BaseModel):
    code: str = Field(min_length=3, max_length=40)
    kind: CouponKind
    value: Decimal = Field(gt=0, max_digits=10, decimal_places=2)
    min_order: Decimal = Field(default=Decimal("0"), ge=0, max_digits=10, decimal_places=2)
    max_uses: int | None = Field(default=None, ge=1, le=1_000_000)
    expires_at: datetime | None = None
    active: bool = True

    @field_validator("code")
    @classmethod
    def _normalize_code(cls, value: str) -> str:
        return _clean_code(value)

    @model_validator(mode="after")
    def _check_percent(self) -> "CouponCreate":
        if self.kind is CouponKind.PERCENT and self.value > 100:
            raise ValueError("O desconto percentual não pode passar de 100%.")
        return self


class CouponUpdate(BaseModel):
    value: Decimal | None = Field(default=None, gt=0, max_digits=10, decimal_places=2)
    min_order: Decimal | None = Field(default=None, ge=0, max_digits=10, decimal_places=2)
    max_uses: int | None = Field(default=None, ge=1, le=1_000_000)
    expires_at: datetime | None = None
    active: bool | None = None


class CouponResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    kind: CouponKind
    value: Decimal
    min_order: Decimal
    max_uses: int | None
    used_count: int
    expires_at: datetime | None
    active: bool
    created_at: datetime
