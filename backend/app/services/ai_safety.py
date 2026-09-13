import re

from app.schemas.ai_analysis import PreliminaryDiagnosticAnalysis, VehicleState

MANDATORY_LIMITATION = "La evaluación es preliminar y requiere confirmación física por un mecánico."

# Auto-appended whenever the model reports the vehicle as already under repair, so a
# disassembled-engine photo is never allowed to silently pass as evidence of the audio symptom's
# cause, even if the provider's own output omits saying so.
REPAIR_STATE_LIMITATION = (
    "La imagen muestra el motor ya desarmado por un taller; no se usó como evidencia directa "
    "de la causa del síntoma reportado en el audio."
)

# Auto-appended whenever the vehicle is reported as under repair and no safety warning already
# covers it, so a disassembled engine is never implicitly presented as safe to start or handle.
DISASSEMBLED_ENGINE_WARNING = (
    "No intente encender ni manipular el motor: la evidencia muestra que está desarmado y en "
    "proceso de reparación en un taller."
)


class UnsafeAIResultError(ValueError):
    """Provider output attempted to state an unverified fault as final."""


class AISafety:
    _confirmation_pattern = re.compile(
        r"\b(confirmed|confirmada|confirmado|definitive|definitivo|definitiva|diagnosis confirmed|falla confirmada)\b",
        re.IGNORECASE,
    )
    _disassembled_warning_pattern = re.compile(r"desarmad", re.IGNORECASE)

    @classmethod
    def validate(cls, analysis: PreliminaryDiagnosticAnalysis) -> PreliminaryDiagnosticAnalysis:
        # Limitations may explain that nothing is confirmed; only diagnostic claims are inspected.
        claims = [
            analysis.summary,
            *analysis.observations.audio,
            *analysis.observations.image,
            *analysis.recommended_tests,
            *analysis.safety_warnings,
            *(cause.cause for cause in analysis.possible_causes),
            *(cause.reasoning for cause in analysis.possible_causes),
        ]
        if any(cls._confirmation_pattern.search(claim) for claim in claims):
            raise UnsafeAIResultError("AI output cannot present a fault as confirmed or definitive")
        if MANDATORY_LIMITATION not in analysis.limitations:
            analysis.limitations.append(MANDATORY_LIMITATION)
        if analysis.vehicle_state == VehicleState.EN_REPARACION:
            if REPAIR_STATE_LIMITATION not in analysis.limitations:
                analysis.limitations.append(REPAIR_STATE_LIMITATION)
            if not any(cls._disassembled_warning_pattern.search(warning) for warning in analysis.safety_warnings):
                analysis.safety_warnings.append(DISASSEMBLED_ENGINE_WARNING)
        return analysis
