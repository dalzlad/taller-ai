from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import DiagnosticStatus, MediaType
from app.schemas.ai_analysis import PreliminaryDiagnosticAnalysis


class DiagnosticCreate(BaseModel):
    vehicle_id: int = Field(gt=0)
    reported_symptoms: str = Field(min_length=3, max_length=10_000)
    mechanic_notes: Optional[str] = Field(default=None, max_length=10_000)


class DiagnosticRead(DiagnosticCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: DiagnosticStatus
    ai_analysis: Optional[PreliminaryDiagnosticAnalysis] = None
    created_at: datetime
    updated_at: datetime


class DiagnosticMediaCreate(BaseModel):
    type: MediaType
    file_url: str = Field(min_length=1, max_length=2048)
    description: Optional[str] = Field(default=None, max_length=10_000)

    @field_validator("file_url")
    @classmethod
    def non_empty_url(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("file_url cannot be empty")
        return value


class DiagnosticMediaRead(DiagnosticMediaCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    diagnostic_id: int
    created_at: datetime


class DiagnosticFindingCreate(BaseModel):
    component: str = Field(min_length=1, max_length=120)
    finding: str = Field(min_length=1, max_length=10_000)
    severity: str = Field(min_length=1, max_length=30)
    confidence: Optional[int] = Field(default=None, ge=0, le=100)
    recommendation: Optional[str] = Field(default=None, max_length=10_000)


class DiagnosticFindingRead(DiagnosticFindingCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    diagnostic_id: int
    created_at: datetime
