"""Link previews (WhatsApp, Instagram, Facebook): each store's page gets its own title, description and a
1200x630 image composed from its cover, logo and name. Crawlers do not run JavaScript, so this is server-side."""
from __future__ import annotations

import html
import io
import time
from uuid import UUID

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.media import Media
from app.models.tenant import Tenant
from app.services.media import MEDIA_PREFIX

OG_SIZE = (1200, 630)
_FONTS = ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/System/Library/Fonts/Supplemental/Arial Bold.ttf")
_cache: dict[str, tuple[float, bytes]] = {}
CACHE_SECONDS = 600


def _font(size: int):
    for path in _FONTS:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _media_image(db: Session, tenant: Tenant, url: str | None) -> Image.Image | None:
    if not url or not url.startswith(MEDIA_PREFIX):
        return None
    try:
        media = db.scalar(select(Media).where(Media.id == UUID(url.removeprefix(MEDIA_PREFIX)), Media.tenant_id == tenant.id))
        return Image.open(io.BytesIO(media.data)).convert("RGBA") if media is not None and media.data else None
    except Exception:
        return None


def _hex(color: str | None) -> tuple[int, int, int]:
    color = (color or "#c2410c").lstrip("#")
    try:
        return tuple(int(color[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]
    except ValueError:
        return (194, 65, 12)


def og_image(db: Session, tenant: Tenant) -> bytes:
    key = f"{tenant.id}:{tenant.updated_at.timestamp() if tenant.updated_at else 0}"
    cached = _cache.get(key)
    if cached and time.monotonic() - cached[0] < CACHE_SECONDS:
        return cached[1]

    width, height = OG_SIZE
    brand = _hex(tenant.primary_color)
    cover = _media_image(db, tenant, tenant.cover_url)
    if cover is not None:
        canvas = ImageOps.fit(cover.convert("RGB"), OG_SIZE, method=Image.Resampling.LANCZOS)
        canvas = canvas.filter(ImageFilter.GaussianBlur(1))
        shade = Image.new("RGBA", OG_SIZE, (0, 0, 0, 0))
        gradient = ImageDraw.Draw(shade)
        for y in range(height):  # dark at the bottom so the name always reads
            gradient.line([(0, y), (width, y)], fill=(0, 0, 0, int(40 + 175 * (y / height))))
        canvas = Image.alpha_composite(canvas.convert("RGBA"), shade)
    else:
        canvas = Image.new("RGBA", OG_SIZE, brand + (255,))
    draw = ImageDraw.Draw(canvas)

    x = 64
    logo = _media_image(db, tenant, tenant.logo_url)
    if logo is not None:
        size = 150
        badge = Image.new("RGBA", (size + 16, size + 16), (255, 255, 255, 255))
        mask = Image.new("L", badge.size, 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, *badge.size), radius=28, fill=255)
        badge.paste(ImageOps.contain(logo, (size, size)), (8, 8), ImageOps.contain(logo, (size, size)))
        canvas.paste(badge, (x, height - 64 - badge.size[1]), mask)
        x += badge.size[0] + 32

    name = tenant.name.strip()
    title = _font(76 if len(name) <= 22 else 58)
    draw.text((x, height - 150), name[:40], font=title, fill="white", anchor="ls")
    draw.text((x, height - 92), "Peça pelo cardápio digital", font=_font(36), fill=(255, 255, 255, 230), anchor="ls")
    draw.rounded_rectangle((width - 300, 48, width - 48, 104), radius=28, fill=brand + (255,))
    draw.text((width - 174, 77), "Ver cardápio", font=_font(28), fill="white", anchor="mm")

    output = io.BytesIO()
    canvas.convert("RGB").save(output, format="JPEG", quality=84)
    data = output.getvalue()
    _cache.clear() if len(_cache) > 500 else None
    _cache[key] = (time.monotonic(), data)
    return data


def meta_tags(title: str, description: str, image: str, url: str) -> str:
    title, description = html.escape(title), html.escape(description)
    return (
        f'<title>{title}</title>\n'
        f'    <meta name="description" content="{description}" />\n'
        f'    <meta property="og:type" content="website" />\n'
        f'    <meta property="og:site_name" content="Mesa Digital" />\n'
        f'    <meta property="og:title" content="{title}" />\n'
        f'    <meta property="og:description" content="{description}" />\n'
        f'    <meta property="og:image" content="{html.escape(image)}" />\n'
        f'    <meta property="og:image:width" content="1200" />\n'
        f'    <meta property="og:image:height" content="630" />\n'
        f'    <meta property="og:url" content="{html.escape(url)}" />\n'
        f'    <meta name="twitter:card" content="summary_large_image" />'
    )
