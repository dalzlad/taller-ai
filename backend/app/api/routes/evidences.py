from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Diagnostic
from app.repositories.diagnostic_evidence import DiagnosticEvidenceRepository
from app.schemas.diagnostic_evidence import DiagnosticEvidenceRead
from app.services.diagnostic_evidence import DiagnosticEvidenceService

diagnostic_router = APIRouter(prefix="/diagnostics", tags=["diagnostic evidences"])
router = APIRouter(prefix="/evidences", tags=["diagnostic evidences"])
repository = DiagnosticEvidenceRepository()
evidence_service = DiagnosticEvidenceService(repository)


def _require_evidence(db: Session, evidence_id: int):
    evidence = repository.get(db, evidence_id)
    if not evidence:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evidence not found")
    return evidence


@diagnostic_router.post(
    "/{diagnostic_id}/evidences", response_model=DiagnosticEvidenceRead, status_code=status.HTTP_201_CREATED
)
def upload_evidence(
    diagnostic_id: int,
    file: Annotated[UploadFile, File(...)],
    description: Annotated[str | None, Form(max_length=10_000)] = None,
    db: Session = Depends(get_db),
) -> DiagnosticEvidenceRead:
    return evidence_service.create(db, diagnostic_id, file, description)


@diagnostic_router.get("/{diagnostic_id}/evidences", response_model=list[DiagnosticEvidenceRead])
def list_evidences(diagnostic_id: int, db: Session = Depends(get_db)) -> list[DiagnosticEvidenceRead]:
    if not db.get(Diagnostic, diagnostic_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Diagnostic not found")
    return repository.list_for_diagnostic(db, diagnostic_id)


@router.get("/{evidence_id}", response_model=DiagnosticEvidenceRead)
def get_evidence(evidence_id: int, db: Session = Depends(get_db)) -> DiagnosticEvidenceRead:
    return _require_evidence(db, evidence_id)


@router.get("/{evidence_id}/file")
def download_evidence(evidence_id: int, db: Session = Depends(get_db)) -> FileResponse:
    evidence = _require_evidence(db, evidence_id)
    file_path = evidence_service.storage.get_file(evidence.file_path)
    if not file_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evidence file not found")
    return FileResponse(file_path, media_type=evidence.mime_type, filename=evidence.file_name)


@router.delete("/{evidence_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_evidence(evidence_id: int, db: Session = Depends(get_db)) -> None:
    evidence_service.delete(db, _require_evidence(db, evidence_id))
