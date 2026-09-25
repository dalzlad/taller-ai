from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.repositories.domain import DEFAULT_SEARCH_LIMIT, MAX_SEARCH_LIMIT, DomainRepository
from app.schemas.vehicle import VehicleCreate, VehicleRead
from app.services.domain import DomainService

router = APIRouter(prefix="/vehicles", tags=["vehicles"])
repository = DomainRepository()
service = DomainService(repository)


@router.post("", response_model=VehicleRead, status_code=status.HTTP_201_CREATED)
def create_vehicle(payload: VehicleCreate, db: Session = Depends(get_db)) -> VehicleRead:
    return service.create_vehicle(db, payload)


@router.get("", response_model=list[VehicleRead])
def list_vehicles(
    customer_id: Annotated[int | None, Query(gt=0, description="Only this customer's vehicles")] = None,
    plate: Annotated[
        str | None,
        Query(min_length=1, max_length=15, description="Partial, case-insensitive plate match"),
    ] = None,
    limit: Annotated[
        int | None,
        Query(ge=1, le=MAX_SEARCH_LIMIT, description=f"Defaults to {DEFAULT_SEARCH_LIMIT} when filtering"),
    ] = None,
    db: Session = Depends(get_db),
) -> list[VehicleRead]:
    """Without filters every vehicle is returned, as before filtering existed."""
    plate_query = plate.strip().upper() if plate is not None else None
    if plate_query == "":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Plate search cannot be blank"
        )
    filtering = customer_id is not None or plate_query is not None
    return repository.list_vehicles(
        db,
        customer_id=customer_id,
        plate=plate_query,
        limit=limit or (DEFAULT_SEARCH_LIMIT if filtering else None),
    )


@router.get("/{vehicle_id}", response_model=VehicleRead)
def get_vehicle(vehicle_id: int, db: Session = Depends(get_db)) -> VehicleRead:
    vehicle = repository.get_vehicle(db, vehicle_id)
    if not vehicle:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vehicle not found")
    return vehicle
