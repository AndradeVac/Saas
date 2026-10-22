from decimal import Decimal

from pydantic import BaseModel, Field, model_validator


class ImportSize(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    price: Decimal = Field(ge=0, le=100000, max_digits=10, decimal_places=2)


class ImportProduct(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=1000)
    price: Decimal = Field(ge=0, le=100000, max_digits=10, decimal_places=2)
    sizes: list[ImportSize] = Field(default_factory=list, max_length=20)


class ImportCategory(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    products: list[ImportProduct] = Field(min_length=1, max_length=200)


class MenuImport(BaseModel):
    """The draft as reviewed by the owner: what will be created."""

    categories: list[ImportCategory] = Field(min_length=1, max_length=40)

    @model_validator(mode="after")
    def _total(self) -> "MenuImport":
        if sum(len(c.products) for c in self.categories) > 300:
            raise ValueError("Importe no máximo 300 produtos de uma vez.")
        return self


class MenuImportResult(BaseModel):
    created: int
    hidden: int  # created hidden because the plan's product limit was reached
    categories: int
