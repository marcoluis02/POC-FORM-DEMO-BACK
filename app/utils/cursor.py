import base64
import binascii
import json
import uuid
from datetime import datetime


def encode_cursor(created_at: datetime, entity_id: uuid.UUID) -> str:
    """Marca dónde terminó la página. El cliente la regresa tal cual para pedir la siguiente."""
    raw = json.dumps({"c": created_at.isoformat(), "i": str(entity_id)}, separators=(",", ":"))
    return base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")


def decode_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    """Lanza ValueError si el cursor no es válido."""
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        data = json.loads(base64.urlsafe_b64decode(padded.encode()))
        created_at = datetime.fromisoformat(data["c"])
        entity_id = uuid.UUID(data["i"])
    except (binascii.Error, UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        raise ValueError("Cursor inválido") from exc
    if created_at.tzinfo is None:
        raise ValueError("Cursor inválido")
    return created_at, entity_id
