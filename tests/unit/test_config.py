from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_aws_estatico_es_opcional_y_storage_sigue_configurado(monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "")

    settings = Settings()

    assert settings.storage_configured is True
    assert settings.aws_static_credentials_configured is False


def test_aws_credenciales_parciales_fallan_rapido(monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "solo-access")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "")

    with pytest.raises(ValidationError):
        Settings()


def test_luna_recibe_tarifas_default_coherentes(monkeypatch):
    monkeypatch.setenv("OPENAI_MODEL", "gpt-5.6-luna")
    monkeypatch.delenv("OPENAI_INPUT_COST_PER_MILLION", raising=False)
    monkeypatch.delenv("OPENAI_OUTPUT_COST_PER_MILLION", raising=False)

    settings = Settings()

    assert settings.openai_input_cost_per_million == Decimal("0.20")
    assert settings.openai_output_cost_per_million == Decimal("1.20")


def test_cambiar_modelo_obliga_a_configurar_ambas_tarifas(monkeypatch):
    monkeypatch.setenv("OPENAI_MODEL", "gpt-5.6-sol")
    monkeypatch.delenv("OPENAI_INPUT_COST_PER_MILLION", raising=False)
    monkeypatch.delenv("OPENAI_OUTPUT_COST_PER_MILLION", raising=False)

    with pytest.raises(ValidationError):
        Settings()


def test_otro_modelo_acepta_tarifas_explicitas(monkeypatch):
    monkeypatch.setenv("OPENAI_MODEL", "gpt-5.6-sol")
    monkeypatch.setenv("OPENAI_INPUT_COST_PER_MILLION", "4")
    monkeypatch.setenv("OPENAI_OUTPUT_COST_PER_MILLION", "20")

    settings = Settings()

    assert settings.openai_model == "gpt-5.6-sol"
    assert settings.openai_input_cost_per_million == Decimal("4")
    assert settings.openai_output_cost_per_million == Decimal("20")
