from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.repositories.domain import DomainRepository
from app.schemas.vehicle import VehicleCreate, VehicleRead
from app.services.domain import DomainService

router = APIRouter(prefix="/vehicles", tags=["vehicles"])
repository = DomainRepository()
service = DomainService(repository)


@router.post("", response_model=VehicleRead, status_code=status.HTTP_201_CREATED)
def create_vehicle(payload: VehicleCreate, db: Session = Depends(get_db)) -> VehicleRead:
    return service.create_vehicle(db, payload)


@router.get("", response_model=list[VehicleRead])
def list_vehicles(db: Session = Depends(get_db)) -> list[VehicleRead]:
    return repository.list_vehicles(db)


@router.get("/{vehicle_id}", response_model=VehicleRead)
def get_vehicle(vehicle_id: int, db: Session = Depends(get_db)) -> VehicleRead:
    vehicle = repository.get_vehicle(db, vehicle_id)
    if not vehicle:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vehicle not found")
    return vehicle
