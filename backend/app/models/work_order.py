from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Numeric, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import WorkOrderStatus

if TYPE_CHECKING:
    from app.models.diagnostic import Diagnostic


class WorkOrder(Base):
    __tablename__ = "work_orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    diagnostic_id: Mapped[int] = mapped_column(ForeignKey("diagnostics.id", ondelete="RESTRICT"), index=True)
    status: Mapped[WorkOrderStatus] = mapped_column(
        Enum(WorkOrderStatus, name="work_order_status"), default=WorkOrderStatus.DRAFT, nullable=False
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    estimated_cost: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    final_cost: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    diagnostic: Mapped["Diagnostic"] = relationship(back_populates="work_orders")
