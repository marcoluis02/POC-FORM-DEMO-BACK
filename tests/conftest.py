import copy
import json
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def _maintenance_template_raw() -> dict:
    return json.loads((FIXTURES_DIR / "maintenance_template.json").read_text(encoding="utf-8"))


@pytest.fixture
def maintenance_template(_maintenance_template_raw: dict) -> dict:
    """Copia nueva en cada test para poder modificarla sin afectar a otros."""
    return copy.deepcopy(_maintenance_template_raw)
