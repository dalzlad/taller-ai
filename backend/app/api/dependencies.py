from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.agents.diagnostic_agent import DiagnosticAgent, PreliminaryDiagnosticAgent
from app.core.config import settings
from app.db.session import get_db
from app.services.ai_provider_factory import AIProviderConfigurationError, AIProviderFactory


def get_diagnostic_agent(db: Session = Depends(get_db)) -> DiagnosticAgent:
    """Build an agent using the configured provider adapter."""
    try:
        provider = AIProviderFactory.create(settings.ai_provider)
    except AIProviderConfigurationError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    # Sharing the request session keeps the agent on the same database connection as the route.
    return PreliminaryDiagnosticAgent(session_factory=lambda: db, ai_provider=provider)
