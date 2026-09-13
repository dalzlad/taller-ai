from typing import Protocol, runtime_checkable

from app.schemas.ai_analysis import PreliminaryDiagnosticAnalysis
from app.schemas.diagnostic_context import DiagnosticContext


@runtime_checkable
class AIProvider(Protocol):
    """Provider-neutral contract for a multimodal preliminary diagnostic analysis."""

    def analyze(self, context: DiagnosticContext) -> PreliminaryDiagnosticAnalysis: ...
