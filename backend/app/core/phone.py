import re


def phone_digits(value: str | None) -> str | None:
    """Digits only, without the +55 country code ("(11) 99999-9999" -> "11999999999").
    Returns None when the value has no digits at all."""
    digits = re.sub(r"\D", "", value or "")
    if digits.startswith("55") and len(digits) in (12, 13):
        digits = digits[2:]
    return digits or None


def normalize_phone(value: str) -> str:
    """Validates a Brazilian phone with area code and returns its digits."""
    digits = phone_digits(value)
    if digits is None or len(digits) not in (10, 11):
        raise ValueError("Informe um telefone válido com DDD.")
    return digits
