from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import DiagnosticStatus

if TYPE_CHECKING:
    from app.models.diagnostic_ai_analysis import DiagnosticAIAnalysis
    from app.models.diagnostic_evidence import DiagnosticEvidence
    from app.models.diagnostic_finding import DiagnosticFinding
    from app.models.diagnostic_media import DiagnosticMedia
    from app.models.vehicle import Vehicle
    from app.models.work_order import WorkOrder


class Diagnostic(Base):
    __tablename__ = "diagnostics"

    id: Mapped[int] = mapped_column(primary_key=True)
    vehicle_id: Mapped[int] = mapped_column(ForeignKey("vehicles.id", ondelete="CASCADE"), index=True)
    reported_symptoms: Mapped[str] = mapped_column(Text, nullable=False)
    mechanic_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_analysis: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[DiagnosticStatus] = mapped_column(
        Enum(DiagnosticStatus, name="diagnostic_status"), default=DiagnosticStatus.CREATED, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    vehicle: Mapped["Vehicle"] = relationship(back_populates="diagnostics")
    media: Mapped[list["DiagnosticMedia"]] = relationship(
        back_populates="diagnostic", cascade="all, delete-orphan"
    )
    evidences: Mapped[list["DiagnosticEvidence"]] = relationship(
        back_populates="diagnostic", cascade="all, delete-orphan"
    )
    findings: Mapped[list["DiagnosticFinding"]] = relationship(
        back_populates="diagnostic", cascade="all, delete-orphan"
    )
    work_orders: Mapped[list["WorkOrder"]] = relationship(back_populates="diagnostic")
    analysis: Mapped["DiagnosticAIAnalysis | None"] = relationship(
        back_populates="diagnostic", uselist=False, cascade="all, delete-orphan"
    )
