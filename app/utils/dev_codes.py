from __future__ import annotations

import time
from collections import deque
from dataclasses import asdict, dataclass
from threading import Lock

from app.core.config import settings

_MAX_ENTRIES = 50


@dataclass(frozen=True)
class DevCodeEntry:
    email_type: str
    recipient: str
    code: str
    link: str
    captured_at: float


_buffer: deque[DevCodeEntry] = deque(maxlen=_MAX_ENTRIES)
_lock = Lock()


def _enabled() -> bool:
    return settings.ENVIRONMENT != "production"


def record(email_type: str, recipient: str, code: str, link: str) -> None:
    if not _enabled():
        return
    entry = DevCodeEntry(
        email_type=email_type,
        recipient=recipient,
        code=code,
        link=link,
        captured_at=time.time(),
    )
    with _lock:
        _buffer.append(entry)


def snapshot() -> list[dict]:
    if not _enabled():
        return []
    with _lock:
        items = list(_buffer)
    items.reverse()
    return [asdict(i) for i in items]


def clear() -> None:
    if not _enabled():
        return
    with _lock:
        _buffer.clear()
