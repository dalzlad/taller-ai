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

    # Signals used to detect that the provider already expressed, in its own words, the same
    # idea as REPAIR_STATE_LIMITATION / DISASSEMBLED_ENGINE_WARNING — so the auto-appended
    # safety net is skipped instead of duplicating a message the model already produced.
    _repair_context_pattern = re.compile(r"desarmad|reparaci[oó]n", re.IGNORECASE)
    _no_evidence_pattern = re.compile(
        r"no\s+(?:\w+\s+){0,3}(?:us|utiliz)\w*\s+como\s+evidencia", re.IGNORECASE
    )
    _no_start_or_handle_pattern = re.compile(
        r"no\s+(?:\w+\s+){0,3}(?:encend|arranqu|arranc|manipul)", re.IGNORECASE
    )

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
            if not any(cls._states_repair_evidence_exclusion(limitation) for limitation in analysis.limitations):
                analysis.limitations.append(REPAIR_STATE_LIMITATION)
            if not any(cls._warns_against_starting_disassembled_engine(warning) for warning in analysis.safety_warnings):
                analysis.safety_warnings.append(DISASSEMBLED_ENGINE_WARNING)
        return analysis

    @classmethod
    def _states_repair_evidence_exclusion(cls, text: str) -> bool:
        """True if `text` already says, in any wording, that repair/disassembly evidence was not
        used as proof of the reported symptom's cause — the same claim REPAIR_STATE_LIMITATION
        makes."""
        return bool(cls._repair_context_pattern.search(text) and cls._no_evidence_pattern.search(text))

    @classmethod
    def _warns_against_starting_disassembled_engine(cls, text: str) -> bool:
        """True if `text` already warns against starting/handling a disassembled engine, the same
        claim DISASSEMBLED_ENGINE_WARNING makes."""
        return bool(cls._repair_context_pattern.search(text) and cls._no_start_or_handle_pattern.search(text))
