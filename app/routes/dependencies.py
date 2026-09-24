from typing import Annotated

from fastapi import Header

IDEMPOTENCY_KEY_MAX_LENGTH = 255

# Header opcional. El front siempre lo manda en las acciones que crean o modifican datos.
IdempotencyKeyHeader = Annotated[
    str | None,
    Header(alias="Idempotency-Key", min_length=1, max_length=IDEMPOTENCY_KEY_MAX_LENGTH),
]
