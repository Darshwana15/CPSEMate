"""
Shared pytest fixtures.

Tests run against the isolated sih_test database (never sih_dev).
DATABASE_URL is overridden here before the app is imported so that
SessionLocal always connects to sih_test during the test run.
"""

import os

# Force tests to use sih_test so sih_dev data is never mutated by tests.
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql://sih_user:changeme@localhost:5433/sih_test"
)

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture()
def client() -> TestClient:
    """FastAPI TestClient for integration tests."""
    return TestClient(app)

from app.db.session import SessionLocal

@pytest.fixture(scope="function")
def db():
    """Provides a database session against the isolated sih_test database."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
