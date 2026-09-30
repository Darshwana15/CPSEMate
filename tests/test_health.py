"""
P0 foundation tests.

Tests:
1. FastAPI application imports successfully.
2. GET /api/v1/health works.
3. Health response has the expected structure.
4. Configuration loads safely.
5. Database configuration initializes without exposing secrets.
"""

from fastapi.testclient import TestClient


# ── 1. Application import ───────────────────────────────────────────

def test_app_imports():
    """The FastAPI application object can be imported."""
    from app.main import app  # noqa: F401

    assert app is not None


# ── 2 & 3. Health endpoint ──────────────────────────────────────────

def test_health_returns_200(client: TestClient):
    """GET /api/v1/health returns 200 OK."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200


def test_health_response_structure(client: TestClient):
    """Health response contains {"status": "ok"}."""
    response = client.get("/api/v1/health")
    data = response.json()
    assert data == {"status": "ok"}


# ── 4. Configuration ───────────────────────────────────────────────

def test_settings_load():
    """Settings object loads without error."""
    from app.core.config import settings

    assert settings is not None
    assert settings.api_v1_prefix == "/api/v1"


def test_settings_has_database_url():
    """Settings object contains a database_url attribute."""
    from app.core.config import settings

    assert hasattr(settings, "database_url")
    assert isinstance(settings.database_url, str)
    assert len(settings.database_url) > 0


# ── 5. Database configuration ──────────────────────────────────────

def test_sqlalchemy_base_exists():
    """SQLAlchemy declarative Base is importable and has metadata."""
    from app.db.base import Base

    assert Base is not None
    assert hasattr(Base, "metadata")


def test_session_factory_exists():
    """Session factory and get_db dependency are importable."""
    from app.db.session import SessionLocal, get_db

    assert SessionLocal is not None
    assert callable(get_db)


def test_database_connectivity():
    """SQLAlchemy can connect to the configured PostgreSQL database."""
    from sqlalchemy import text

    from app.db.session import engine

    with engine.connect() as conn:
        result = conn.execute(text("SELECT 1 AS connected"))
        row = result.fetchone()
        assert row is not None
        assert row[0] == 1
