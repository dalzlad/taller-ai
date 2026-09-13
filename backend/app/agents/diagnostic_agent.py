from abc import ABC, abstractmethod
from collections.abc import Callable

from sqlalchemy.orm import Session, sessionmaker

from app.models import Diagnostic
from app.models.enums import DiagnosticEvidenceType, DiagnosticStatus, MediaType
from app.schemas.ai_analysis import PreliminaryDiagnosticAnalysis
from app.schemas.diagnostic_context import (
    DiagnosticContext,
    DiagnosticDetailsContext,
    DiagnosticEvidenceContext,
    DiagnosticVehicleContext,
)
from app.services.ai_provider import AIProvider
from app.services.ai_safety import AISafety
from app.services.vehicle_history_service import StubVehicleHistoryService, VehicleHistoryService


class DiagnosticNotFoundError(Exception):
    """Raised when the requested diagnostic does not exist."""


class DiagnosticAgent(ABC):
    @abstractmethod
    def analyze(self, diagnostic_id: int) -> PreliminaryDiagnosticAnalysis:
        """Produce and persist a preliminary, non-confirmatory assessment."""


class PreliminaryDiagnosticAgent(DiagnosticAgent):
    def __init__(
        self,
        session_factory: Callable[[], Session] | sessionmaker[Session],
        ai_provider: AIProvider,
        vehicle_history_service: VehicleHistoryService | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._ai_provider = ai_provider
        self._vehicle_history_service = vehicle_history_service or StubVehicleHistoryService()

    def analyze(self, diagnostic_id: int) -> PreliminaryDiagnosticAnalysis:
        with self._session_factory() as db:
            diagnostic = db.get(Diagnostic, diagnostic_id)
            if not diagnostic:
                raise DiagnosticNotFoundError(f"Diagnostic {diagnostic_id} not found")

            context = self._build_context(diagnostic)
            return AISafety.validate(self._ai_provider.analyze(context))

    def _build_context(self, diagnostic: Diagnostic) -> DiagnosticContext:
        vehicle = diagnostic.vehicle
        evidences = [
            DiagnosticEvidenceContext(
                evidence_type=evidence.evidence_type,
                file_name=evidence.file_name,
                mime_type=evidence.mime_type,
                file_reference=evidence.file_path,
                description=evidence.description,
            )
            for evidence in diagnostic.evidences
        ]
        # Legacy URL-based media remains readable while the new local evidence model is adopted.
        evidences.extend(
            DiagnosticEvidenceContext(
                evidence_type=DiagnosticEvidenceType.IMAGE if media.type == MediaType.PHOTO else DiagnosticEvidenceType(media.type.value),
                file_name=media.file_url.rsplit("/", 1)[-1],
                mime_type="application/octet-stream",
                file_reference=media.file_url,
                description=media.description,
            )
            for media in diagnostic.media
        )
        return DiagnosticContext(
            vehicle=DiagnosticVehicleContext(
                id=vehicle.id,
                brand=vehicle.brand,
                model=vehicle.model,
                year=vehicle.year,
                engine=vehicle.engine,
                mileage=vehicle.mileage,
                plate=vehicle.plate,
                vin=vehicle.vin,
            ),
            diagnostic=DiagnosticDetailsContext(
                id=diagnostic.id,
                reported_symptoms=diagnostic.reported_symptoms,
                mechanic_notes=diagnostic.mechanic_notes,
                status=diagnostic.status,
            ),
            history=self._vehicle_history_service.get_history(diagnostic.vehicle_id),
            evidences=evidences,
            technical_knowledge={"available": False, "items": []},
        )
