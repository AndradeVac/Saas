"""PIX "copia e cola" (BR Code, static, with amount) built from the restaurant's own PIX key.

The money goes straight to the restaurant: the platform only formats the payment request. Static codes carry no
payment confirmation, so staff confirm the payment in their bank app (automatic confirmation comes with Asaas).
Spec: Manual de Padrões para Iniciação do Pix (BCB), EMV QRCPS-MPM.
"""
import re
import unicodedata
from decimal import Decimal

_CPF_WEIGHTS = (list(range(10, 1, -1)), list(range(11, 1, -1)))


def _valid_cpf(digits: str) -> bool:
    if len(digits) != 11 or digits == digits[0] * 11:
        return False
    for size, weights in ((9, _CPF_WEIGHTS[0]), (10, _CPF_WEIGHTS[1])):
        total = sum(int(d) * w for d, w in zip(digits[:size], weights))
        check = (total * 10) % 11 % 10
        if check != int(digits[size]):
            return False
    return True


def normalize_pix_key(raw: str) -> str | None:
    """The key in the format the PIX network expects: e-mail, +55 phone, CPF/CNPJ digits or random key (EVP)."""
    key = (raw or "").strip()
    if not key:
        return None
    if "@" in key:
        return key.lower()
    if re.fullmatch(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}", key):
        return key.lower()
    digits = re.sub(r"\D", "", key)
    if key.startswith("+"):
        return f"+{digits}"
    if len(digits) == 14:
        return digits  # CNPJ
    if len(digits) == 11 and _valid_cpf(digits):
        return digits  # CPF (checked first: a valid CPF is not a phone)
    if len(digits) in (10, 11):
        return f"+55{digits}"  # phone with area code
    if len(digits) in (12, 13) and digits.startswith("55"):
        return f"+{digits}"
    return key


def is_valid_pix_key(raw: str) -> bool:
    """True for the five key types the PIX network accepts (after normalisation)."""
    key = normalize_pix_key(raw)
    if not key:
        return False
    if "@" in key:
        return bool(re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", key)) and len(key) <= 77
    if re.fullmatch(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", key):
        return True
    if re.fullmatch(r"\+55\d{10,11}", key):
        return True
    return bool(re.fullmatch(r"\d{11}|\d{14}", key))


def pix_key_kind(raw: str) -> str:
    """How the key was understood, shown to the owner: an 11-digit phone can also be a valid CPF."""
    key = normalize_pix_key(raw) or ""
    if "@" in key:
        return "E-mail"
    if key.startswith("+"):
        return "Celular"
    if len(key) == 14 and key.isdigit():
        return "CNPJ"
    if len(key) == 11 and key.isdigit():
        return "CPF"
    return "Chave aleatória"


def _ascii(text: str, limit: int) -> str:
    plain = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    plain = re.sub(r"[^A-Za-z0-9 ]", "", plain).strip().upper()
    return (plain or "LOJA")[:limit].strip()


def _field(field_id: str, value: str) -> str:
    return f"{field_id}{len(value):02d}{value}"


def _crc16(payload: str) -> str:
    crc = 0xFFFF
    for byte in payload.encode():
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) if crc & 0x8000 else (crc << 1)
            crc &= 0xFFFF
    return f"{crc:04X}"


def brcode(key: str, amount: Decimal, merchant_name: str, merchant_city: str = "BRASIL", reference: str = "***") -> str:
    account = _field("00", "br.gov.bcb.pix") + _field("01", key)
    reference = re.sub(r"[^A-Za-z0-9]", "", reference)[:25] or "***"
    payload = (
        _field("00", "01")
        + _field("26", account)
        + _field("52", "0000")
        + _field("53", "986")
        + _field("54", f"{amount:.2f}")
        + _field("58", "BR")
        + _field("59", _ascii(merchant_name, 25))
        + _field("60", _ascii(merchant_city, 15))
        + _field("62", _field("05", reference))
        + "6304"
    )
    return payload + _crc16(payload)
