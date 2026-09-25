from app.cloud.openai_extraction import IMAGE_DETAIL, PDF_DETAIL, OpenAIExtractionProvider
from app.domain.document_types import DocumentMimeType
from app.interfaces.extraction_provider import ExtractionInput


def test_pdf_request_usa_input_file_con_detail_high():
    source = ExtractionInput(
        filename="formulario.pdf",
        mime_type=DocumentMimeType.PDF,
        content=b"%PDF-1.4 prueba",
    )

    content = OpenAIExtractionProvider._content(source)

    file_item = next(item for item in content if item["type"] == "input_file")
    assert file_item["filename"] == "formulario.pdf"
    assert file_item["file_data"].startswith("data:application/pdf;base64,")
    assert file_item["detail"] == PDF_DETAIL == "high"
    assert all(item["type"] != "input_image" for item in content)


def test_imagen_request_usa_input_image_con_detail_high():
    source = ExtractionInput(
        filename="formulario.png",
        mime_type=DocumentMimeType.PNG,
        content=b"\x89PNG\r\n\x1a\n",
    )

    content = OpenAIExtractionProvider._content(source)

    image_item = next(item for item in content if item["type"] == "input_image")
    assert image_item["image_url"].startswith("data:image/png;base64,")
    assert image_item["detail"] == IMAGE_DETAIL == "high"
    assert all(item["type"] != "input_file" for item in content)


def test_status_transitorios_se_marcan_retryable():
    for status in (408, 409, 425, 429, 500, 503):
        assert OpenAIExtractionProvider._status_is_retryable(status)

    for status in (400, 401, 403, 404, 422):
        assert not OpenAIExtractionProvider._status_is_retryable(status)
