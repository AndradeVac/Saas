"""Production entry point: one process serves the API under /api and the built frontend everywhere else.

    uvicorn app.web:web

Every tenant subdomain (<slug>.<domain>) and the platform site share this app; the frontend reads the
subdomain and calls /api on the same origin, so there is no CORS round-trip in production.
Locally keep using `uvicorn app.main:app` + Vite.
"""
import os
import re
import time
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.og import meta_tags, og_image
from app.main import app as api
from app.models.tenant import Tenant, TenantStatus

FRONTEND_DIR = Path(os.getenv("FRONTEND_DIST", Path(__file__).resolve().parents[2] / "frontend" / "dist"))

web = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)


@web.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    headers = response.headers
    headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    headers.setdefault("X-Content-Type-Options", "nosniff")
    headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=(), payment=()")
    # Only our own pages may frame the app (the landing page shows a menu inside a phone mockup): blocks
    # clickjacking of the panel by other sites.
    headers.setdefault("Content-Security-Policy", f"frame-ancestors 'self' https://{settings.root_domain} https://*.{settings.root_domain}")
    return response


@web.on_event("startup")
async def start_background_jobs() -> None:
    """Every hour: lifecycle e-mails (each goes out once, so several processes running this is fine) and housekeeping."""
    import asyncio

    from fastapi.concurrency import run_in_threadpool

    from app.core.rate_limit import purge_old_counters
    from app.services import lifecycle
    from app.services.access_log import purge_old_access_logs
    from app.services.tab import expire_forgotten_tabs

    enabled = settings.background_jobs if settings.background_jobs is not None else settings.is_production
    if not enabled:
        return

    async def loop() -> None:
        await asyncio.sleep(60)  # let the app finish booting
        while True:
            try:
                await run_in_threadpool(lifecycle.run)
                await run_in_threadpool(purge_old_counters)
                await run_in_threadpool(expire_forgotten_tabs)
                await run_in_threadpool(purge_old_access_logs)
            except Exception:  # never let the loop die
                import logging

                logging.getLogger(__name__).exception("Background jobs failed")
            await asyncio.sleep(3600)

    asyncio.get_running_loop().create_task(loop())


web.mount("/api", api)


@web.api_route("/health", methods=["GET", "HEAD"], include_in_schema=False)
def health():
    """Process liveness for the platform's health checks (the database check lives at /api/health)."""
    return {"status": "ok"}


if (FRONTEND_DIR / "index.html").exists():
    # Vite fingerprints everything under /assets, so it can be cached forever.
    web.mount("/assets", StaticFiles(directory=FRONTEND_DIR / "assets"), name="assets")

    @web.middleware("http")
    async def cache_assets(request, call_next):
        response = await call_next(request)
        if request.url.path.startswith("/assets/") and response.status_code == 200:
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return response

    INDEX = (FRONTEND_DIR / "index.html").read_text()
    _HEAD = re.compile(r"\s*(<title>.*?</title>|<meta name=\"description\"[^>]*>)", re.S)
    BASE = _HEAD.sub("", INDEX)  # the shell without its generic title/description
    PLATFORM_DESCRIPTION = "Cardápio digital com QR Code, pedidos pelo celular e comanda por mesa. Sem comissão por pedido. Teste grátis por 14 dias."
    _pages: dict[str, tuple[float, str]] = {}

    def _slug(request: Request) -> str | None:
        host = (request.headers.get("host") or "").split(":")[0].lower()
        suffix = f".{settings.root_domain}"
        return host[: -len(suffix)] if host.endswith(suffix) and host.count(".") >= settings.root_domain.count(".") + 1 else None

    def _page(request: Request) -> str:
        """index.html with the link-preview tags of the store (or of the platform)."""
        slug = _slug(request)
        cached = _pages.get(slug or "")
        if cached and time.monotonic() - cached[0] < 60:
            return cached[1]
        base = f"https://{request.headers.get('host', settings.root_domain)}"
        tags = meta_tags("Mesa Digital · Cardápio digital e pedidos para restaurantes", PLATFORM_DESCRIPTION, f"https://{settings.root_domain}/og-image.jpg", base + "/")
        if slug:
            with SessionLocal() as db:
                tenant = db.scalar(select(Tenant).where(Tenant.slug == slug))
            if tenant is not None and tenant.status is not TenantStatus.SUSPENDED:
                name = tenant.name.strip()
                description = (tenant.description or f"Veja o cardápio de {name} e peça pelo celular.").strip()
                version = int(tenant.updated_at.timestamp()) if tenant.updated_at else 0
                tags = meta_tags(f"{name} · Cardápio digital", description, f"{base}/og/{slug}.jpg?v={version}", base + "/")
        page = BASE.replace("</head>", f"    {tags}\n  </head>", 1) if "</head>" in BASE else tags + BASE
        if len(_pages) > 1000:
            _pages.clear()
        _pages[slug or ""] = (time.monotonic(), page)
        return page

    @web.get("/og/{slug}.jpg", include_in_schema=False)
    def store_preview_image(slug: str) -> Response:
        with SessionLocal() as db:
            tenant = db.scalar(select(Tenant).where(Tenant.slug == slug))
            if tenant is None:
                return Response(status_code=404)
            data = og_image(db, tenant)
        return Response(data, media_type="image/jpeg", headers={"Cache-Control": "public, max-age=3600"})

    # HEAD too: uptime monitors and link previews probe pages with it.
    @web.api_route("/{path:path}", methods=["GET", "HEAD"], include_in_schema=False)
    def spa(path: str, request: Request) -> Response:
        """Files from the build (favicon, robots.txt…) or the app shell for client-side routes."""
        candidate = (FRONTEND_DIR / path).resolve()
        if path and candidate.is_file() and FRONTEND_DIR.resolve() in candidate.parents:
            return FileResponse(candidate)
        try:
            return HTMLResponse(_page(request), headers={"Cache-Control": "no-cache"})
        except Exception:  # a database hiccup must never take the site down
            return FileResponse(FRONTEND_DIR / "index.html", headers={"Cache-Control": "no-cache"})
