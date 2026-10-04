from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.common import safe_image_url


class _ImageMixin(BaseModel):
    @field_validator("image_url", check_fields=False)
    @classmethod
    def _image(cls, value: str | None) -> str | None:
        return safe_image_url(value)


class CategoryCreate(_ImageMixin):
    name: str = Field(min_length=1, max_length=80)
    image_url: str | None = Field(default=None, max_length=300)
    sort_order: int = Field(default=0, ge=0, le=1000)


class CategoryUpdate(_ImageMixin):
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
