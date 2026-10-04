from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    image_url: str | None = Field(default=None, max_length=300)
    sort_order: int = Field(default=0, ge=0, le=1000)


class CategoryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    image_url: str | None = Field(default=None, max_length=300)
    sort_order: int | None = Field(default=None, ge=0, le=1000)
    active: bool | None = None


class CategoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    image_url: str | None = None
    sort_order: int
    active: bool
    created_at: datetime
    updated_at: datetime
