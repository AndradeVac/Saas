from uuid import UUID

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.exceptions import NotFoundError
from app.core.security import admin_only
from app.models.media import Media
from app.models.user import User
from app.services.media import MediaService

router = APIRouter(tags=["Media"])


class UploadResult(BaseModel):
    url: str
    size: int
    used_bytes: int
    quota_bytes: int


@router.post("/media", response_model=UploadResult, status_code=201)
async def upload_image(file: UploadFile = File(...), db: Session = Depends(get_db), actor: User = Depends(admin_only)):
    # Read one byte past the limit so oversized uploads are rejected without buffering them entirely.
    raw = await file.read(settings.media_max_upload_mb * 1024 * 1024 + 1)
    service = MediaService(db, actor.tenant_id)
    media = service.save(raw)
    db.commit()
    return UploadResult(url=f"/media/{media.id}", size=media.size, used_bytes=service.used_bytes(), quota_bytes=service.quota_bytes())


@router.get("/media-usage", response_model=UploadResult)
def usage(db: Session = Depends(get_db), actor: User = Depends(admin_only)):
    service = MediaService(db, actor.tenant_id)
    return UploadResult(url="", size=0, used_bytes=service.used_bytes(), quota_bytes=service.quota_bytes())


@router.get("/media/{media_id}")
def get_image(media_id: UUID, db: Session = Depends(get_db)):
    """Public: <img> tags cannot send the tenant header, and the id is an unguessable UUID."""
    media = db.get(Media, media_id)
    if media is None:
        raise NotFoundError("Imagem não encontrada.")
    return Response(
        content=media.data,
        media_type=media.content_type,
        headers={"Cache-Control": "public, max-age=31536000, immutable", "X-Content-Type-Options": "nosniff"},
    )
