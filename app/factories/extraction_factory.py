from app.core.config import Settings
from app.interfaces.extraction_provider import ExtractionProvider


def build_extraction_provider(settings: Settings) -> ExtractionProvider:
    provider = settings.ai_provider.strip().lower()
    if provider == "openai":
        # Import tardío: la API puede arrancar con el worker apagado aunque el SDK de IA
        # no esté instalado/configurado en ese entorno.
        from app.cloud.openai_extraction import OpenAIExtractionProvider

        return OpenAIExtractionProvider(settings)
    raise ValueError(f"AI_PROVIDER no soportado: {settings.ai_provider!r}. Para esta POC usa 'openai'.")
