import logging

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.routes import (
    analytics,
    audit,
    auth,
    categories,
    coupons,
    customers,
    media,
    orders,
    platform,
    products,
    public,
    tenant,
    users,
)
from app.core.config import settings
from app.core.database import get_db
from app.core.exceptions import register_exception_handlers
from app.core.logging_config import configure_logging

configure_logging()
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Mesa Digital API",
    version="1.0.0",
    # Interactive docs are only exposed outside production.
    docs_url=None if settings.is_production else "/docs",
    redoc_url=None,
    openapi_url=None if settings.is_production else "/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_exact_origins,
    allow_origin_regex=settings.cors_origin_regex,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Tenant"],
)

register_exception_handlers(app)

for module in (
    platform, auth, tenant, users, categories, products, customers, coupons, media, orders, public, analytics, audit,
):
    app.include_router(module.router)


@app.api_route("/", methods=["GET", "HEAD"], include_in_schema=False)
def root():
    return {"status": "ok", "service": "mesa-digital-api"}


@app.api_route("/health", methods=["GET", "HEAD"], include_in_schema=False)
def health(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        logger.exception("Health check failed: database unreachable")
        return JSONResponse(status_code=503, content={"status": "error", "database": "unreachable"})
    return {"status": "ok", "database": "ok"}
