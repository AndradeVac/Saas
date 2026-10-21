"""Table labels and the secret code printed in each table's QR Code.

The code proves the customer is looking at the QR Code on that table: without it, anyone who knew a table number
could read that table's bill or add orders to it. It is an HMAC of the label with a per-tenant secret, so it never
needs to be stored and changing the secret invalidates every printed QR Code at once.
"""
import base64
import hashlib
import hmac
import re

_PREFIX = re.compile(r"^(mesa|table|mesas|n[ºo°]\.?)\s*", re.IGNORECASE)


def normalize_table_label(value: str | None) -> str | None:
    """'07', ' Mesa 7 ', 'mesa 7' and '7' are the same table: '7'. Other names keep their text ('Varanda 2')."""
    if value is None:
        return None
    label = " ".join(value.split())
    label = _PREFIX.sub("", label).strip(" -#")
    if label.isdigit():
        label = str(int(label))
    return label[:30] or None


def table_code(secret: str, label: str) -> str:
    digest = hmac.new(secret.encode(), normalize_table_label(label).encode(), hashlib.sha256).digest()
    return base64.b32encode(digest).decode()[:8].lower()


def valid_table_code(secret: str, label: str | None, code: str | None) -> bool:
    if not label or not code:
        return False
    return hmac.compare_digest(table_code(secret, label), code.strip().lower())
