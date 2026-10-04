"""Image uploads: validated with Pillow, resized, re-encoded as WebP and stored in the database."""
import io
from uuid import UUID

from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import BusinessRuleError
from app.models.category import Category
from app.models.media import Media
from app.models.product import Product
from app.models.tenant import Tenant

MAX_DIMENSION = 1200
MAX_PIXELS = 40_000_000  # refuses decompression bombs
MEDIA_PREFIX = "/media/"

Image.MAX_IMAGE_PIXELS = MAX_PIXELS


def media_id_from_url(url: str | None) -> UUID | None:
    if not url or not url.startswith(MEDIA_PREFIX):
        return None
    try:
        return UUID(url[len(MEDIA_PREFIX):])
    except ValueError:
        return None


class MediaService:
    def __init__(self, db: Session, tenant_id: UUID):
        self.db = db
        self.tenant_id = tenant_id

    def used_bytes(self) -> int:
        return int(self.db.scalar(select(func.coalesce(func.sum(Media.size), 0)).where(Media.tenant_id == self.tenant_id)) or 0)

    def quota_bytes(self) -> int:
        return settings.media_quota_mb * 1024 * 1024

    def save(self, raw: bytes) -> Media:
        if len(raw) > settings.media_max_upload_mb * 1024 * 1024:
            raise BusinessRuleError(f"A imagem deve ter no máximo {settings.media_max_upload_mb} MB.")
        try:
            image = Image.open(io.BytesIO(raw))
            image.load()
        except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as error:
            raise BusinessRuleError("Arquivo inválido. Envie uma imagem JPG, PNG ou WebP.") from error

        image = ImageOps.exif_transpose(image)
        image.thumbnail((MAX_DIMENSION, MAX_DIMENSION))
        if image.mode not in ("RGB", "RGBA"):
            image = image.convert("RGBA" if "transparency" in image.info else "RGB")
        output = io.BytesIO()
        image.save(output, format="WEBP", quality=82, method=4)
        data = output.getvalue()

        if self.used_bytes() + len(data) > self.quota_bytes():
            raise BusinessRuleError("Limite de armazenamento de imagens atingido. Remova imagens que não usa mais.")

        media = Media(tenant_id=self.tenant_id, content_type="image/webp", size=len(data), data=data)
        self.db.add(media)
        self.db.flush()
        return media

    def release_if_orphan(self, url: str | None) -> None:
        """Deletes an uploaded file once nothing in the tenant points at it anymore."""
        media_id = media_id_from_url(url)
        if media_id is None:
            return
        self.db.flush()
        references = sum(
            int(self.db.scalar(select(func.count()).select_from(model).where(model.tenant_id == self.tenant_id, column == url)) or 0)
            for model, column in ((Product, Product.image_url), (Category, Category.image_url))
        )
        tenant = self.db.get(Tenant, self.tenant_id)
        if tenant is not None and url in (tenant.logo_url, tenant.cover_url):
            references += 1
        if references == 0:
            media = self.db.get(Media, media_id)
            if media is not None and media.tenant_id == self.tenant_id:
                self.db.delete(media)
