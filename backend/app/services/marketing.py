"""Ready-to-print marketing material with the store's brand: table cards with each table's QR Code, a window
poster and a square Instagram post. Takes away the "how do I spread the word" friction."""
from __future__ import annotations

import io
from urllib.parse import quote

from PIL import Image, ImageDraw, ImageFilter, ImageOps
from reportlab.graphics import renderPDF
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.og import _font, _hex, _media_image
from app.core.tables import normalize_table_label, table_code
from app.models.tenant import Tenant


def _qr(c: canvas.Canvas, value: str, x: float, y: float, size: float) -> None:
    widget = QrCodeWidget(value, barLevel="M")
    left, bottom, right, top = widget.getBounds()
    drawing = Drawing(size, size, transform=[size / (right - left), 0, 0, size / (top - bottom), 0, 0])
    drawing.add(widget)
    renderPDF.draw(drawing, c, x, y)


def _logo(db: Session, tenant: Tenant) -> ImageReader | None:
    image = _media_image(db, tenant, tenant.logo_url)
    if image is None:
        return None
    output = io.BytesIO()
    image.save(output, format="PNG")
    output.seek(0)
    return ImageReader(output)


def table_cards_pdf(db: Session, tenant: Tenant, labels: list[str]) -> bytes:
    """Four A6 cards per A4 page (cut along the lines), one per table, each with its own QR Code."""
    brand = colors.HexColor("#%02x%02x%02x" % _hex(tenant.primary_color))
    logo = _logo(db, tenant)
    output = io.BytesIO()
    c = canvas.Canvas(output, pagesize=A4)
    c.setTitle(f"{tenant.name.strip()} - QR Codes das mesas")
    width, height = A4
    card_w, card_h = width / 2, height / 2
    tables = [label for label in (normalize_table_label(raw) for raw in labels) if label]
    for index, label in enumerate(tables):
        if index and index % 4 == 0:
            c.showPage()
        col, row = index % 2, (index // 2) % 2
        x0, y0 = col * card_w, height - (row + 1) * card_h
        c.setStrokeColor(colors.HexColor("#d4d4d4"))
        c.setDash(3, 3)
        c.rect(x0, y0, card_w, card_h)
        c.setDash()
        c.setFillColor(brand)
        c.rect(x0, y0 + card_h - 34 * mm, card_w, 34 * mm, stroke=0, fill=1)
        text_x = x0 + 10 * mm
        if logo:
            c.setFillColor(colors.white)
            c.roundRect(x0 + 8 * mm, y0 + card_h - 29 * mm, 24 * mm, 24 * mm, 3 * mm, stroke=0, fill=1)
            c.drawImage(logo, x0 + 9.5 * mm, y0 + card_h - 27.5 * mm, 21 * mm, 21 * mm, mask="auto", preserveAspectRatio=True)
            text_x = x0 + 37 * mm
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 15)
        c.drawString(text_x, y0 + card_h - 16 * mm, tenant.name.strip()[:26])
        c.setFont("Helvetica", 10)
        c.drawString(text_x, y0 + card_h - 23 * mm, "Cardápio digital")
        c.setFillColor(colors.HexColor("#111111"))
        c.setFont("Helvetica-Bold", 24)
        c.drawCentredString(x0 + card_w / 2, y0 + card_h - 48 * mm, f"Mesa {label}")
        url = settings.tenant_url(tenant.slug, f"/?mesa={quote(label)}&k={table_code(tenant.table_secret, label)}")
        _qr(c, url, x0 + card_w / 2 - 30 * mm, y0 + 30 * mm, 60 * mm)
        c.setFont("Helvetica-Bold", 12)
        c.drawCentredString(x0 + card_w / 2, y0 + 22 * mm, "Aponte a câmera do celular")
        c.setFont("Helvetica", 10)
        c.setFillColor(colors.HexColor("#555555"))
        c.drawCentredString(x0 + card_w / 2, y0 + 16 * mm, "Veja o cardápio, peça e pague pelo celular")
        c.setFont("Helvetica", 7)
        c.drawCentredString(x0 + card_w / 2, y0 + 7 * mm, "mesadig.com.br")
    c.save()
    return output.getvalue()


def poster_pdf(db: Session, tenant: Tenant) -> bytes:
    """A4 poster for the window / counter: big QR Code to the menu."""
    brand = colors.HexColor("#%02x%02x%02x" % _hex(tenant.primary_color))
    logo = _logo(db, tenant)
    output = io.BytesIO()
    c = canvas.Canvas(output, pagesize=A4)
    c.setTitle(f"{tenant.name.strip()} - Cartaz")
    width, height = A4
    c.setFillColor(brand)
    c.rect(0, height - 80 * mm, width, 80 * mm, stroke=0, fill=1)
    if logo:
        c.setFillColor(colors.white)
        c.roundRect(width / 2 - 20 * mm, height - 52 * mm, 40 * mm, 40 * mm, 5 * mm, stroke=0, fill=1)
        c.drawImage(logo, width / 2 - 17 * mm, height - 49 * mm, 34 * mm, 34 * mm, mask="auto", preserveAspectRatio=True)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 26)
    c.drawCentredString(width / 2, height - 68 * mm, tenant.name.strip()[:30])
    c.setFillColor(colors.HexColor("#111111"))
    c.setFont("Helvetica-Bold", 34)
    c.drawCentredString(width / 2, height - 105 * mm, "Peça pelo celular")
    c.setFont("Helvetica", 15)
    c.setFillColor(colors.HexColor("#444444"))
    c.drawCentredString(width / 2, height - 116 * mm, "Sem fila, sem aplicativo: aponte a câmera para o código")
    _qr(c, settings.tenant_url(tenant.slug, "/"), width / 2 - 45 * mm, 62 * mm, 90 * mm)
    c.setFont("Helvetica-Bold", 14)
    c.setFillColor(brand)
    c.drawCentredString(width / 2, 50 * mm, settings.tenant_url(tenant.slug, "/").replace("https://", "").rstrip("/"))
    c.setFont("Helvetica", 12)
    c.setFillColor(colors.HexColor("#555555"))
    c.drawCentredString(width / 2, 38 * mm, "1. Aponte a câmera   2. Escolha   3. Peça e pague pelo celular")
    c.save()
    return output.getvalue()


def instagram_png(db: Session, tenant: Tenant) -> bytes:
    """1080x1080 post: cover photo, logo, name and the menu address."""
    size = 1080
    brand = _hex(tenant.primary_color)
    cover = _media_image(db, tenant, tenant.cover_url)
    if cover is not None:
        canvas_img = ImageOps.fit(cover.convert("RGB"), (size, size)).filter(ImageFilter.GaussianBlur(1)).convert("RGBA")
        shade = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw_shade = ImageDraw.Draw(shade)
        for y in range(size):
            draw_shade.line([(0, y), (size, y)], fill=(0, 0, 0, int(30 + 190 * (y / size) ** 1.4)))
        canvas_img = Image.alpha_composite(canvas_img, shade)
    else:
        canvas_img = Image.new("RGBA", (size, size), brand + (255,))
    draw = ImageDraw.Draw(canvas_img)
    logo = _media_image(db, tenant, tenant.logo_url)
    if logo is not None:
        badge = Image.new("RGBA", (190, 190), (255, 255, 255, 255))
        mask = Image.new("L", badge.size, 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, 190, 190), radius=36, fill=255)
        inner = ImageOps.contain(logo, (166, 166))
        badge.paste(inner, ((190 - inner.width) // 2, (190 - inner.height) // 2), inner)
        canvas_img.paste(badge, (70, 560), mask)
    name = tenant.name.strip()
    draw.text((70, 820), name[:30], font=_font(84 if len(name) <= 18 else 62), fill="white", anchor="ls")
    draw.text((70, 890), "Agora você pede pelo celular!", font=_font(44), fill="white", anchor="ls")
    url = settings.tenant_url(tenant.slug, "/").replace("https://", "").replace("http://", "").rstrip("/")
    font = _font(36)
    draw.rounded_rectangle((70, 930, 70 + int(font.getlength(url)) + 60, 1010), radius=40, fill=brand + (255,))
    draw.text((100, 970), url, font=font, fill="white", anchor="lm")
    output = io.BytesIO()
    canvas_img.convert("RGB").save(output, format="PNG", optimize=True)
    return output.getvalue()
