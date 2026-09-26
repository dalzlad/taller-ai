from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.agents.diagnostic_agent import DiagnosticAgent, PreliminaryDiagnosticAgent
from app.core.config import settings
from app.db.session import get_db
from app.services.ai_provider import AIProvider
from app.services.ai_provider_factory import AIProviderConfigurationError, AIProviderFactory
from app.services.diagnostic_analysis import DiagnosticAnalysisService


def get_ai_provider() -> AIProvider:
    """Build the provider adapter selected by AI_PROVIDER."""
    try:
        return AIProviderFactory.create(settings.ai_provider)
    except AIProviderConfigurationError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc


def get_diagnostic_agent(
    db: Session = Depends(get_db), provider: AIProvider = Depends(get_ai_provider)
) -> DiagnosticAgent:
    """Build an agent using the configured provider adapter."""
    # Sharing the request session keeps the agent on the same database connection as the route.
    return PreliminaryDiagnosticAgent(session_factory=lambda: db, ai_provider=provider)


def get_diagnostic_analysis_service(
    agent: DiagnosticAgent = Depends(get_diagnostic_agent),
    provider: AIProvider = Depends(get_ai_provider),
) -> DiagnosticAnalysisService:
    """FastAPI resolves get_ai_provider once per request, so the agent and the persisted
    metadata always refer to the same provider instance."""
    return DiagnosticAnalysisService(agent=agent, provider=provider)
