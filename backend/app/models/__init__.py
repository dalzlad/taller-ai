"""SQLAlchemy ORM models registered for migrations."""

from app.models.customer import Customer
from app.models.diagnostic import Diagnostic
from app.models.diagnostic_evidence import DiagnosticEvidence
from app.models.diagnostic_finding import DiagnosticFinding
from app.models.diagnostic_media import DiagnosticMedia
from app.models.vehicle import Vehicle
from app.models.work_order import WorkOrder

__all__ = ["Customer", "Diagnostic", "DiagnosticEvidence", "DiagnosticFinding", "DiagnosticMedia", "Vehicle", "WorkOrder"]
