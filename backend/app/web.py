"""Production entry point: one process serves the API under /api and the built frontend everywhere else.

    uvicorn app.web:web

Every tenant subdomain (<slug>.<domain>) and the platform site share this app; the frontend reads the
subdomain and calls /api on the same origin, so there is no CORS round-trip in production.
Locally keep using `uvicorn app.main:app` + Vite.
"""
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.main import app as api

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

    # HEAD too: uptime monitors and link previews probe pages with it.
    @web.api_route("/{path:path}", methods=["GET", "HEAD"], include_in_schema=False)
    def spa(path: str) -> Response:
        """Files from the build (favicon, robots.txt…) or the app shell for client-side routes."""
        candidate = (FRONTEND_DIR / path).resolve()
        if path and candidate.is_file() and FRONTEND_DIR.resolve() in candidate.parents:
            return FileResponse(candidate)
        return FileResponse(FRONTEND_DIR / "index.html", headers={"Cache-Control": "no-cache"})
