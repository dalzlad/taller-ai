from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import WorkOrderStatus


class WorkOrderCreate(BaseModel):
    diagnostic_id: int = Field(gt=0)
    description: str = Field(min_length=1, max_length=10_000)
    estimated_cost: Optional[Decimal] = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    final_cost: Optional[Decimal] = Field(default=None, ge=0, max_digits=12, decimal_places=2)

    @model_validator(mode="after")
    def final_cost_requires_estimate(self) -> "WorkOrderCreate":
        if self.final_cost is not None and self.estimated_cost is None:
            raise ValueError("estimated_cost is required when final_cost is provided")
        return self


class WorkOrderRead(WorkOrderCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: WorkOrderStatus
    created_at: datetime
