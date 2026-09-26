import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.db.base import Base
from app.db.session import get_db
from app.main import app


@pytest.fixture(autouse=True)
def isolate_ai_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tests never use the AI provider or credentials from the local .env: every test starts
    on the offline stub, and tests that need another provider configure it explicitly."""
    monkeypatch.setattr(settings, "ai_provider", "stub")
    for name in ("gemini_api_key", "gemini_model", "openai_api_key", "openai_model"):
        monkeypatch.setattr(settings, name, None)


@pytest.fixture()
def client() -> TestClient:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)

    def override_get_db():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)
    engine.dispose()
