from app.schemas.ai_analysis import PreliminaryDiagnosticAnalysis
from app.schemas.diagnostic_context import DiagnosticContext
from app.services.providers.openai_request_builder import OpenAIRequestBuilder


class OpenAIProviderNotEnabledError(RuntimeError):
    """Raised until the real OpenAI integration is deliberately enabled."""


class OpenAIAIProvider:
    """OpenAI adapter boundary; intentionally performs no network operation in this stage."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        request_builder: OpenAIRequestBuilder | None = None,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.request_builder = request_builder or OpenAIRequestBuilder()

    def analyze(self, context: DiagnosticContext) -> PreliminaryDiagnosticAnalysis:
        # Build now to keep the future request boundary exercised, but never send it anywhere.
        self.request_builder.build(context)
        raise OpenAIProviderNotEnabledError(
            "OpenAI provider is configured but real API integration is not enabled yet."
        )
