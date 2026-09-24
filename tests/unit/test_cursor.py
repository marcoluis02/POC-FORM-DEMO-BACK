import uuid
from datetime import UTC, datetime

import pytest

from app.utils.cursor import decode_cursor, encode_cursor


def test_el_cursor_regresa_los_mismos_valores():
    created_at = datetime(2026, 9, 24, 18, 22, 17, 110801, tzinfo=UTC)
    entity_id = uuid.uuid4()

    assert decode_cursor(encode_cursor(created_at, entity_id)) == (created_at, entity_id)


@pytest.mark.parametrize("bad_cursor", ["abc", "!!!", "eyJ4IjoxfQ", "e30"])
def test_cursor_invalido_lanza_value_error(bad_cursor):
    with pytest.raises(ValueError):
        decode_cursor(bad_cursor)
