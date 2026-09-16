from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import DiagnosticEvidenceType, DiagnosticStatus


class DiagnosticVehicleContext(BaseModel):
    id: int
    brand: str
    model: str
    year: int
    engine: str | None = None
    mileage: int
    plate: str
    vin: str | None = None


class DiagnosticDetailsContext(BaseModel):
    id: int
    reported_symptoms: str
    mechanic_notes: str | None = None
    status: DiagnosticStatus


class DiagnosticEvidenceContext(BaseModel):
    """A file reference only. Providers decide later how to fetch supported media."""

    evidence_type: DiagnosticEvidenceType
    file_name: str
    mime_type: str
    file_reference: str
    description: str | None = None


class DiagnosticContext(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=False)

    vehicle: DiagnosticVehicleContext
    diagnostic: DiagnosticDetailsContext
    history: dict[str, Any] = Field(default_factory=dict)
    evidences: list[DiagnosticEvidenceContext] = Field(default_factory=list)
    technical_knowledge: dict[str, Any] = Field(default_factory=dict)
