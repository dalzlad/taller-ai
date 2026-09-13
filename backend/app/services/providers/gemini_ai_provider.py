import base64
import json
from pathlib import Path
from typing import Any

import httpx
from pydantic import ValidationError

from app.models.enums import DiagnosticEvidenceType
from app.schemas.ai_analysis import PreliminaryDiagnosticAnalysis
from app.schemas.diagnostic_context import DiagnosticContext, DiagnosticEvidenceContext
from app.services.storage_service import StorageService

GEMINI_API_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
DEFAULT_TIMEOUT_SECONDS = 30.0

SYSTEM_INSTRUCTIONS = (
    "Eres un asistente de diagnóstico vehicular. Tu trabajo es analizar la evidencia visual y "
    "auditiva de un vehículo (fotos del vehículo o motor, y grabaciones de sonido del motor u "
    "otros componentes) para generar un diagnóstico preliminar, útil para el usuario y para un "
    "mecánico que luego confirme el caso.\n\n"
    "SOBRE EL AUDIO: cuando se adjunte una grabación, descríbela basándote únicamente en lo que "
    "realmente se escucha en ella — golpeteos (knocking), silbidos, vibración, ruidos metálicos, "
    "rechinidos, chillidos, etc. No inventes sonidos, matices ni detalles que no percibas con "
    "claridad en el audio proporcionado.\n\n"
    "PASO 1 — CLASIFICA CADA IMAGEN\n"
    "Antes de razonar sobre causas, clasifica cada imagen en una de estas categorías:\n"
    "- \"vehiculo_exterior\": foto del auto completo o exterior, sin detalle de motor.\n"
    "- \"motor_capo_abierto\": motor visible, ensamblado y en estado normal de funcionamiento.\n"
    "- \"motor_desarmado_reparacion\": motor con piezas removidas, evidencia de estar en proceso "
    "de servicio/reparación en un taller.\n"
    "- \"componente_especifico\": una pieza aislada (arrancador, batería, correa, etc.).\n"
    "- \"otro\": no aporta información relevante al diagnóstico.\n\n"
    "PASO 2 — EVALÚA COHERENCIA TEMPORAL\n"
    "- Si alguna imagen es \"motor_desarmado_reparacion\", NO la uses como evidencia de la CAUSA "
    "del síntoma auditivo. Trátala únicamente como contexto de que el vehículo YA está siendo "
    "intervenido por un taller.\n"
    "- Solo cruces evidencia de audio e imagen como soporte conjunto de una misma causa "
    "(\"based_on\": [\"ambos\"]) si ambas corresponden al mismo estado del vehículo (por ejemplo, "
    "motor ensamblado y en funcionamiento normal).\n"
    "- Si el estado del vehículo es ambiguo o contradictorio entre audio e imagen, declara "
    "\"vehicle_state\": \"indeterminado\" explícitamente y reduce la confianza (\"confidence\") de "
    "las causas propuestas.\n\n"
    "PASO 3 — GENERA EL DIAGNÓSTICO\n"
    "Responde exclusivamente con el JSON solicitado por el esquema de la respuesta, con este "
    "significado por campo:\n"
    "- \"summary\": resumen breve del caso; indica si el vehículo parece estar en uso normal o ya "
    "en proceso de reparación.\n"
    "- \"vehicle_state\": \"en_uso\", \"en_reparacion\" o \"indeterminado\".\n"
    "- \"observations.audio\": hallazgos derivados únicamente del audio.\n"
    "- \"observations.image\": un hallazgo por imagen analizada, mencionando su categoría.\n"
    "- \"possible_causes[].based_on\": qué evidencia respalda cada causa (\"audio\", \"image\" y/o "
    "\"ambos\").\n"
    "- \"limitations\": si \"vehicle_state\" es \"en_reparacion\", incluye explícitamente que la "
    "imagen muestra el motor ya desarmado por un taller y que no se usó como evidencia directa de "
    "la causa del síntoma reportado en el audio.\n\n"
    "REGLAS OBLIGATORIAS:\n"
    "- Nunca inventes una relación causal entre una imagen de reparación en curso y el síntoma "
    "reportado en el audio.\n"
    "- Si el estado del vehículo es indeterminado, decláralo explícitamente en \"vehicle_state\" y "
    "baja la confianza de todas las causas propuestas.\n"
    "- \"confidence\" debe ser un número entre 0.0 y 1.0.\n"
    "- Nunca sugieras que el usuario intente encender o manipular un motor que aparece desarmado "
    "en las imágenes; inclúyelo siempre en \"safety_warnings\" si aplica.\n"
    "- Nunca afirmes que una falla está confirmada, definitiva o verificada: toda causa posible es "
    "una hipótesis que requiere inspección física de un mecánico calificado."
)

# Gemini's documented audio MIME types, keyed by the mime types this backend actually stores
# for accepted uploads (see DiagnosticEvidenceService._ALLOWED). audio/mp4 (.m4a) is deliberately
# absent: Gemini's generateContent does not document support for it, so it is treated as an
# unsupported format rather than sent speculatively.
_GEMINI_AUDIO_MIME_TYPES: dict[str, str] = {
    "audio/mpeg": "audio/mp3",
    "audio/mp3": "audio/mp3",
    "audio/wav": "audio/wav",
    "audio/x-wav": "audio/wav",
    "audio/aac": "audio/aac",
    "audio/ogg": "audio/ogg",
    "audio/flac": "audio/flac",
    "audio/aiff": "audio/aiff",
    "audio/x-aiff": "audio/aiff",
}

# A subset of OpenAPI schema understood by Gemini's structured-output mode (responseSchema).
RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "vehicle_state": {"type": "string", "enum": ["en_uso", "en_reparacion", "indeterminado"]},
        "observations": {
            "type": "object",
            "properties": {
                "audio": {"type": "array", "items": {"type": "string"}},
                "image": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["audio", "image"],
        },
        "possible_causes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "cause": {"type": "string"},
                    "confidence": {"type": "number"},
                    "reasoning": {"type": "string"},
                    "based_on": {
                        "type": "array",
                        "items": {"type": "string", "enum": ["audio", "image", "ambos"]},
                    },
                },
                "required": ["cause", "confidence", "reasoning", "based_on"],
            },
        },
        "recommended_tests": {"type": "array", "items": {"type": "string"}},
        "safety_warnings": {"type": "array", "items": {"type": "string"}},
        "limitations": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "summary",
        "vehicle_state",
        "observations",
        "possible_causes",
        "recommended_tests",
        "safety_warnings",
        "limitations",
    ],
}


class GeminiProviderConfigurationError(RuntimeError):
    """Raised when the gemini provider is used without the required credentials."""


class GeminiProviderResponseError(RuntimeError):
    """Raised when Gemini's response cannot be parsed into the analysis contract."""


class GeminiAIProvider:
    """Google Gemini adapter; performs a real multimodal call against the Gemini REST API.

    Sends image and audio evidence inline in the same ``generateContent`` call as
    ``inline_data`` parts, so the model can reason over both together (e.g. an engine
    photo plus a recording of the noise it makes). Video evidence and unsupported audio
    formats are not sent; they are surfaced as a ``limitation`` instead of failing.

    Uses direct HTTP calls (via httpx, already a project dependency) instead of the
    ``google-generativeai`` SDK: that package is deprecated upstream in favor of
    ``google-genai`` and pulls a heavy transitive dependency tree (grpc, cryptography,
    google-auth, ...) that this backend does not otherwise need. The REST surface used
    here (``generateContent`` with inline image data and ``responseSchema``) is small
    and stable enough that a thin HTTP client is simpler to maintain.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        storage_service: StorageService | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        # No fallback to settings here, by design: only AIProviderFactory resolves defaults
        # from the environment, so constructing this class directly (e.g. in tests) never
        # silently picks up real ambient credentials.
        self.api_key = api_key
        self.model = model
        self._storage_service = storage_service or StorageService()
        self._client = client

    def analyze(self, context: DiagnosticContext) -> PreliminaryDiagnosticAnalysis:
        if not self.api_key or not self.model:
            raise GeminiProviderConfigurationError(
                "GEMINI_API_KEY and GEMINI_MODEL must be set in the environment to use the gemini provider."
            )

        evidence_parts, limitations = self._build_evidence_parts(context)
        parts: list[dict[str, Any]] = [{"text": self._build_prompt(context)}, *evidence_parts]

        payload = {
            "system_instruction": {"parts": [{"text": SYSTEM_INSTRUCTIONS}]},
            "contents": [{"role": "user", "parts": parts}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseSchema": RESPONSE_SCHEMA,
            },
        }

        response_body = self._call_gemini(payload)
        analysis = self._parse_response(response_body)
        for limitation in limitations:
            if limitation not in analysis.limitations:
                analysis.limitations.append(limitation)
        return analysis

    def _build_prompt(self, context: DiagnosticContext) -> str:
        return json.dumps(
            {
                "vehicle": context.vehicle.model_dump(mode="json"),
                "diagnostic": context.diagnostic.model_dump(mode="json"),
                "history": context.history,
                "technical_knowledge": context.technical_knowledge,
                "evidence_summary": [
                    {
                        "type": evidence.evidence_type.value,
                        "file_name": evidence.file_name,
                        "description": evidence.description,
                    }
                    for evidence in context.evidences
                ],
            },
            ensure_ascii=False,
        )

    def _build_evidence_parts(self, context: DiagnosticContext) -> tuple[list[dict[str, Any]], list[str]]:
        """Build inline_data parts for evidence Gemini can consume, plus a limitation per
        piece of evidence that was excluded (unsupported type, unsupported format, or
        unreadable file) so nothing is dropped silently."""
        parts: list[dict[str, Any]] = []
        limitations: list[str] = []
        for evidence in context.evidences:
            if evidence.evidence_type == DiagnosticEvidenceType.IMAGE:
                image_part = self._load_inline_part(evidence, evidence.mime_type or "application/octet-stream")
                if image_part is None:
                    limitations.append(
                        f"No fue posible leer la evidencia de imagen '{evidence.file_name}'; se excluyó del análisis."
                    )
                else:
                    parts.append(image_part)
            elif evidence.evidence_type == DiagnosticEvidenceType.AUDIO:
                gemini_mime_type = _GEMINI_AUDIO_MIME_TYPES.get((evidence.mime_type or "").lower().strip())
                if gemini_mime_type is None:
                    limitations.append(
                        f"Formato de audio no soportado por Gemini ('{evidence.mime_type}', archivo "
                        f"'{evidence.file_name}'); se excluyó del análisis de sonido del motor."
                    )
                    continue
                audio_part = self._load_inline_part(evidence, gemini_mime_type)
                if audio_part is None:
                    limitations.append(
                        f"No fue posible leer la evidencia de audio '{evidence.file_name}'; se excluyó del análisis."
                    )
                else:
                    parts.append(audio_part)
            else:
                # Video evidence is intentionally not sent to the model yet; the limitation
                # makes this explicit instead of silently ignoring the evidence.
                limitations.append(
                    f"Evidencia de tipo {evidence.evidence_type.value} ('{evidence.file_name}') aún no es "
                    "analizada por este proveedor; queda pendiente para una etapa posterior."
                )
        return parts, limitations

    def _load_inline_part(self, evidence: DiagnosticEvidenceContext, mime_type: str) -> dict[str, Any] | None:
        file_path = self._resolve_evidence_path(evidence.file_reference)
        if file_path is None:
            return None
        content = file_path.read_bytes()
        return {
            "inline_data": {
                "mime_type": mime_type,
                "data": base64.b64encode(content).decode("ascii"),
            }
        }

    def _resolve_evidence_path(self, file_reference: str) -> Path | None:
        # Legacy evidence may carry a remote URL instead of a local storage reference;
        # get_file() safely returns None for anything outside the storage root.
        try:
            return self._storage_service.get_file(file_reference)
        except ValueError:
            return None

    def _call_gemini(self, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{GEMINI_API_BASE_URL}/models/{self.model}:generateContent"
        client = self._client or httpx.Client(timeout=DEFAULT_TIMEOUT_SECONDS)
        owns_client = self._client is None
        try:
            response = client.post(url, params={"key": self.api_key}, json=payload)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as exc:
            raise GeminiProviderResponseError(f"Gemini API request failed: {exc}") from exc
        finally:
            if owns_client:
                client.close()

    def _parse_response(self, data: dict[str, Any]) -> PreliminaryDiagnosticAnalysis:
        candidates = data.get("candidates") or []
        if not candidates:
            block_reason = (data.get("promptFeedback") or {}).get("blockReason")
            raise GeminiProviderResponseError(f"Gemini returned no candidates (blockReason={block_reason}).")
        try:
            text = candidates[0]["content"]["parts"][0]["text"]
            parsed = json.loads(text)
            return PreliminaryDiagnosticAnalysis.model_validate(parsed)
        except (KeyError, IndexError, TypeError, json.JSONDecodeError, ValidationError) as exc:
            raise GeminiProviderResponseError(
                f"Gemini response could not be parsed into the expected analysis contract: {exc}"
            ) from exc
