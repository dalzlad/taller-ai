from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import DiagnosticEvidenceType


class DiagnosticEvidenceCreate(BaseModel):
    """Metadata parsed from the multipart request after the file is validated."""

    description: str | None = Field(default=None, max_length=10_000)


class DiagnosticEvidenceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    diagnostic_id: int
    evidence_type: DiagnosticEvidenceType
    file_name: str
    mime_type: str
    file_size: int
    description: str | None
    created_at: datetime
