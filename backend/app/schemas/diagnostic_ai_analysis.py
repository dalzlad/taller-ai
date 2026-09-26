from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.schemas.ai_analysis import PreliminaryDiagnosticAnalysis


class DiagnosticAIAnalysisRead(BaseModel):
    """A persisted analysis together with the provider metadata that produced it."""

    model_config = ConfigDict(from_attributes=True)

    diagnostic_id: int
    provider: str
    model: str | None
    schema_version: int
    generated_at: datetime
    result: PreliminaryDiagnosticAnalysis
