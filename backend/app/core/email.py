"""Transactional e-mail through Resend (https://resend.com). Without RESEND_API_KEY nothing is sent:
in development the message is logged so links can be followed; in production a warning is logged."""
import json
import logging
import urllib.request

from app.core.config import settings

logger = logging.getLogger(__name__)


def send_email(to: str, subject: str, html: str, text: str) -> bool:
    if not settings.resend_api_key:
        if settings.is_production:
            logger.warning("E-mail not sent (RESEND_API_KEY missing): %s", subject)
        else:
            logger.info("E-mail (dev, not sent) to %s: %s\n%s", to, subject, text)
        return False
    request = urllib.request.Request(
        "https://api.resend.com/emails",
        data=json.dumps({"from": settings.email_from, "to": [to], "subject": subject, "html": html, "text": text}).encode(),
        headers={"Authorization": f"Bearer {settings.resend_api_key}", "Content-Type": "application/json", "User-Agent": "mesa-digital"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:  # noqa: S310 - fixed https host
            return 200 <= response.status < 300
    except Exception:
        logger.exception("Failed to send e-mail: %s", subject)
        return False
