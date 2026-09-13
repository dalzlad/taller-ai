import pytest

from app.models.enums import DiagnosticEvidenceType, DiagnosticStatus
from app.schemas.diagnostic_context import (
    DiagnosticContext,
    DiagnosticDetailsContext,
    DiagnosticEvidenceContext,
    DiagnosticVehicleContext,
)
from app.services.ai_provider import AIProvider
from app.services.ai_provider_factory import AIProviderFactory
from app.services.providers.openai_ai_provider import (
    OpenAIAIProvider,
    OpenAIProviderNotEnabledError,
)
from app.services.providers.openai_request_builder import OpenAIRequestBuilder
from app.services.providers.stub_ai_provider import StubAIProvider


def _context() -> DiagnosticContext:
    return DiagnosticContext(
        vehicle=DiagnosticVehicleContext(
            id=1, brand="Honda", model="Civic", year=2018, engine="2.0L", mileage=80000,
            plate="ABC123", vin="1HGCM82633A004352",
        ),
        diagnostic=DiagnosticDetailsContext(
            id=7, reported_symptoms="Vibration al acelerar", mechanic_notes="Revisar encendido",
            status=DiagnosticStatus.CREATED,
        ),
        history={"previous_repairs": ["Cambio de bujías"]},
        technical_knowledge={"available": False},
        evidences=[
            DiagnosticEvidenceContext(
                evidence_type=DiagnosticEvidenceType.IMAGE,
                file_name="motor.jpg", mime_type="image/jpeg",
                file_reference="diagnostics/7/uuid.jpg", description="Zona del motor",
            )
        ],
    )


def test_openai_provider_implements_contract_without_real_key() -> None:
    provider = OpenAIAIProvider()
    assert isinstance(provider, AIProvider)
    with pytest.raises(OpenAIProviderNotEnabledError, match="real API integration is not enabled yet"):
        provider.analyze(_context())


def test_factory_supports_stub_and_openai_without_calling_network() -> None:
    assert isinstance(AIProviderFactory.create("stub"), StubAIProvider)
    provider = AIProviderFactory.create("openai")
    assert isinstance(provider, OpenAIAIProvider)
    assert provider.api_key is None
    with pytest.raises(OpenAIProviderNotEnabledError):
        provider.analyze(_context())


def test_openai_request_builder_separates_text_metadata_and_evidence_references() -> None:
    request = OpenAIRequestBuilder().build(_context())
    assert request.textual_context["symptoms"] == "Vibration al acelerar"
    assert request.textual_context["vehicle"]["brand"] == "Honda"
    assert request.evidences[0]["type"] == "IMAGE"
    assert request.evidences[0]["reference"] == "diagnostics/7/uuid.jpg"
    assert "motor.jpg" in request.evidences[0]["file_name"]
    assert "bytes" not in repr(request).lower()
    assert all("bytes" not in item for item in request.evidences)
