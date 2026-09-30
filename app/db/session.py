"""
SQLAlchemy engine and session management.

Provides:
- engine:          the SQLAlchemy Engine bound to the configured DATABASE_URL
- SessionLocal:    a session factory for request-scoped database sessions
- get_db():        FastAPI dependency that yields a session per request
"""

from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.db.base import Base

# Import model modules so SQLite fallback can create the full schema with the registered
# ORM metadata. This is needed even when the app is running in local demo mode.
import app.models  # noqa: F401

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
)

# The project targets PostgreSQL in production but also runs local demo/test passes on SQLite.
# Earlier SQLite runs may have persisted a stale unique index created from the PostgreSQL-only
# partial index definition, which breaks the one-active-mapping invariant. Remove it before schema
# creation so the database matches the portable runtime behavior.
if settings.database_url.startswith("sqlite"):
    with engine.begin() as conn:
        for name in [
            "idx_unique_active_mapping",
            "idx_unique_active_mapping_sqlite",
        ]:
            try:
                conn.execute(text(f"DROP INDEX IF EXISTS {name}"))
            except Exception:
                pass

# Create tables automatically for local prototype and demo runs when the schema is not
# managed by an external migration layer.
Base.metadata.create_all(bind=engine)

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency — yields a database session, closes after use."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
