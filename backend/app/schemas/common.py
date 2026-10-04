from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int


def safe_image_url(value: str | None) -> str | None:
    """Image links are either an uploaded file (/media/<id>) or an http(s) URL; nothing else."""
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None
    if value.startswith("/media/") or value.lower().startswith(("http://", "https://")):
        return value
    raise ValueError("Informe um link de imagem válido (http/https) ou envie um arquivo.")
