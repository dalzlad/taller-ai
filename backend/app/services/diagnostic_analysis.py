from datetime import UTC, datetime

from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.agents.diagnostic_agent import DiagnosticAgent, DiagnosticNotFoundError
from app.models import DiagnosticAIAnalysis
from app.models.enums import DiagnosticStatus
from app.repositories.domain import DomainRepository
from app.schemas.ai_analysis import ANALYSIS_SCHEMA_VERSION, PreliminaryDiagnosticAnalysis
from app.services.ai_provider import AIProvider


class AIAnalysisNotFoundError(Exception):
    """Raised when a diagnostic has no valid persisted analysis."""


def load_valid_analysis(record: DiagnosticAIAnalysis | None) -> PreliminaryDiagnosticAnalysis | None:
    """The stored result, or None when there is none or it no longer matches the current contract."""
    if record is None or record.schema_version != ANALYSIS_SCHEMA_VERSION:
        return None
    try:
        return PreliminaryDiagnosticAnalysis.model_validate(record.result)
    except ValidationError:
        return None


def get_persisted_analysis(
    db: Session, diagnostic_id: int, repository: DomainRepository | None = None
) -> DiagnosticAIAnalysis:
    """Read-only lookup; never calls the AI provider."""
    repository = repository or DomainRepository()
    if not repository.get_diagnostic(db, diagnostic_id):
        raise DiagnosticNotFoundError(f"Diagnostic {diagnostic_id} not found")
    record = repository.get_ai_analysis(db, diagnostic_id)
    if load_valid_analysis(record) is None:
        raise AIAnalysisNotFoundError(f"Diagnostic {diagnostic_id} has no AI analysis")
    return record  # type: ignore[return-value]


class DiagnosticAnalysisService:
    """Runs the diagnostic agent at most once per diagnostic and persists its result."""

    def __init__(
        self,
        agent: DiagnosticAgent,
        provider: AIProvider,
        repository: DomainRepository | None = None,
    ) -> None:
        self.agent = agent
        self.provider = provider
        self.repository = repository or DomainRepository()

    def analyze(self, db: Session, diagnostic_id: int) -> PreliminaryDiagnosticAnalysis:
        """Return the persisted analysis when a valid one exists; otherwise generate, persist and
        return a new one. Provider or safety errors propagate and nothing is persisted."""
        if not self.repository.get_diagnostic(db, diagnostic_id):
            raise DiagnosticNotFoundError(f"Diagnostic {diagnostic_id} not found")
        cached = load_valid_analysis(self.repository.get_ai_analysis(db, diagnostic_id))
        if cached is not None:
            return cached

        analysis = self.agent.analyze(diagnostic_id)

        # The agent may close the shared request session, so everything is reloaded here.
        diagnostic = self.repository.get_diagnostic(db, diagnostic_id)
        if not diagnostic:
            raise DiagnosticNotFoundError(f"Diagnostic {diagnostic_id} not found")
        record = self.repository.get_ai_analysis(db, diagnostic_id)
        if record is None:
            # An existing but invalid record (outdated contract) is overwritten in place instead.
            record = DiagnosticAIAnalysis(diagnostic_id=diagnostic_id)
            db.add(record)
        record.provider = self.provider.name
        record.model = self.provider.model
        record.schema_version = ANALYSIS_SCHEMA_VERSION
        record.result = analysis.model_dump(mode="json")
        record.generated_at = datetime.now(UTC)
        if diagnostic.status == DiagnosticStatus.CREATED:
            diagnostic.status = DiagnosticStatus.REVIEW
        try:
            db.commit()
        except IntegrityError:
            # A concurrent request persisted this diagnostic's analysis first; keep that one.
            db.rollback()
            stored = load_valid_analysis(self.repository.get_ai_analysis(db, diagnostic_id))
            if stored is None:
                raise
            return stored
        return analysis
