"""Error reporting (Sentry). Off unless SENTRY_DSN is set.

Privacy (LGPD): no request bodies, cookies, headers with credentials or user data are sent; only the error,
the stack trace and the route. Customer names, phones and addresses never leave the server this way.
"""
from app.core.config import settings

_SECRET_KEYS = ("authorization", "cookie", "password", "token", "access_token", "asaas-access-token", "x-api-key")


def _scrub(event, _hint):
    request = event.get("request") or {}
    request.pop("data", None)
    request.pop("cookies", None)
    request.pop("query_string", None)
    headers = request.get("headers") or {}
    for key in list(headers):
        if key.lower() in _SECRET_KEYS:
            headers[key] = "[removido]"
    event.pop("user", None)
    return event


def init_monitoring() -> None:
    if not settings.sentry_dsn:
        return
    import sentry_sdk

    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.environment,
        send_default_pii=False,
        max_request_body_size="never",
        traces_sample_rate=0.0,  # errors only (the free tier is for error alerts)
        before_send=_scrub,
    )
