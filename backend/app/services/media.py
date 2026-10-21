"""Image uploads: validated with Pillow, resized and re-encoded as WebP.

Stored in Cloudflare R2 when it is configured (served straight from the bucket's public address), otherwise in
the database (served by /media/<id>). Either way a `media` row tracks the size for the per-tenant quota.
"""
import io
import logging
import uuid
from uuid import UUID

from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy import event, func, select
from sqlalchemy.orm import Session

from app.core import storage
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
logger = logging.getLogger(__name__)


def media_id_from_url(url: str | None) -> UUID | None:
    """The media id behind an image link we issued: /media/<id> or <bucket url>/<tenant>/<id>.webp."""
    if not url:
        return None
    if url.startswith(MEDIA_PREFIX):
        candidate = url[len(MEDIA_PREFIX):]
    elif settings.media_public_url and url.startswith(settings.media_public_url.rstrip("/") + "/"):
        candidate = url.rsplit("/", 1)[-1].removesuffix(".webp")
    else:
        return None
    try:
        return UUID(candidate)
    except ValueError:
        return None


def media_url(media: Media) -> str:
    return storage.public_url(media.storage_key) if media.storage_key else f"{MEDIA_PREFIX}{media.id}"


def _delete_after_commit(db: Session, key: str) -> None:
    """Removes the bucket object only once the database change is committed (a rollback keeps the image)."""
    pending = db.info.setdefault("r2_pending_deletes", [])
    if not pending:

        @event.listens_for(db, "after_commit", once=True)
        def _purge(session):
            for stale in session.info.pop("r2_pending_deletes", []):
                try:
                    storage.delete_object(stale)
                except Exception:  # the row is gone; a leftover file only costs storage
                    logger.warning("Could not delete %s from object storage", stale, exc_info=True)

    pending.append(key)


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

        if settings.object_storage_enabled:
            media_id = uuid.uuid4()
            key = f"{self.tenant_id}/{media_id}.webp"
            try:
                storage.put_object(key, data, "image/webp")
            except Exception as error:
                logger.exception("Upload to object storage failed")
                raise BusinessRuleError("Não foi possível salvar a imagem agora. Tente novamente.") from error
            media = Media(id=media_id, tenant_id=self.tenant_id, content_type="image/webp", size=len(data), storage_key=key)
        else:
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
                if media.storage_key:
                    _delete_after_commit(self.db, media.storage_key)
                self.db.delete(media)
