"""Opening hours: {"mon": [["08:00", "18:00"]], ...} in the tenant's own time zone."""
from datetime import datetime
from zoneinfo import ZoneInfo

DAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")


def _minutes(value: str) -> int:
    hours, minutes = value.split(":")
    return int(hours) * 60 + int(minutes)


def is_open_now(
    *,
    accepting_orders: bool,
    hours_mode: str,
    opening_hours: dict,
    timezone: str,
    now: datetime | None = None,
) -> bool:
    """MANUAL mode follows the owner's switch; SCHEDULE also requires being inside a listed interval.
    An interval whose close is not after its open runs past midnight into the next day."""
    if not accepting_orders:
        return False
    if hours_mode != "SCHEDULE":
        return True

    local = (now or datetime.now(ZoneInfo(timezone))).astimezone(ZoneInfo(timezone))
    current = local.hour * 60 + local.minute
    today = DAYS[local.weekday()]
    yesterday = DAYS[(local.weekday() - 1) % 7]

    for start, end in opening_hours.get(today, []):
        open_at, close_at = _minutes(start), _minutes(end)
        if close_at > open_at:
            if open_at <= current < close_at:
                return True
        elif current >= open_at:
            return True
    for start, end in opening_hours.get(yesterday, []):
        open_at, close_at = _minutes(start), _minutes(end)
        if close_at <= open_at and current < close_at:
            return True
    return False
