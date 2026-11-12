"""Vaqt bilan ishlash uchun yordamchilar.

Baza naive UTC saqlaydi (SQLite `DATETIME`), API esa doim `Z` suffiksi bilan
qaytaradi — shunda brauzer vaqtni to'g'ri, UTC sifatida o'qiydi.
"""

from datetime import datetime, timezone


def utcnow() -> datetime:
    """Hozirgi UTC vaqt, naive (bazaga yozish uchun)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def iso_utc(value: datetime | None) -> str | None:
    """Naive UTC vaqtni API uchun `2026-11-12T11:50:04Z` ko'rinishida beradi."""
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
