import hashlib
import json
from typing import Any


def bytes_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def stable_hash(payload: Any) -> str:
    """SHA-256 de un JSON con llaves ordenadas. Dos peticiones iguales dan el mismo hash."""
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
