"""Small in-memory, per-client rate limiter used as a FastAPI dependency.

State lives in the process, which matches the single-instance deployment. If the
API is ever scaled to several instances, move this to a shared store (e.g. Redis).
The key combines the client IP with the tenant so one busy restaurant behind a
shared NAT does not lock out the others.
"""
import time
from collections import defaultdict, deque
from threading import Lock

from fastapi import HTTPException, Request, status


class RateLimiter:
    def __init__(self, max_requests: int, window_seconds: int):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def __call__(self, request: Request) -> None:
        client = request.client.host if request.client else "unknown"
        key = f"{client}|{request.headers.get('x-tenant', '')}"
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
        with self._lock:
            self._hits.clear()


login_rate_limit = RateLimiter(max_requests=10, window_seconds=60)
signup_rate_limit = RateLimiter(max_requests=5, window_seconds=600)
slug_check_rate_limit = RateLimiter(max_requests=30, window_seconds=60)
public_order_rate_limit = RateLimiter(max_requests=20, window_seconds=60)
public_lookup_rate_limit = RateLimiter(max_requests=60, window_seconds=60)
