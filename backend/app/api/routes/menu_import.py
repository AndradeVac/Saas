from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from app.core import menu_ai
from app.core.database import get_db
from app.core.rate_limit import menu_import_rate_limit
from app.core.security import admin_only
from app.models.user import User
from app.schemas.menu_import import MenuImport, MenuImportResult
from app.services.menu_import import MenuImportService

router = APIRouter(prefix="/menu-import", tags=["Menu import"])


@router.post("/read", response_model=menu_ai.MenuDraft, dependencies=[Depends(menu_import_rate_limit)])
async def read_menu(files: list[UploadFile] = File(...), actor: User = Depends(admin_only)):
    """Photos (or a PDF) of a printed menu -> a draft for the owner to review. Saves nothing."""
    raw = [await file.read(menu_ai.MAX_FILE_MB * 1024 * 1024 + 1) for file in files[: menu_ai.MAX_FILES + 1]]
    return await run_in_threadpool(menu_ai.read_menu, raw)


@router.post("/apply", response_model=MenuImportResult)
def apply_menu(data: MenuImport, db: Session = Depends(get_db), actor: User = Depends(admin_only)):
    return MenuImportService(db, actor.tenant_id).apply(data, actor)
