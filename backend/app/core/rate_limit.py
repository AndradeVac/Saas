"""Per-client rate limiter used as a FastAPI dependency.

Counts live in Postgres (fixed windows, one upsert per check), so every app machine and worker sees the same
attempts. If the database cannot be reached, it falls back to an in-process counter instead of failing open.
Keys use the real client IP (see app.core.client_ip; forwarded headers sent by the
visitor are ignored). Tenant routes also add the tenant, so one busy restaurant behind
a shared NAT does not lock out the others; platform routes (sign-up, address check)
key on the IP alone, otherwise changing the X-Tenant header would reset the counter.
"""
import logging
import time
from collections import defaultdict, deque
from datetime import datetime, timezone
from threading import Lock

from fastapi import HTTPException, Request, status
from sqlalchemy import text

from app.core.client_ip import client_ip

logger = logging.getLogger(__name__)

_UPSERT = text("""
    INSERT INTO rate_limits (key, window_start, hits) VALUES (:key, :window, 1)
    ON CONFLICT (key) DO UPDATE SET
        hits = CASE WHEN rate_limits.window_start = EXCLUDED.window_start THEN rate_limits.hits + 1 ELSE 1 END,
        window_start = EXCLUDED.window_start
    RETURNING hits
""")


class RateLimiter:
    def __init__(self, max_requests: int, window_seconds: int, per_tenant: bool = True, name: str = ""):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.per_tenant = per_tenant
        self.name = name or f"rl{max_requests}-{window_seconds}"
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def _refuse(self) -> None:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Muitas tentativas. Aguarde um instante e tente novamente.",
            headers={"Retry-After": str(self.window_seconds)},
        )

    def _shared_hits(self, key: str) -> int | None:
        from app.core.database import SessionLocal

        now = datetime.now(timezone.utc).timestamp()
        window = datetime.fromtimestamp(now - now % self.window_seconds, tz=timezone.utc)
        try:
            with SessionLocal() as db:
                hits = db.execute(_UPSERT, {"key": f"{self.name}|{key}"[:200], "window": window}).scalar_one()
                db.commit()
                return int(hits)
        except Exception:
            logger.warning("Shared rate limit unavailable; using the in-process counter", exc_info=True)
            return None

    def __call__(self, request: Request) -> None:
        tenant = request.headers.get("x-tenant", "").strip().lower()[:40] if self.per_tenant else ""
        key = f"{client_ip(request)}|{tenant}"
        shared = self._shared_hits(key)
        if shared is not None:
            if shared > self.max_requests:
                self._refuse()
            return
        now = time.monotonic()
        with self._lock:
            hits = self._hits[key]
            while hits and now - hits[0] > self.window_seconds:
                hits.popleft()
            if len(hits) >= self.max_requests:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Muitas tentativas. Aguarde um instante e tente novamente.",
                    headers={"Retry-After": str(self.window_seconds)},
                )
            hits.append(now)

    def reset(self) -> None:
        from app.core.database import SessionLocal

        with self._lock:
            self._hits.clear()
        try:
            with SessionLocal() as db:
                db.execute(text("DELETE FROM rate_limits WHERE key LIKE :prefix"), {"prefix": f"{self.name}|%"})
                db.commit()
        except Exception:
            pass


def purge_old_counters() -> None:
    """Hourly: drops counters of windows that ended long ago."""
    from app.core.database import SessionLocal

    with SessionLocal() as db:
        db.execute(text("DELETE FROM rate_limits WHERE window_start < now() - interval '1 day'"))
        db.commit()


login_rate_limit = RateLimiter(max_requests=10, window_seconds=60, name="login")
signup_rate_limit = RateLimiter(max_requests=5, window_seconds=600, per_tenant=False, name="signup")
password_reset_rate_limit = RateLimiter(max_requests=5, window_seconds=900, name="password_reset")
slug_check_rate_limit = RateLimiter(max_requests=30, window_seconds=60, per_tenant=False, name="slug_check")
public_order_rate_limit = RateLimiter(max_requests=20, window_seconds=60, name="public_order")
public_lookup_rate_limit = RateLimiter(max_requests=60, window_seconds=60, name="public_lookup")
menu_import_rate_limit = RateLimiter(max_requests=6, window_seconds=3600, name="menu_import")  # each reading costs money
