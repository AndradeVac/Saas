from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ProductCreate(BaseModel):
    category_id: UUID
    name: str = Field(min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=1000)
    image_url: str | None = Field(default=None, max_length=300)
    price: Decimal = Field(ge=0, max_digits=10, decimal_places=2)
    featured: bool = False


class ProductUpdate(BaseModel):
    category_id: UUID | None = None
    name: str | None = Field(default=None, min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=1000)
    image_url: str | None = Field(default=None, max_length=300)
    price: Decimal | None = Field(default=None, ge=0, max_digits=10, decimal_places=2)
    featured: bool | None = None
    active: bool | None = None


class ProductResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    category_id: UUID
    name: str
    description: str | None
    image_url: str | None = None
    price: Decimal
    featured: bool
    active: bool
    created_at: datetime
    updated_at: datetime
