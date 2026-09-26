from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.diagnostic import Diagnostic


class DiagnosticAIAnalysis(Base):
    """Persisted preliminary AI analysis; at most one per diagnostic."""

    __tablename__ = "diagnostic_ai_analyses"

    id: Mapped[int] = mapped_column(primary_key=True)
    diagnostic_id: Mapped[int] = mapped_column(
        ForeignKey("diagnostics.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    provider: Mapped[str] = mapped_column(String(30), nullable=False)
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False)
    result: Mapped[dict] = mapped_column(JSON, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    diagnostic: Mapped["Diagnostic"] = relationship(back_populates="analysis")
