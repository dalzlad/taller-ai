from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

# Version of the PreliminaryDiagnosticAnalysis contract stored in diagnostic_ai_analyses.result.
# Bump it whenever the contract changes incompatibly: stored analyses with an older version are
# then treated as missing and regenerated instead of breaking reads.
ANALYSIS_SCHEMA_VERSION = 1


class VehicleState(str, Enum):
    """Whether the evidence indicates the vehicle is running normally, already under repair, or
    that its state cannot be determined from the available evidence."""

    EN_USO = "en_uso"
    EN_REPARACION = "en_reparacion"
    INDETERMINADO = "indeterminado"


class CauseBasis(str, Enum):
    """Which evidence channel(s) support a given possible cause."""

    AUDIO = "audio"
    IMAGE = "image"
    AMBOS = "ambos"


class PossibleCause(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cause: str = Field(min_length=1, max_length=500)
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str = Field(min_length=1, max_length=5_000)
    based_on: list[CauseBasis] = Field(default_factory=list)


class AnalysisObservations(BaseModel):
    """Findings kept separate by evidence channel, so an audio-only or image-only finding is
    never presented as if it were corroborated by the other channel."""

    model_config = ConfigDict(extra="forbid")

    audio: list[str] = Field(default_factory=list)
    image: list[str] = Field(default_factory=list)


class PreliminaryDiagnosticAnalysis(BaseModel):
    """Non-confirmatory AI-assisted diagnostic output."""

    model_config = ConfigDict(extra="forbid")

    summary: str = Field(min_length=1, max_length=5_000)
    vehicle_state: VehicleState = VehicleState.INDETERMINADO
    observations: AnalysisObservations = Field(default_factory=AnalysisObservations)
    possible_causes: list[PossibleCause] = Field(default_factory=list)
    recommended_tests: list[str] = Field(default_factory=list)
    safety_warnings: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)

    @classmethod
    def from_knowledge_response(cls, response: dict[str, Any]) -> "PreliminaryDiagnosticAnalysis":
        """Legacy parser retained for callers migrating to AIProvider."""
        return cls.model_validate(response)
