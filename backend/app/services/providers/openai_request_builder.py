from dataclasses import dataclass
from typing import Any

from app.schemas.diagnostic_context import DiagnosticContext


@dataclass(frozen=True)
class OpenAIRequest:
    """Provider-internal request representation; it contains references, never media bytes."""

    system_instructions: str
    textual_context: dict[str, Any]
    evidences: list[dict[str, Any]]
    metadata: dict[str, Any]


class OpenAIRequestBuilder:
    """Builds a future multimodal request without HTTP, SDK, or database dependencies."""

    system_instructions = (
        "Produce a preliminary mechanical assessment. Never state an unverified fault as confirmed or definitive."
    )

    def build(self, context: DiagnosticContext) -> OpenAIRequest:
        return OpenAIRequest(
            system_instructions=self.system_instructions,
            textual_context={
                "symptoms": context.diagnostic.reported_symptoms,
                "mechanic_notes": context.diagnostic.mechanic_notes,
                "vehicle": context.vehicle.model_dump(mode="json"),
                "history": context.history,
                "technical_knowledge": context.technical_knowledge,
            },
            evidences=[
                {
                    "type": evidence.evidence_type.value,
                    "file_name": evidence.file_name,
                    "mime_type": evidence.mime_type,
                    "reference": evidence.file_reference,
                    "description": evidence.description,
                }
                for evidence in context.evidences
            ],
            metadata={
                "diagnostic_id": context.diagnostic.id,
                "diagnostic_status": context.diagnostic.status.value,
            },
        )
