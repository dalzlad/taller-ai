from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.agents.diagnostic_agent import PreliminaryDiagnosticAgent
from app.api.dependencies import get_diagnostic_agent
from app.db.base import Base
from app.main import app
from app.models import Customer, Diagnostic, DiagnosticEvidence, DiagnosticMedia, Vehicle
from app.models.enums import DiagnosticEvidenceType, DiagnosticStatus, MediaType
from app.schemas.ai_analysis import PreliminaryDiagnosticAnalysis
from app.services.ai_provider_factory import AIProviderConfigurationError, AIProviderFactory
from app.services.ai_safety import (
    DISASSEMBLED_ENGINE_WARNING,
    MANDATORY_LIMITATION,
    REPAIR_STATE_LIMITATION,
    AISafety,
    UnsafeAIResultError,
)
from app.services.providers.stub_ai_provider import StubAIProvider


def _session_factory_with_diagnostic() -> tuple[sessionmaker[Session], int, object]:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    with factory() as db:
        customer = Customer(name="Luis Mecánico", phone="3001234567", email="luis@example.com")
        vehicle = Vehicle(
            customer=customer,
            plate="ABC123",
            vin="1HGCM82633A004352",
            brand="Honda",
            model="Civic",
            year=2018,
            mileage=80000,
        )
        diagnostic = Diagnostic(
            vehicle=vehicle,
            reported_symptoms="Vibration while accelerating",
            mechanic_notes="Inspect ignition components",
        )
        db.add_all(
            [
                diagnostic,
                DiagnosticMedia(
                    diagnostic=diagnostic, type=MediaType.PHOTO, file_url="https://example.test/engine.jpg"
                ),
                DiagnosticMedia(
                    diagnostic=diagnostic, type=MediaType.AUDIO, file_url="https://example.test/noise.mp3"
                ),
                DiagnosticEvidence(
                    diagnostic=diagnostic,
                    evidence_type=DiagnosticEvidenceType.IMAGE,
                    file_name="engine.jpg",
                    file_path="diagnostics/1/engine.jpg",
                    mime_type="image/jpeg",
                    file_size=10,
                ),
            ]
        )
        db.commit()
        diagnostic_id = diagnostic.id
    return factory, diagnostic_id, engine


def test_agent_orchestrates_provider_with_context_without_persisting_analysis() -> None:
    session_factory, diagnostic_id, engine = _session_factory_with_diagnostic()
    history = Mock()
    history.get_history.return_value = {"previous_repairs": ["Spark plugs replaced in 2023"]}
    provider = Mock()
    provider.analyze.return_value = PreliminaryDiagnosticAnalysis(
        summary="Preliminary review suggests checking the ignition system.",
        vehicle_state="en_uso",
        observations={"audio": ["Available evidence requires mechanic review."], "image": []},
        possible_causes=[
            {
                "cause": "Worn ignition coil",
                "confidence": 0.62,
                "reasoning": "Symptoms are compatible.",
                "based_on": ["audio"],
            }
        ],
        recommended_tests=["Check coil output with the manufacturer procedure."],
        safety_warnings=[],
        limitations=[],
    )
    agent = PreliminaryDiagnosticAgent(session_factory, provider, history)

    result = agent.analyze(diagnostic_id)

    assert result.possible_causes[0].confidence == 0.62
    assert MANDATORY_LIMITATION in result.limitations
    history.get_history.assert_called_once()
    provider.analyze.assert_called_once()
    context = provider.analyze.call_args.args[0]
    assert context.vehicle.brand == "Honda"
    assert context.diagnostic.reported_symptoms == "Vibration while accelerating"
    assert {evidence.file_name for evidence in context.evidences} >= {"engine.jpg", "noise.mp3"}
    assert all(not hasattr(evidence, "bytes") for evidence in context.evidences)
    assert MANDATORY_LIMITATION in AISafety.validate(StubAIProvider().analyze(context)).limitations
    with Session(engine) as db:
        diagnostic = db.get(Diagnostic, diagnostic_id)
        assert diagnostic is not None
        assert diagnostic.status == DiagnosticStatus.CREATED
        assert diagnostic.ai_analysis is None
    Base.metadata.drop_all(engine)
    engine.dispose()


def test_analyze_endpoint_delegates_to_agent(client: TestClient) -> None:
    expected = PreliminaryDiagnosticAnalysis(
        summary="Preliminary review only.",
        possible_causes=[],
        recommended_tests=[],
        safety_warnings=[],
        limitations=["Not a confirmed fault."],
    )
    agent = Mock()
    agent.analyze.return_value = expected
    app.dependency_overrides[get_diagnostic_agent] = lambda: agent
    customer = client.post(
        "/customers", json={"name": "Ana Ruiz", "phone": "+57 300 000 0000", "email": "ana@example.com"}
    ).json()
    vehicle = client.post(
        "/vehicles",
        json={"customer_id": customer["id"], "plate": "DEL123", "brand": "Kia", "model": "Rio", "year": 2020, "mileage": 1},
    ).json()
    diagnostic_id = client.post(
        "/diagnostics", json={"vehicle_id": vehicle["id"], "reported_symptoms": "Ruido al frenar"}
    ).json()["id"]

    response = client.post(f"/diagnostics/{diagnostic_id}/analyze")

    assert response.status_code == 200
    assert response.json()["summary"] == "Preliminary review only."
    agent.analyze.assert_called_once_with(diagnostic_id)
    app.dependency_overrides.pop(get_diagnostic_agent)


def test_analyze_endpoint_uses_stub_provider_and_returns_404_for_missing_diagnostic(client: TestClient) -> None:
    customer = client.post(
        "/customers", json={"name": "Ana Ruiz", "phone": "+57 300 000 0000", "email": "ana.ruiz@example.com"}
    ).json()
    vehicle = client.post(
        "/vehicles",
        json={"customer_id": customer["id"], "plate": "AI1234", "brand": "Toyota", "model": "Yaris", "year": 2020, "mileage": 1000},
    ).json()
    diagnostic = client.post(
        "/diagnostics", json={"vehicle_id": vehicle["id"], "reported_symptoms": "Ruido al arrancar"}
    ).json()

    response = client.post(f"/diagnostics/{diagnostic['id']}/analyze")
    assert response.status_code == 200
    assert MANDATORY_LIMITATION in response.json()["limitations"]
    assert client.post("/diagnostics/999/analyze").status_code == 404


def test_stub_provider_factory_and_safety() -> None:
    provider = AIProviderFactory.create("stub")
    assert isinstance(provider, StubAIProvider)
    with pytest.raises(AIProviderConfigurationError):
        AIProviderFactory.create("unknown")

    unsafe = PreliminaryDiagnosticAnalysis(
        summary="The failure is confirmed.", possible_causes=[], recommended_tests=[], safety_warnings=[], limitations=[]
    )
    with pytest.raises(UnsafeAIResultError):
        AISafety.validate(unsafe)
    spanish_unsafe = unsafe.model_copy(update={"summary": "La falla está confirmada."})
    with pytest.raises(UnsafeAIResultError):
        AISafety.validate(spanish_unsafe)


def test_ai_safety_flags_repair_state_limitation_and_warning_when_missing() -> None:
    """A disassembled-engine photo must never pass silently as evidence of the audio symptom's
    cause: when the provider reports the vehicle as under repair, AISafety must add the
    explanatory limitation and a warning against starting/handling the engine, even if the
    provider's own output omitted them."""
    analysis = PreliminaryDiagnosticAnalysis(
        summary="El motor aparece desarmado en un taller; el audio reporta un ruido al ralentí.",
        vehicle_state="en_reparacion",
        observations={"audio": ["Golpeteo leve al ralentí."], "image": ["motor_desarmado_reparacion: bloque sin culata."]},
        possible_causes=[],
        recommended_tests=[],
        safety_warnings=[],
        limitations=[],
    )

    validated = AISafety.validate(analysis)

    assert REPAIR_STATE_LIMITATION in validated.limitations
    assert DISASSEMBLED_ENGINE_WARNING in validated.safety_warnings


def test_ai_safety_does_not_duplicate_repair_limitation_when_provider_paraphrased_it() -> None:
    """Regression test for a real Gemini output that stated the same idea as
    REPAIR_STATE_LIMITATION in different words; AISafety must recognize the paraphrase instead
    of appending a second, redundant limitation."""
    provider_limitation = (
        "El vehículo está en un taller y las imágenes muestran el motor desarmado, por lo que "
        "estas imágenes no pueden usarse como evidencia directa de la causa del síntoma "
        "auditivo, ya que el motor no está en su estado operativo normal."
    )
    analysis = PreliminaryDiagnosticAnalysis(
        summary="Motor desarmado en taller; se reporta un ruido en el audio.",
        vehicle_state="en_reparacion",
        possible_causes=[],
        recommended_tests=[],
        safety_warnings=[],
        limitations=[provider_limitation],
    )

    validated = AISafety.validate(analysis)

    assert validated.limitations == [provider_limitation, MANDATORY_LIMITATION]
    assert REPAIR_STATE_LIMITATION not in validated.limitations


def test_ai_safety_does_not_duplicate_repair_warning_already_present() -> None:
    analysis = PreliminaryDiagnosticAnalysis(
        summary="Motor desarmado en taller.",
        vehicle_state="en_reparacion",
        possible_causes=[],
        recommended_tests=[],
        safety_warnings=["El motor está desarmado; no lo intente encender."],
        limitations=[],
    )

    validated = AISafety.validate(analysis)

    assert validated.safety_warnings == ["El motor está desarmado; no lo intente encender."]
