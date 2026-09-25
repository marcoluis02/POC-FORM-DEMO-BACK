from collections import deque
from decimal import Decimal

from app.interfaces.extraction_provider import (
    ExtractionInput,
    ExtractionProviderError,
    ExtractionResult,
    ExtractionWarning,
)


class FakeExtractionProvider:
    """Fake controlable para probar ExtractionService y el worker sin llamar a OpenAI."""

    def __init__(self) -> None:
        self.calls: list[ExtractionInput] = []
        self._outcomes = deque()
        self.default_result = ExtractionResult(definition=None, warnings=[], estimated_cost=None)

    def queue_result(
        self,
        definition,
        *,
        warnings: list[ExtractionWarning] | None = None,
        estimated_cost: Decimal | None = None,
    ) -> None:
        self._outcomes.append(
            ExtractionResult(
                definition=definition,
                warnings=warnings or [],
                estimated_cost=estimated_cost,
            )
        )

    def queue_error(
        self,
        code: str,
        message: str,
        *,
        retryable: bool = False,
    ) -> None:
        self._outcomes.append(ExtractionProviderError(code, message, retryable=retryable))

    async def extract(self, source: ExtractionInput) -> ExtractionResult:
        self.calls.append(source)
        outcome = self._outcomes.popleft() if self._outcomes else self.default_result
        if isinstance(outcome, Exception):
            raise outcome
        return outcome
