from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Customer, Diagnostic, DiagnosticFinding, DiagnosticMedia, Vehicle, WorkOrder
from app.repositories.domain import DomainRepository
from app.schemas.customer import CustomerCreate
from app.schemas.diagnostic import DiagnosticCreate, DiagnosticFindingCreate, DiagnosticMediaCreate
from app.schemas.vehicle import VehicleCreate
from app.schemas.work_order import WorkOrderCreate


class DomainService:
    def __init__(self, repository: DomainRepository | None = None) -> None:
        self.repository = repository or DomainRepository()

    @staticmethod
    def _not_found(resource: str, resource_id: int) -> HTTPException:
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"{resource} {resource_id} not found")

    @staticmethod
    def _save(db: Session, entity: object) -> object:
        try:
            db.add(entity)
            db.commit()
            db.refresh(entity)
            return entity
        except IntegrityError as exc:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="The resource conflicts with an existing record",
            ) from exc

    def create_customer(self, db: Session, data: CustomerCreate) -> Customer:
        return self._save(db, Customer(**data.model_dump()))  # type: ignore[return-value]

    def create_vehicle(self, db: Session, data: VehicleCreate) -> Vehicle:
        if not self.repository.get_customer(db, data.customer_id):
            raise self._not_found("Customer", data.customer_id)
        return self._save(db, Vehicle(**data.model_dump()))  # type: ignore[return-value]

    def create_diagnostic(self, db: Session, data: DiagnosticCreate) -> Diagnostic:
        if not self.repository.get_vehicle(db, data.vehicle_id):
            raise self._not_found("Vehicle", data.vehicle_id)
        return self._save(db, Diagnostic(**data.model_dump()))  # type: ignore[return-value]

    def create_media(self, db: Session, diagnostic_id: int, data: DiagnosticMediaCreate) -> DiagnosticMedia:
        if not self.repository.get_diagnostic(db, diagnostic_id):
            raise self._not_found("Diagnostic", diagnostic_id)
        return self._save(db, DiagnosticMedia(diagnostic_id=diagnostic_id, **data.model_dump()))  # type: ignore[return-value]

    def create_finding(
        self, db: Session, diagnostic_id: int, data: DiagnosticFindingCreate
    ) -> DiagnosticFinding:
        if not self.repository.get_diagnostic(db, diagnostic_id):
            raise self._not_found("Diagnostic", diagnostic_id)
        return self._save(db, DiagnosticFinding(diagnostic_id=diagnostic_id, **data.model_dump()))  # type: ignore[return-value]

    def create_work_order(self, db: Session, data: WorkOrderCreate) -> WorkOrder:
        if not self.repository.get_diagnostic(db, data.diagnostic_id):
            raise self._not_found("Diagnostic", data.diagnostic_id)
        return self._save(db, WorkOrder(**data.model_dump()))  # type: ignore[return-value]
