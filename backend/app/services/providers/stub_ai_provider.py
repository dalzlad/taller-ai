from app.models.enums import DiagnosticEvidenceType
from app.schemas.ai_analysis import (
    AnalysisObservations,
    PreliminaryDiagnosticAnalysis,
    VehicleState,
)
from app.schemas.diagnostic_context import DiagnosticContext


class StubAIProvider:
    """Offline deterministic provider used until a real adapter is explicitly implemented."""

    def analyze(self, context: DiagnosticContext) -> PreliminaryDiagnosticAnalysis:
        image_observations = [
            f"Evidencia disponible para revisión: {evidence.file_name} (imagen)."
            for evidence in context.evidences
            if evidence.evidence_type == DiagnosticEvidenceType.IMAGE
        ]
        audio_observations = [
            f"Evidencia disponible para revisión: {evidence.file_name} (audio)."
            for evidence in context.evidences
            if evidence.evidence_type == DiagnosticEvidenceType.AUDIO
        ]
        return PreliminaryDiagnosticAnalysis(
            summary=(
                f'Evaluación preliminar generada con la información reportada '
                f'("{context.diagnostic.reported_symptoms}"); se requiere verificación mecánica.'
            ),
            vehicle_state=VehicleState.INDETERMINADO,
            observations=AnalysisObservations(audio=audio_observations, image=image_observations),
            possible_causes=[
                {
                    "cause": "Se requiere inspección mecánica adicional",
                    "confidence": 0.1,
                    "reasoning": "El proveedor stub no identifica fallas y solo organiza la información disponible.",
                    "based_on": [],
                }
            ],
            recommended_tests=["Realizar inspección visual y pruebas diagnósticas realizadas por un mecánico calificado."],
            safety_warnings=["No operar el vehículo si hay problemas de frenos, dirección, sobrecalentamiento, humo o fugas."],
            limitations=["La evaluación es preliminar y requiere confirmación física por un mecánico."],
        )
