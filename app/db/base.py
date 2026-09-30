"""
SQLAlchemy declarative Base.

All domain models will inherit from this Base.
Domain models are NOT defined yet — they belong to the next phase.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Declarative base class for all SQLAlchemy models."""

    pass
