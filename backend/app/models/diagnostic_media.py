from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import MediaType


class DiagnosticMedia(Base):
    __tablename__ = "diagnostic_media"

    id: Mapped[int] = mapped_column(primary_key=True)
    diagnostic_id: Mapped[int] = mapped_column(ForeignKey("diagnostics.id", ondelete="CASCADE"), index=True)
    type: Mapped[MediaType] = mapped_column(Enum(MediaType, name="media_type"), nullable=False)
    file_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    diagnostic: Mapped["Diagnostic"] = relationship(back_populates="media")
