from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import DiagnosticEvidence


class DiagnosticEvidenceRepository:
    def get(self, db: Session, evidence_id: int) -> DiagnosticEvidence | None:
        return db.get(DiagnosticEvidence, evidence_id)

    def list_for_diagnostic(self, db: Session, diagnostic_id: int) -> list[DiagnosticEvidence]:
        statement = select(DiagnosticEvidence).where(DiagnosticEvidence.diagnostic_id == diagnostic_id)
        return list(db.scalars(statement.order_by(DiagnosticEvidence.id)))
