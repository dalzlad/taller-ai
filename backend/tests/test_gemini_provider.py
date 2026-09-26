import json
from pathlib import Path

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
from app.services.ai_safety import MANDATORY_LIMITATION, AISafety, UnsafeAIResultError
from app.services.providers.gemini_ai_provider import (
    GeminiAIProvider,
    GeminiProviderConfigurationError,
    GeminiProviderResponseError,
)
from app.services.storage_service import StorageService


def _storage_with_file(root: Path, relative_path: str, content: bytes = b"fake-bytes") -> StorageService:
    """A real StorageService backed by pytest's tmp_path, pre-seeded with one file, so
    evidence-loading code paths can be exercised without touching the project's real
    storage directory."""
    full_path = root / relative_path
    full_path.parent.mkdir(parents=True, exist_ok=True)
    full_path.write_bytes(content)
    return StorageService(root=root)


def _context(evidences: list[DiagnosticEvidenceContext] | None = None) -> DiagnosticContext:
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
        evidences=evidences if evidences is not None else [],
    )


def _fake_analysis_payload() -> dict:
    return {
        "summary": "Evaluación preliminar generada por Gemini; requiere verificación mecánica.",
        "vehicle_state": "en_uso",
        "observations": {"audio": ["Vibración reportada al acelerar."], "image": []},
        "possible_causes": [
            {
                "cause": "Bujía en mal estado",
                "confidence": 0.4,
                "reasoning": "Coincide con los síntomas reportados.",
                "based_on": ["audio"],
            }
        ],
        "recommended_tests": ["Inspeccionar bujías y bobinas de encendido."],
        "safety_warnings": [],
        "limitations": [],
    }


class _FakeResponse:
    def __init__(self, body: dict, status_code: int = 200) -> None:
        self._body = body
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            import httpx

            raise httpx.HTTPStatusError("error", request=None, response=self)  # type: ignore[arg-type]

    def json(self) -> dict:
        return self._body


class _FakeClient:
    """Duck-typed stand-in for httpx.Client; records the call and never touches the network."""

    def __init__(self, body: dict, status_code: int = 200) -> None:
        self._body = body
        self._status_code = status_code
        self.calls: list[dict] = []

    def post(self, url: str, params: dict, json: dict):
        self.calls.append({"url": url, "params": params, "json": json})
        return _FakeResponse(self._body, self._status_code)

    def close(self) -> None:
        pass


def _gemini_success_body(payload: dict) -> dict:
    return {"candidates": [{"content": {"parts": [{"text": json.dumps(payload)}]}}]}


def test_gemini_provider_implements_contract() -> None:
    assert isinstance(GeminiAIProvider(api_key="k", model="gemini-1.5-flash"), AIProvider)


def test_gemini_provider_requires_api_key_and_model() -> None:
    provider = GeminiAIProvider(api_key=None, model=None)
    with pytest.raises(GeminiProviderConfigurationError, match="GEMINI_API_KEY and GEMINI_MODEL"):
        provider.analyze(_context())


def test_gemini_provider_calls_api_and_parses_analysis_without_network() -> None:
    fake_client = _FakeClient(_gemini_success_body(_fake_analysis_payload()))
    provider = GeminiAIProvider(api_key="test-key", model="gemini-1.5-flash", client=fake_client)

    result = provider.analyze(_context())

    assert result.summary == _fake_analysis_payload()["summary"]
    assert result.possible_causes[0].cause == "Bujía en mal estado"
    # No real network call is made; only the fake client recorded the request.
    assert len(fake_client.calls) == 1
    assert fake_client.calls[0]["params"] == {"key": "test-key"}
    assert "gemini-1.5-flash:generateContent" in fake_client.calls[0]["url"]
    # AISafety must still apply to Gemini's output like any other provider.
    validated = AISafety.validate(result)
    assert MANDATORY_LIMITATION in validated.limitations


def test_gemini_provider_flags_unsupported_video_evidence_as_limitation() -> None:
    body = _gemini_success_body(_fake_analysis_payload())
    fake_client = _FakeClient(body)
    provider = GeminiAIProvider(api_key="test-key", model="gemini-1.5-flash", client=fake_client)
    context = _context(
        evidences=[
            DiagnosticEvidenceContext(
                evidence_type=DiagnosticEvidenceType.VIDEO,
                file_name="clip.mp4", mime_type="video/mp4",
                file_reference="diagnostics/7/clip.mp4",
            ),
        ]
    )

    result = provider.analyze(context)

    assert any("VIDEO" in limitation for limitation in result.limitations)
    # Video evidence must not be forwarded as an inline data part to the API.
    sent_parts = fake_client.calls[0]["json"]["contents"][0]["parts"]
    assert all("inline_data" not in part for part in sent_parts)


def test_gemini_provider_includes_audio_evidence_as_inline_data(tmp_path: Path) -> None:
    body = _gemini_success_body(_fake_analysis_payload())
    fake_client = _FakeClient(body)
    storage = _storage_with_file(tmp_path, "diagnostics/7/motor.mp3")
    provider = GeminiAIProvider(
        api_key="test-key", model="gemini-1.5-flash", client=fake_client, storage_service=storage
    )
    context = _context(
        evidences=[
            DiagnosticEvidenceContext(
                evidence_type=DiagnosticEvidenceType.AUDIO,
                file_name="motor.mp3", mime_type="audio/mpeg",
                file_reference="diagnostics/7/motor.mp3", description="Ruido al ralentí",
            ),
        ]
    )

    result = provider.analyze(context)

    sent_parts = fake_client.calls[0]["json"]["contents"][0]["parts"]
    audio_parts = [p for p in sent_parts if "inline_data" in p]
    assert len(audio_parts) == 1
    # audio/mpeg is normalized to the MIME type Gemini documents (audio/mp3).
    assert audio_parts[0]["inline_data"]["mime_type"] == "audio/mp3"
    assert audio_parts[0]["inline_data"]["data"]  # non-empty base64 payload
    assert not result.limitations or "motor.mp3" not in " ".join(result.limitations)
    # The system prompt must ask the model to describe audible engine characteristics and never
    # invent sounds beyond what the recording actually contains.
    system_text = fake_client.calls[0]["json"]["system_instruction"]["parts"][0]["text"]
    assert "audio" in system_text.lower()
    assert "golpeteos" in system_text.lower() or "knocking" in system_text.lower()
    assert "no inventes" in system_text.lower()


def test_gemini_provider_combines_image_and_audio_evidence_in_one_call(tmp_path: Path) -> None:
    body = _gemini_success_body(_fake_analysis_payload())
    fake_client = _FakeClient(body)
    storage = StorageService(root=tmp_path)
    (tmp_path / "diagnostics/7").mkdir(parents=True)
    (tmp_path / "diagnostics/7/motor.jpg").write_bytes(b"fake-image-bytes")
    (tmp_path / "diagnostics/7/motor.wav").write_bytes(b"fake-audio-bytes")
    provider = GeminiAIProvider(
        api_key="test-key", model="gemini-1.5-flash", client=fake_client, storage_service=storage
    )
    context = _context(
        evidences=[
            DiagnosticEvidenceContext(
                evidence_type=DiagnosticEvidenceType.IMAGE,
                file_name="motor.jpg", mime_type="image/jpeg",
                file_reference="diagnostics/7/motor.jpg", description="Zona del motor",
            ),
            DiagnosticEvidenceContext(
                evidence_type=DiagnosticEvidenceType.AUDIO,
                file_name="motor.wav", mime_type="audio/wav",
                file_reference="diagnostics/7/motor.wav", description="Sonido al acelerar",
            ),
        ]
    )

    provider.analyze(context)

    # A single generateContent call carries both pieces of evidence together.
    assert len(fake_client.calls) == 1
    sent_parts = fake_client.calls[0]["json"]["contents"][0]["parts"]
    mime_types = {p["inline_data"]["mime_type"] for p in sent_parts if "inline_data" in p}
    assert mime_types == {"image/jpeg", "audio/wav"}


def test_gemini_provider_flags_unsupported_audio_format_as_limitation_not_crash() -> None:
    body = _gemini_success_body(_fake_analysis_payload())
    fake_client = _FakeClient(body)
    provider = GeminiAIProvider(api_key="test-key", model="gemini-1.5-flash", client=fake_client)
    context = _context(
        evidences=[
            DiagnosticEvidenceContext(
                evidence_type=DiagnosticEvidenceType.AUDIO,
                file_name="motor.m4a", mime_type="audio/mp4",
                file_reference="diagnostics/7/motor.m4a",
            ),
        ]
    )

    result = provider.analyze(context)

    assert any("motor.m4a" in limitation and "no soportado" in limitation for limitation in result.limitations)
    # The unsupported audio must not reach the API as an inline data part.
    sent_parts = fake_client.calls[0]["json"]["contents"][0]["parts"]
    assert all("inline_data" not in part for part in sent_parts)


def test_gemini_provider_notes_unreadable_image_evidence_instead_of_failing() -> None:
    fake_client = _FakeClient(_gemini_success_body(_fake_analysis_payload()))
    provider = GeminiAIProvider(api_key="test-key", model="gemini-1.5-flash", client=fake_client)
    context = _context(
        evidences=[
            DiagnosticEvidenceContext(
                evidence_type=DiagnosticEvidenceType.IMAGE,
                file_name="missing.jpg", mime_type="image/jpeg",
                file_reference="diagnostics/999/missing.jpg",
            )
        ]
    )

    result = provider.analyze(context)

    assert any("missing.jpg" in limitation for limitation in result.limitations)


def test_gemini_provider_raises_on_unparseable_response() -> None:
    fake_client = _FakeClient({"candidates": [{"content": {"parts": [{"text": "not json"}]}}]})
    provider = GeminiAIProvider(api_key="test-key", model="gemini-1.5-flash", client=fake_client)

    with pytest.raises(GeminiProviderResponseError):
        provider.analyze(_context())


def test_gemini_provider_raises_when_blocked_with_no_candidates() -> None:
    fake_client = _FakeClient({"candidates": [], "promptFeedback": {"blockReason": "SAFETY"}})
    provider = GeminiAIProvider(api_key="test-key", model="gemini-1.5-flash", client=fake_client)

    with pytest.raises(GeminiProviderResponseError, match="SAFETY"):
        provider.analyze(_context())


def test_ai_safety_still_rejects_confirmed_language_from_gemini() -> None:
    unsafe_payload = _fake_analysis_payload()
    unsafe_payload["summary"] = "La falla está confirmada."
    fake_client = _FakeClient(_gemini_success_body(unsafe_payload))
    provider = GeminiAIProvider(api_key="test-key", model="gemini-1.5-flash", client=fake_client)

    result = provider.analyze(_context())
    with pytest.raises(UnsafeAIResultError):
        AISafety.validate(result)


def test_factory_creates_gemini_provider_and_reads_only_from_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.services.ai_provider_factory.settings.gemini_api_key", "env-key")
    monkeypatch.setattr("app.services.ai_provider_factory.settings.gemini_model", "gemini-1.5-flash")

    provider = AIProviderFactory.create("gemini")

    assert isinstance(provider, GeminiAIProvider)
    assert provider.api_key == "env-key"
    assert provider.model == "gemini-1.5-flash"


def test_no_hardcoded_api_key_in_provider_or_factory_source() -> None:
    import inspect

    from app.services import ai_provider_factory
    from app.services.providers import gemini_ai_provider

    provider_source = inspect.getsource(gemini_ai_provider)
    factory_source = inspect.getsource(ai_provider_factory)
    # Common Google API key prefix must never appear literally in source.
    assert "AIza" not in provider_source
    assert "AIza" not in factory_source
    # The provider itself must never read settings directly; only the factory may,
    # so that constructing the provider directly in tests never touches real credentials.
    assert "settings." not in provider_source
    assert "settings.gemini_api_key" in factory_source
    assert "settings.gemini_model" in factory_source


# --- Timeout configurable (GEMINI_TIMEOUT_SECONDS) --------------------------------------------


def test_gemini_provider_uses_its_configured_timeout_for_the_http_client(monkeypatch: pytest.MonkeyPatch) -> None:
    created: list[float] = []

    def fake_httpx_client(timeout: float) -> _FakeClient:
        created.append(timeout)
        return _FakeClient(_gemini_success_body(_fake_analysis_payload()))

    monkeypatch.setattr("app.services.providers.gemini_ai_provider.httpx.Client", fake_httpx_client)

    GeminiAIProvider(api_key="k", model="m", timeout_seconds=12.5).analyze(_context())

    assert created == [12.5]


def test_gemini_provider_timeout_defaults_to_30_seconds() -> None:
    assert GeminiAIProvider(api_key="k", model="m").timeout_seconds == 30.0


def test_factory_passes_gemini_timeout_from_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.services.ai_provider_factory.settings.gemini_timeout_seconds", 45.0)

    provider = AIProviderFactory.create("gemini", api_key="k", model="m")

    assert isinstance(provider, GeminiAIProvider)
    assert provider.timeout_seconds == 45.0


def test_gemini_timeout_setting_default_and_validation() -> None:
    from pydantic import ValidationError

    from app.core.config import Settings

    assert Settings.model_fields["gemini_timeout_seconds"].default == 30.0
    for invalid in (0, -1, 301):
        with pytest.raises(ValidationError):
            Settings(_env_file=None, gemini_timeout_seconds=invalid)


# --- Metadatos del proveedor (se guardan con cada análisis) ------------------------------------


def test_providers_expose_name_and_model_for_persisted_metadata() -> None:
    from app.services.providers.openai_ai_provider import OpenAIAIProvider
    from app.services.providers.stub_ai_provider import StubAIProvider

    stub = StubAIProvider()
    gemini = GeminiAIProvider(api_key="k", model="gemini-1.5-flash")
    openai = OpenAIAIProvider(model="gpt-x")

    assert (stub.name, stub.model) == ("stub", None)
    assert (gemini.name, gemini.model) == ("gemini", "gemini-1.5-flash")
    assert (openai.name, openai.model) == ("openai", "gpt-x")
    assert all(isinstance(p, AIProvider) for p in (stub, gemini, openai))
