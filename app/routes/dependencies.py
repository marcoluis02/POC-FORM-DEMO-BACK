from typing import Annotated

from fastapi import Header, Query

IDEMPOTENCY_KEY_MAX_LENGTH = 255
CURSOR_MAX_LENGTH = 500

# Header opcional. El front siempre lo manda en las acciones que crean o modifican datos.
IdempotencyKeyHeader = Annotated[
    str | None,
    Header(alias="Idempotency-Key", min_length=1, max_length=IDEMPOTENCY_KEY_MAX_LENGTH),
]

# Cursor de la página siguiente (lo regresa el listado anterior en next_cursor)
CursorQuery = Annotated[str | None, Query(min_length=1, max_length=CURSOR_MAX_LENGTH)]
