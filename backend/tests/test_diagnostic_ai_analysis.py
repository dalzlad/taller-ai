"""Persistencia del análisis de IA: se genera una sola vez por diagnóstico y se reutiliza."""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies import get_ai_provider
from app.db.session import get_db
from app.main import app
from app.models import Diagnostic, DiagnosticAIAnalysis
from app.models.enums import DiagnosticStatus
from app.schemas.ai_analysis import ANALYSIS_SCHEMA_VERSION, PreliminaryDiagnosticAnalysis
from app.schemas.diagnostic_context import DiagnosticContext
from app.services.ai_safety import MANDATORY_LIMITATION
from app.services.providers.gemini_ai_provider import (
    GeminiProviderConfigurationError,
    GeminiProviderResponseError,
)
from app.services.providers.openai_ai_provider import OpenAIProviderNotEnabledError
from app.services.providers.stub_ai_provider import StubAIProvider


class FakeProvider:
    """Counts calls; returns the stub analysis, a fixed analysis, or raises a given error."""

    def __init__(self, name: str = "stub", model: str | None = None) -> None:
        self.name = name
        self.model = model
        self.calls = 0
        self.result: PreliminaryDiagnosticAnalysis | None = None
        self.error: Exception | None = None

    def analyze(self, context: DiagnosticContext) -> PreliminaryDiagnosticAnalysis:
        self.calls += 1
        if self.error is not None:
            raise self.error
        return self.result or StubAIProvider().analyze(context)


@pytest.fixture()
def provider(client: TestClient) -> FakeProvider:
    fake = FakeProvider()
    app.dependency_overrides[get_ai_provider] = lambda: fake
    return fake


@contextmanager
def _db() -> Iterator[Session]:
    """A session on the same in-memory database the test client uses."""
    sessions = app.dependency_overrides[get_db]()
    try:
        yield next(sessions)
    finally:
        sessions.close()


def _diagnostic(client: TestClient) -> int:
    customer = client.post(
        "/customers", json={"name": "Ana Ruiz", "phone": "+57 300 000 0000", "email": "ana@example.com"}
    ).json()
    vehicle = client.post(
        "/vehicles",
        json={"customer_id": customer["id"], "plate": "IAA123", "brand": "Kia", "model": "Rio", "year": 2020, "mileage": 1},
    ).json()
    return client.post(
        "/diagnostics", json={"vehicle_id": vehicle["id"], "reported_symptoms": "Ruido al arrancar"}
    ).json()["id"]


def _status(client: TestClient, diagnostic_id: int) -> str:
    return client.get(f"/diagnostics/{diagnostic_id}").json()["status"]


def _analysis_rows(diagnostic_id: int) -> int:
    with _db() as db:
        statement = select(func.count()).where(DiagnosticAIAnalysis.diagnostic_id == diagnostic_id)
        return db.scalar(statement)


# --- Primer análisis ---------------------------------------------------------------------------


def test_first_analysis_calls_provider_once_and_persists_it_with_metadata(client, provider) -> None:
    diagnostic_id = _diagnostic(client)

    response = client.post(f"/diagnostics/{diagnostic_id}/analyze")

    assert response.status_code == 200
    body = response.json()
    # POST keeps its previous response shape: the analysis itself, without metadata.
    assert set(body) == set(PreliminaryDiagnosticAnalysis.model_fields)
    assert MANDATORY_LIMITATION in body["limitations"]
    assert provider.calls == 1

    stored = client.get(f"/diagnostics/{diagnostic_id}/analysis")
    assert stored.status_code == 200
    stored_body = stored.json()
    assert stored_body["diagnostic_id"] == diagnostic_id
    assert stored_body["provider"] == "stub"
    assert stored_body["model"] is None
    assert stored_body["schema_version"] == ANALYSIS_SCHEMA_VERSION
    assert stored_body["generated_at"]
    assert stored_body["result"] == body
    assert _status(client, diagnostic_id) == "REVIEW"


def test_gemini_analysis_persists_provider_and_model(client, provider) -> None:
    provider.name, provider.model = "gemini", "gemini-2.0-flash"
    diagnostic_id = _diagnostic(client)

    client.post(f"/diagnostics/{diagnostic_id}/analyze")

    stored = client.get(f"/diagnostics/{diagnostic_id}/analysis").json()
    assert (stored["provider"], stored["model"]) == ("gemini", "gemini-2.0-flash")


def test_legacy_ai_analysis_column_stays_unused(client, provider) -> None:
    diagnostic_id = _diagnostic(client)

    client.post(f"/diagnostics/{diagnostic_id}/analyze")

    assert client.get(f"/diagnostics/{diagnostic_id}").json()["ai_analysis"] is None


# --- Idempotencia ------------------------------------------------------------------------------


def test_second_analysis_returns_persisted_result_without_calling_provider(client, provider) -> None:
    diagnostic_id = _diagnostic(client)
    first = client.post(f"/diagnostics/{diagnostic_id}/analyze").json()
    generated_at = client.get(f"/diagnostics/{diagnostic_id}/analysis").json()["generated_at"]

    second = client.post(f"/diagnostics/{diagnostic_id}/analyze")

    assert second.status_code == 200
    assert second.json() == first
    assert provider.calls == 1
    assert client.get(f"/diagnostics/{diagnostic_id}/analysis").json()["generated_at"] == generated_at
    assert _analysis_rows(diagnostic_id) == 1


def test_cached_analysis_is_returned_even_if_provider_would_now_fail(client, provider) -> None:
    diagnostic_id = _diagnostic(client)
    first = client.post(f"/diagnostics/{diagnostic_id}/analyze").json()
    provider.error = GeminiProviderResponseError("should not be called")

    response = client.post(f"/diagnostics/{diagnostic_id}/analyze")

    assert response.status_code == 200
    assert response.json() == first
    assert provider.calls == 1


# --- Consulta (GET) ----------------------------------------------------------------------------


def test_get_analysis_returns_404_without_calling_provider(client, provider) -> None:
    diagnostic_id = _diagnostic(client)

    missing_analysis = client.get(f"/diagnostics/{diagnostic_id}/analysis")
    missing_diagnostic = client.get("/diagnostics/999/analysis")

    assert missing_analysis.status_code == 404
    assert missing_analysis.json()["detail"] == "AI analysis not found"
    assert missing_diagnostic.status_code == 404
    assert missing_diagnostic.json()["detail"] == "Diagnostic not found"
    assert provider.calls == 0


def test_analyze_missing_diagnostic_returns_404_without_calling_provider(client, provider) -> None:
    response = client.post("/diagnostics/999/analyze")

    assert response.status_code == 404
    assert response.json()["detail"] == "Diagnostic not found"
    assert provider.calls == 0


def test_get_analysis_works_even_if_provider_configuration_is_broken(
    client, provider, monkeypatch: pytest.MonkeyPatch
) -> None:
    diagnostic_id = _diagnostic(client)
    client.post(f"/diagnostics/{diagnostic_id}/analyze")
    app.dependency_overrides.pop(get_ai_provider)
    monkeypatch.setattr("app.api.dependencies.settings.ai_provider", "not-a-provider")

    assert client.post(f"/diagnostics/{diagnostic_id}/analyze").status_code == 503
    assert client.get(f"/diagnostics/{diagnostic_id}/analysis").status_code == 200


# --- Errores: nada se persiste -----------------------------------------------------------------


def _unsafe_result() -> PreliminaryDiagnosticAnalysis:
    return PreliminaryDiagnosticAnalysis(summary="Falla confirmada en la bomba de agua.")


@pytest.mark.parametrize(
    ("configure", "expected_status"),
    [
        (lambda p: setattr(p, "result", _unsafe_result()), 422),
        (lambda p: setattr(p, "error", GeminiProviderResponseError("bad response")), 502),
        (lambda p: setattr(p, "error", GeminiProviderConfigurationError("missing key")), 503),
        (lambda p: setattr(p, "error", OpenAIProviderNotEnabledError("not enabled")), 503),
    ],
    ids=["resultado_inseguro", "gemini_502", "gemini_sin_config", "openai_no_habilitado"],
)
def test_failed_analysis_persists_nothing_and_keeps_status(client, provider, configure, expected_status) -> None:
    diagnostic_id = _diagnostic(client)
    configure(provider)

    response = client.post(f"/diagnostics/{diagnostic_id}/analyze")

    assert response.status_code == expected_status
    assert _analysis_rows(diagnostic_id) == 0
    assert _status(client, diagnostic_id) == "CREATED"
    assert client.get(f"/diagnostics/{diagnostic_id}/analysis").status_code == 404


def test_failed_analysis_can_be_retried(client, provider) -> None:
    diagnostic_id = _diagnostic(client)
    provider.error = GeminiProviderResponseError("temporary")
    assert client.post(f"/diagnostics/{diagnostic_id}/analyze").status_code == 502

    provider.error = None
    response = client.post(f"/diagnostics/{diagnostic_id}/analyze")

    assert response.status_code == 200
    assert provider.calls == 2
    assert _status(client, diagnostic_id) == "REVIEW"


# --- Estado del diagnóstico --------------------------------------------------------------------


@pytest.mark.parametrize("initial", [DiagnosticStatus.REVIEW, DiagnosticStatus.COMPLETED])
def test_status_only_moves_from_created(client, provider, initial) -> None:
    diagnostic_id = _diagnostic(client)
    with _db() as db:
        db.get(Diagnostic, diagnostic_id).status = initial
        db.commit()

    client.post(f"/diagnostics/{diagnostic_id}/analyze")

    assert _status(client, diagnostic_id) == initial.value
    assert _analysis_rows(diagnostic_id) == 1


# --- Análisis persistido inválido --------------------------------------------------------------


def _corrupt(diagnostic_id: int, **fields) -> None:
    with _db() as db:
        record = db.scalars(
            select(DiagnosticAIAnalysis).where(DiagnosticAIAnalysis.diagnostic_id == diagnostic_id)
        ).one()
        for name, value in fields.items():
            setattr(record, name, value)
        db.commit()


@pytest.mark.parametrize(
    "corruption",
    [{"result": {"unexpected": "shape"}}, {"schema_version": ANALYSIS_SCHEMA_VERSION - 1}],
    ids=["resultado_invalido", "version_antigua"],
)
def test_invalid_persisted_analysis_is_regenerated_in_place(client, provider, corruption) -> None:
    diagnostic_id = _diagnostic(client)
    client.post(f"/diagnostics/{diagnostic_id}/analyze")
    _corrupt(diagnostic_id, generated_at=datetime(2020, 1, 1, tzinfo=UTC), **corruption)
    assert client.get(f"/diagnostics/{diagnostic_id}/analysis").status_code == 404

    provider.name, provider.model = "gemini", "gemini-2.0-flash"
    response = client.post(f"/diagnostics/{diagnostic_id}/analyze")

    assert response.status_code == 200
    assert provider.calls == 2
    assert _analysis_rows(diagnostic_id) == 1
    stored = client.get(f"/diagnostics/{diagnostic_id}/analysis").json()
    assert (stored["provider"], stored["model"]) == ("gemini", "gemini-2.0-flash")
    assert stored["schema_version"] == ANALYSIS_SCHEMA_VERSION
    assert not stored["generated_at"].startswith("2020")


def test_failed_regeneration_keeps_the_existing_record(client, provider) -> None:
    diagnostic_id = _diagnostic(client)
    client.post(f"/diagnostics/{diagnostic_id}/analyze")
    _corrupt(diagnostic_id, result={"unexpected": "shape"})
    provider.error = GeminiProviderResponseError("down")

    assert client.post(f"/diagnostics/{diagnostic_id}/analyze").status_code == 502

    with _db() as db:
        record = db.scalars(select(DiagnosticAIAnalysis)).one()
        assert record.result == {"unexpected": "shape"}
        assert record.provider == "stub"


# --- Restricciones de base de datos ------------------------------------------------------------


def test_database_allows_at_most_one_analysis_per_diagnostic(client, provider) -> None:
    diagnostic_id = _diagnostic(client)
    client.post(f"/diagnostics/{diagnostic_id}/analyze")

    with _db() as db:
        db.add(
            DiagnosticAIAnalysis(
                diagnostic_id=diagnostic_id, provider="stub", schema_version=1, result={}
            )
        )
        with pytest.raises(IntegrityError):
            db.commit()


def test_deleting_a_diagnostic_deletes_its_analysis(client, provider) -> None:
    diagnostic_id = _diagnostic(client)
    client.post(f"/diagnostics/{diagnostic_id}/analyze")

    with _db() as db:
        db.delete(db.get(Diagnostic, diagnostic_id))
        db.commit()

    assert _analysis_rows(diagnostic_id) == 0
