from app.services.ai_provider import AIProvider
from app.core.config import settings
from app.services.providers.gemini_ai_provider import GeminiAIProvider
from app.services.providers.openai_ai_provider import OpenAIAIProvider
from app.services.providers.stub_ai_provider import StubAIProvider


class AIProviderConfigurationError(RuntimeError):
    """Raised when the selected provider has no installed implementation."""


class AIProviderFactory:
    @staticmethod
    def create(
        provider_name: str,
        *,
        api_key: str | None = None,
        model: str | None = None,
    ) -> AIProvider:
        normalized_name = provider_name.lower().strip()
        if normalized_name == "stub":
            return StubAIProvider()
        if normalized_name == "openai":
            return OpenAIAIProvider(
                api_key=settings.openai_api_key if api_key is None else api_key,
                model=settings.openai_model if model is None else model,
            )
        if normalized_name == "gemini":
            return GeminiAIProvider(
                api_key=settings.gemini_api_key if api_key is None else api_key,
                model=settings.gemini_model if model is None else model,
            )
        raise AIProviderConfigurationError(
            f"AI provider '{provider_name}' is not implemented. Supported providers: stub, openai, gemini."
        )
