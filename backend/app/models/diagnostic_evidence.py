from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import DiagnosticEvidenceType

if TYPE_CHECKING:
    from app.models.diagnostic import Diagnostic


class DiagnosticEvidence(Base):
    __tablename__ = "diagnostic_evidences"

    id: Mapped[int] = mapped_column(primary_key=True)
    diagnostic_id: Mapped[int] = mapped_column(ForeignKey("diagnostics.id", ondelete="CASCADE"), index=True)
    evidence_type: Mapped[DiagnosticEvidenceType] = mapped_column(
        Enum(DiagnosticEvidenceType, name="diagnostic_evidence_type"), nullable=False
    )
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    diagnostic: Mapped["Diagnostic"] = relationship(back_populates="evidences")
