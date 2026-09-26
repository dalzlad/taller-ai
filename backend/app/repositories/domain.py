from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models import (
    Customer,
    Diagnostic,
    DiagnosticAIAnalysis,
    DiagnosticFinding,
    DiagnosticMedia,
    Vehicle,
    WorkOrder,
)

LIKE_ESCAPE = "\\"
DEFAULT_SEARCH_LIMIT = 20
MAX_SEARCH_LIMIT = 50


def _contains_pattern(text: str) -> str:
    """LIKE pattern for a literal substring: user-typed % and _ are not wildcards."""
    escaped = (
        text.replace(LIKE_ESCAPE, LIKE_ESCAPE * 2)
        .replace("%", f"{LIKE_ESCAPE}%")
        .replace("_", f"{LIKE_ESCAPE}_")
    )
    return f"%{escaped}%"


class DomainRepository:
    """Query methods kept separate from HTTP and business validation concerns."""

    def get_customer(self, db: Session, customer_id: int) -> Customer | None:
        return db.get(Customer, customer_id)

    def list_customers(self, db: Session, *, limit: int | None = None) -> list[Customer]:
        statement = select(Customer).order_by(Customer.id)
        if limit is not None:
            statement = statement.limit(limit)
        return list(db.scalars(statement))

    def search_customers(self, db: Session, query: str, limit: int) -> list[Customer]:
        """Case-insensitive partial match on name, phone or email."""
        pattern = _contains_pattern(query)
        statement = (
            select(Customer)
            .where(
                or_(
                    Customer.name.ilike(pattern, escape=LIKE_ESCAPE),
                    Customer.phone.ilike(pattern, escape=LIKE_ESCAPE),
                    Customer.email.ilike(pattern, escape=LIKE_ESCAPE),
                )
            )
            .order_by(Customer.name, Customer.id)
            .limit(limit)
        )
        return list(db.scalars(statement))

    def get_vehicle(self, db: Session, vehicle_id: int) -> Vehicle | None:
        return db.get(Vehicle, vehicle_id)

    def list_vehicles(
        self,
        db: Session,
        *,
        customer_id: int | None = None,
        plate: str | None = None,
        limit: int | None = None,
    ) -> list[Vehicle]:
        """All vehicles by default; filters combine and `plate` is a partial, case-insensitive match."""
        statement = select(Vehicle).order_by(Vehicle.id)
        if customer_id is not None:
            statement = statement.where(Vehicle.customer_id == customer_id)
        if plate is not None:
            statement = statement.where(Vehicle.plate.ilike(_contains_pattern(plate), escape=LIKE_ESCAPE))
        if limit is not None:
            statement = statement.limit(limit)
        return list(db.scalars(statement))

    def get_diagnostic(self, db: Session, diagnostic_id: int) -> Diagnostic | None:
        return db.get(Diagnostic, diagnostic_id)

    def list_diagnostics(self, db: Session) -> list[Diagnostic]:
        return list(db.scalars(select(Diagnostic).order_by(Diagnostic.id.desc())))

    def get_ai_analysis(self, db: Session, diagnostic_id: int) -> DiagnosticAIAnalysis | None:
        statement = select(DiagnosticAIAnalysis).where(DiagnosticAIAnalysis.diagnostic_id == diagnostic_id)
        return db.scalars(statement).one_or_none()

    def list_media(self, db: Session, diagnostic_id: int) -> list[DiagnosticMedia]:
        statement = select(DiagnosticMedia).where(DiagnosticMedia.diagnostic_id == diagnostic_id)
        return list(db.scalars(statement.order_by(DiagnosticMedia.id)))

    def list_findings(self, db: Session, diagnostic_id: int) -> list[DiagnosticFinding]:
        statement = select(DiagnosticFinding).where(DiagnosticFinding.diagnostic_id == diagnostic_id)
        return list(db.scalars(statement.order_by(DiagnosticFinding.id)))

    def list_work_orders(self, db: Session) -> list[WorkOrder]:
        return list(db.scalars(select(WorkOrder).order_by(WorkOrder.id.desc())))
