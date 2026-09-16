from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class VehicleCreate(BaseModel):
    customer_id: int = Field(gt=0)
    plate: str = Field(min_length=3, max_length=15)
    vin: str | None = Field(default=None, min_length=17, max_length=17)
    brand: str = Field(min_length=1, max_length=80)
    model: str = Field(min_length=1, max_length=100)
    year: int = Field(ge=1886, le=2100)
    engine: str | None = Field(default=None, max_length=100)
    mileage: int = Field(ge=0)

    @field_validator("plate", "vin", mode="before")
    @classmethod
    def normalize_identifiers(cls, value: str | None) -> str | None:
        return value.strip().upper() if value else None


class VehicleRead(VehicleCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
