import os
from pathlib import Path

import pytest

from app.cloud.openai_extraction import OpenAIExtractionProvider
from app.core.config import get_settings
from app.domain.document_types import DocumentMimeType
from app.interfaces.extraction_provider import ExtractionInput

SAMPLE_PDF = Path(__file__).resolve().parents[1] / "fixtures" / "openai_form_sample.pdf"


@pytest.mark.integration
@pytest.mark.skipif(
    os.getenv("RUN_OPENAI_INTEGRATION") != "1",
    reason="Prueba real con OpenAI: ejecutar explícitamente con RUN_OPENAI_INTEGRATION=1.",
)
async def test_pdf_real_produce_formulario_revisable():
    settings = get_settings()
    if not settings.openai_api_key.strip():
        pytest.skip("OPENAI_API_KEY no está configurada.")

    provider = OpenAIExtractionProvider(settings)
    result = await provider.extract(
        ExtractionInput(
            filename=SAMPLE_PDF.name,
            mime_type=DocumentMimeType.PDF,
            content=SAMPLE_PDF.read_bytes(),
        )
    )

    assert result.definition is not None
    assert result.definition.sections
    assert sum(len(section.fields) for section in result.definition.sections) > 0
