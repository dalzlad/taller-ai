from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Customer, Diagnostic, DiagnosticFinding, DiagnosticMedia, Vehicle, WorkOrder


class DomainRepository:
    """Query methods kept separate from HTTP and business validation concerns."""

    def get_customer(self, db: Session, customer_id: int) -> Customer | None:
        return db.get(Customer, customer_id)

    def list_customers(self, db: Session) -> list[Customer]:
        return list(db.scalars(select(Customer).order_by(Customer.id)))

    def get_vehicle(self, db: Session, vehicle_id: int) -> Vehicle | None:
        return db.get(Vehicle, vehicle_id)

    def list_vehicles(self, db: Session) -> list[Vehicle]:
        return list(db.scalars(select(Vehicle).order_by(Vehicle.id)))

    def get_diagnostic(self, db: Session, diagnostic_id: int) -> Diagnostic | None:
        return db.get(Diagnostic, diagnostic_id)

    def list_diagnostics(self, db: Session) -> list[Diagnostic]:
        return list(db.scalars(select(Diagnostic).order_by(Diagnostic.id.desc())))

    def list_media(self, db: Session, diagnostic_id: int) -> list[DiagnosticMedia]:
        statement = select(DiagnosticMedia).where(DiagnosticMedia.diagnostic_id == diagnostic_id)
        return list(db.scalars(statement.order_by(DiagnosticMedia.id)))

    def list_findings(self, db: Session, diagnostic_id: int) -> list[DiagnosticFinding]:
        statement = select(DiagnosticFinding).where(DiagnosticFinding.diagnostic_id == diagnostic_id)
        return list(db.scalars(statement.order_by(DiagnosticFinding.id)))

    def list_work_orders(self, db: Session) -> list[WorkOrder]:
        return list(db.scalars(select(WorkOrder).order_by(WorkOrder.id.desc())))
