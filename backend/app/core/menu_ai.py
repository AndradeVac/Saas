"""Reads photos (or a PDF) of a printed menu with Claude and returns a draft: categories, products and prices.

Nothing is saved here: the owner reviews the draft in the panel before anything is created.
"""
from __future__ import annotations

import base64
import io
import logging
from decimal import Decimal

import anthropic
from PIL import Image, ImageOps, UnidentifiedImageError
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.exceptions import BusinessRuleError

logger = logging.getLogger(__name__)

MODEL = "claude-opus-5-5"
MAX_FILES = 4
MAX_FILE_MB = 10
MAX_DIMENSION = 2400  # enough to read small print; larger photos only cost more

PROMPT = """Estas imagens são o cardápio de um restaurante brasileiro. Transcreva TODOS os itens à venda.

- Mantenha os nomes como estão escritos (corrija só caixa alta exagerada: "X-BACON" pode virar "X-Bacon").
- Agrupe nas categorias do próprio cardápio (ex.: Lanches, Espetinhos, Porções, Bebidas). Se o cardápio não tiver
  categorias, crie poucas e simples.
- description: só o que estiver escrito (ingredientes, acompanhamentos). Não invente.
- price: em reais, número com ponto decimal (R$ 25,90 -> 25.90). Se não der para ler o preço, use null.
- sizes: quando o mesmo item tiver preços por tamanho ou quantidade (P/M/G, 300 ml/600 ml, meia/inteira),
  liste cada um com seu preço e deixe price com o menor deles. Senão, lista vazia.
- Ignore textos que não são itens (endereço, telefone, horário, promoções sem preço)."""


class DraftSize(BaseModel):
    name: str
    price: float


class DraftProduct(BaseModel):
    name: str
    description: str | None = None
    price: float | None = None
    sizes: list[DraftSize] = Field(default_factory=list)


class DraftCategory(BaseModel):
    name: str
    products: list[DraftProduct]


class MenuDraft(BaseModel):
    categories: list[DraftCategory]


def enabled() -> bool:
    return bool(settings.anthropic_api_key)


def _content_block(raw: bytes) -> dict:
    if raw.startswith(b"%PDF"):
        data = base64.standard_b64encode(raw).decode()
        return {"type": "document", "source": {"type": "base64", "media_type": "application/pdf", "data": data}}
    try:
        image = Image.open(io.BytesIO(raw))
        image.load()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as error:
        raise BusinessRuleError("Arquivo inválido. Envie fotos JPG, PNG ou WebP, ou um PDF.") from error
    image = ImageOps.exif_transpose(image).convert("RGB")
    image.thumbnail((MAX_DIMENSION, MAX_DIMENSION))
    output = io.BytesIO()
    image.save(output, format="JPEG", quality=85)
    data = base64.standard_b64encode(output.getvalue()).decode()
    return {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": data}}


def read_menu(files: list[bytes]) -> MenuDraft:
    if not enabled():
        raise BusinessRuleError("A leitura de cardápio por foto ainda não está disponível.")
    if not files or len(files) > MAX_FILES:
        raise BusinessRuleError(f"Envie de 1 a {MAX_FILES} arquivos.")
    if any(len(raw) > MAX_FILE_MB * 1024 * 1024 for raw in files):
        raise BusinessRuleError(f"Cada arquivo deve ter no máximo {MAX_FILE_MB} MB.")
    content = [_content_block(raw) for raw in files] + [{"type": "text", "text": PROMPT}]

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key, timeout=170, max_retries=1)
    try:
        response = client.beta.messages.parse(
            model=MODEL,
            max_tokens=16000,
            output_config={"effort": "low"},  # transcription, not reasoning: low keeps it fast
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            messages=[{"role": "user", "content": content}],
            output_format=MenuDraft,
        )
    except anthropic.RateLimitError as error:
        raise BusinessRuleError("Muitas leituras agora. Tente de novo em alguns minutos.") from error
    except anthropic.APIStatusError as error:
        logger.exception("Menu reading failed (%s)", error.status_code)
        raise BusinessRuleError("Não foi possível ler o cardápio agora. Tente novamente.") from error
    except anthropic.APIConnectionError as error:
        logger.exception("Menu reading failed (connection)")
        raise BusinessRuleError("Não foi possível ler o cardápio agora. Tente novamente.") from error

    draft = response.parsed_output
    if response.stop_reason in ("refusal", "max_tokens") or draft is None:
        logger.warning("Menu reading stopped: %s", response.stop_reason)
        raise BusinessRuleError("Não consegui ler esse cardápio. Tente uma foto mais nítida, de frente e com boa luz.")
    draft.categories = [c for c in draft.categories if c.products]
    if not draft.categories:
        raise BusinessRuleError("Não encontrei produtos com preço nessas fotos. Tente uma foto mais nítida.")
    return draft


def to_decimal(value: float) -> Decimal:
    return Decimal(str(round(value, 2))).quantize(Decimal("0.01"))
