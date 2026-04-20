from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from typing import Any, Optional


DATE_FORMATS = (
    "%Y-%m-%d",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%dT%H:%M:%S.%f",
)


def utcnow() -> datetime:
    return datetime.utcnow()


def _as_utc_naive(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def parse_datetime(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return _as_utc_naive(value)

    text = str(value).strip()
    if not text:
        return None

    text = text.replace("Z", "+00:00")
    try:
        return _as_utc_naive(datetime.fromisoformat(text))
    except ValueError:
        pass

    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def stable_id(*parts: Any) -> str:
    digest = hashlib.sha256("|".join(str(x) for x in parts).encode("utf-8")).hexdigest()
    return digest[:20]
