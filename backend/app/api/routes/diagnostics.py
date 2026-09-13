from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.api.dependencies import get_diagnostic_agent
from app.agents.diagnostic_agent import DiagnosticAgent, DiagnosticNotFoundError
from app.services.ai_safety import UnsafeAIResultError
from app.services.providers.gemini_ai_provider import (
    GeminiProviderConfigurationError,
    GeminiProviderResponseError,
)
from app.services.providers.openai_ai_provider import OpenAIProviderNotEnabledError
from app.repositories.domain import DomainRepository
from app.schemas.diagnostic import (
    DiagnosticCreate,
    DiagnosticFindingCreate,
    DiagnosticFindingRead,
    DiagnosticMediaCreate,
    DiagnosticMediaRead,
    DiagnosticRead,
)
from app.schemas.ai_analysis import PreliminaryDiagnosticAnalysis
from app.services.domain import DomainService

router = APIRouter(prefix="/diagnostics", tags=["diagnostics"])
repository = DomainRepository()
service = DomainService(repository)


def _require_diagnostic(db: Session, diagnostic_id: int):
    diagnostic = repository.get_diagnostic(db, diagnostic_id)
    if not diagnostic:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Diagnostic not found")
    return diagnostic


@router.post("", response_model=DiagnosticRead, status_code=status.HTTP_201_CREATED)
def create_diagnostic(payload: DiagnosticCreate, db: Session = Depends(get_db)) -> DiagnosticRead:
    return service.create_diagnostic(db, payload)


@router.get("", response_model=list[DiagnosticRead])
def list_diagnostics(db: Session = Depends(get_db)) -> list[DiagnosticRead]:
    return repository.list_diagnostics(db)


@router.post("/{diagnostic_id}/analyze", response_model=PreliminaryDiagnosticAnalysis)
def analyze_diagnostic(
    diagnostic_id: int, agent: DiagnosticAgent = Depends(get_diagnostic_agent)
) -> PreliminaryDiagnosticAnalysis:
    """Request a preliminary assessment; no AI result is treated as a confirmed fault."""
    try:
        return agent.analyze(diagnostic_id)
    except DiagnosticNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Diagnostic not found") from exc
    except UnsafeAIResultError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except OpenAIProviderNotEnabledError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except GeminiProviderConfigurationError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except GeminiProviderResponseError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc


@router.get("/{diagnostic_id}", response_model=DiagnosticRead)
def get_diagnostic(diagnostic_id: int, db: Session = Depends(get_db)) -> DiagnosticRead:
    return _require_diagnostic(db, diagnostic_id)


@router.post("/{diagnostic_id}/media", response_model=DiagnosticMediaRead, status_code=status.HTTP_201_CREATED)
def create_media(
    diagnostic_id: int, payload: DiagnosticMediaCreate, db: Session = Depends(get_db)
) -> DiagnosticMediaRead:
    return service.create_media(db, diagnostic_id, payload)


@router.get("/{diagnostic_id}/media", response_model=list[DiagnosticMediaRead])
def list_media(diagnostic_id: int, db: Session = Depends(get_db)) -> list[DiagnosticMediaRead]:
    _require_diagnostic(db, diagnostic_id)
    return repository.list_media(db, diagnostic_id)


@router.post(
    "/{diagnostic_id}/findings", response_model=DiagnosticFindingRead, status_code=status.HTTP_201_CREATED
)
def create_finding(
    diagnostic_id: int, payload: DiagnosticFindingCreate, db: Session = Depends(get_db)
) -> DiagnosticFindingRead:
    return service.create_finding(db, diagnostic_id, payload)


@router.get("/{diagnostic_id}/findings", response_model=list[DiagnosticFindingRead])
def list_findings(diagnostic_id: int, db: Session = Depends(get_db)) -> list[DiagnosticFindingRead]:
    _require_diagnostic(db, diagnostic_id)
    return repository.list_findings(db, diagnostic_id)
