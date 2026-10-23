"""Portuguese names for enum values, shared by every screen-free output (exports, reports)."""

SERVICE_LABELS = {"DINE_IN": "No local", "TAKEAWAY": "Para levar", "DELIVERY": "Entrega"}
PAYMENT_LABELS = {"PIX": "PIX", "CARD": "Cartão", "CASH": "Dinheiro", "TAB": "Na comanda"}
STATUS_LABELS = {
    "RECEIVED": "Recebido", "PREPARING": "Em preparo", "READY": "Pronto", "FINISHED": "Entregue", "CANCELLED": "Cancelado",
}
WEEKDAYS = ("segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo")


def label(mapping: dict[str, str], value) -> str:
    raw = getattr(value, "value", value)
    return mapping.get(raw, raw)
