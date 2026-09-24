import subprocess
import sys
from pathlib import Path

import pytest

BACK_DIR = Path(__file__).resolve().parents[2]
MODELS_DIR = BACK_DIR / "app" / "models"
MIGRATIONS_ENV = BACK_DIR / "app" / "sql" / "migrations" / "env.py"


def model_modules() -> list[str]:
    """Archivos de app/models que definen una tabla."""
    return sorted(
        f"app.models.{path.stem}"
        for path in MODELS_DIR.glob("*.py")
        if "__tablename__" in path.read_text(encoding="utf-8")
    )


def run_clean_python(code: str) -> str:
    # Proceso nuevo: así solo se carga lo que importa app.models, igual que en Alembic
    result = subprocess.run(
        [sys.executable, "-c", code], cwd=BACK_DIR, capture_output=True, text=True, check=True, timeout=60
    )
    return result.stdout


def test_hay_modelos_para_revisar():
    assert len(model_modules()) >= 1


@pytest.mark.parametrize("module", model_modules())
def test_cada_modelo_esta_en_el_registro(module):
    loaded = run_clean_python("import sys, app.models; print('\\n'.join(sys.modules))").split()

    assert module in loaded, f"Agrega {module} a app/models/__init__.py para que Alembic lo vea."


def test_la_metadata_de_alembic_trae_todas_las_tablas():
    tables = run_clean_python("from app.models import Base; print('\\n'.join(Base.metadata.tables))").split()

    assert len(tables) == len(model_modules())


def test_env_de_alembic_usa_el_registro_y_no_solo_base():
    source = MIGRATIONS_ENV.read_text(encoding="utf-8")

    assert "from app.models import Base" in source
    assert "from app.models.base import" not in source
