from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.common import safe_image_url


def _new_id() -> str:
    return uuid4().hex[:10]


class OptionItem(BaseModel):
    id: str = Field(default_factory=_new_id, max_length=40)
    name: str = Field(min_length=1, max_length=80)
    price: Decimal = Field(default=Decimal("0"), ge=0, le=100000, max_digits=10, decimal_places=2)
    active: bool = True


class OptionGroup(BaseModel):
    """A choice the customer makes on a product (size, extras, doneness...)."""

    id: str = Field(default_factory=_new_id, max_length=40)
    name: str = Field(min_length=1, max_length=80)
    required: bool = False
    min: int = Field(default=0, ge=0, le=40)
    max: int = Field(default=1, ge=1, le=40)
    options: list[OptionItem] = Field(min_length=1, max_length=40)

    @model_validator(mode="after")
    def _check_limits(self) -> "OptionGroup":
        if self.required and self.min < 1:
            self.min = 1
        if self.max < self.min:
            raise ValueError(f"Em “{self.name}”, o máximo não pode ser menor que o mínimo.")
        active = sum(1 for option in self.options if option.active)
        if self.min > active:
            raise ValueError(f"Em “{self.name}”, o mínimo é maior que a quantidade de opções ativas.")
        if len({option.id for option in self.options}) != len(self.options):
            raise ValueError("Opções duplicadas.")
        return self


def _unique_groups(groups: list[OptionGroup] | None) -> list[OptionGroup] | None:
    if groups is not None and len({group.id for group in groups}) != len(groups):
        raise ValueError("Grupos de opções duplicados.")
    return groups


class ProductCreate(BaseModel):
    category_id: UUID
    name: str = Field(min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=1000)
    image_url: str | None = Field(default=None, max_length=300)
    price: Decimal = Field(ge=0, max_digits=10, decimal_places=2)
    featured: bool = False
    available: bool = True
    sort_order: int = Field(default=0, ge=0, le=100000)
    options: list[OptionGroup] = Field(default_factory=list, max_length=12)

    @field_validator("image_url")
    @classmethod
    def _image(cls, value: str | None) -> str | None:
        return safe_image_url(value)

    @field_validator("options")
    @classmethod
    def _groups(cls, value):
        return _unique_groups(value)


class ProductUpdate(BaseModel):
    category_id: UUID | None = None
    name: str | None = Field(default=None, min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=1000)
    image_url: str | None = Field(default=None, max_length=300)
    price: Decimal | None = Field(default=None, ge=0, max_digits=10, decimal_places=2)
    featured: bool | None = None
    available: bool | None = None
    active: bool | None = None
    sort_order: int | None = Field(default=None, ge=0, le=100000)
    options: list[OptionGroup] | None = Field(default=None, max_length=12)

    @field_validator("image_url")
    @classmethod
    def _image(cls, value: str | None) -> str | None:
        return safe_image_url(value)

    @field_validator("options")
    @classmethod
    def _groups(cls, value):
        return _unique_groups(value)


class ProductResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    category_id: UUID
    name: str
    description: str | None
    image_url: str | None = None
    price: Decimal
    featured: bool
    available: bool
    active: bool
    sort_order: int
    options: list[OptionGroup]
    created_at: datetime
    updated_at: datetime
