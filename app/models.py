import uuid
from datetime import datetime, timezone

import uuid

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    TypeDecorator,
    UniqueConstraint,
    event,
    select,
    text,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import relationship

_SQLITE = "sqlite" in str(__import__("app.core.config", fromlist=["settings"]).settings.database_url)

from app.db.base import Base

JSONB = JSON


class GUID(TypeDecorator):
    """Cross-database UUID type compatible with SQLite and PostgreSQL."""

    impl = String(36)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, uuid.UUID):
            return str(value)
        return str(uuid.UUID(str(value)))

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return uuid.UUID(str(value))


def utc_now() -> datetime:
    """Returns current timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


class CPSE(Base):
    __tablename__ = "cpse"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    code = Column(String(50), unique=True, nullable=False)
    name = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    materials = relationship("Material", back_populates="cpse")


class Material(Base):
    __tablename__ = "material"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    cpse_id = Column(GUID(), ForeignKey("cpse.id", ondelete="RESTRICT"), nullable=False)

    source_material_code = Column(String(100), nullable=False)
    source_description = Column(Text, nullable=False)
    source_uom = Column(String(50), nullable=False)
    source_specifications = Column(Text, nullable=True)
    raw_source_data = Column(JSONB, nullable=True)

    category = Column(String(50), nullable=True)

    valve_type = Column(String(100), nullable=True)
    size = Column(String(100), nullable=True)
    body_material = Column(String(100), nullable=True)
    pressure_class = Column(String(100), nullable=True)
    connection_type = Column(String(100), nullable=True)
    trim = Column(String(100), nullable=True)

    normalized_uom = Column(String(50), nullable=True)
    normalized_description = Column(Text, nullable=True)
    normalized_attributes = Column(JSONB, nullable=True)

    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    cpse = relationship("CPSE", back_populates="materials")
    mappings = relationship("MaterialNationalMapping", back_populates="material")

    __table_args__ = (
        UniqueConstraint("cpse_id", "source_material_code", name="uq_material_cpse_source_code"),
        Index("ix_material_cpse_id", "cpse_id"),
        Index("ix_material_category", "category"),
    )


class NationalMaterial(Base):
    __tablename__ = "national_material"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    national_code = Column(String(100), unique=True, nullable=False)
    category = Column(String(50), nullable=False)
    canonical_description = Column(Text, nullable=False)

    normalized_attributes = Column(JSONB, nullable=True)

    valve_type = Column(String(100), nullable=True)
    size = Column(String(100), nullable=True)
    body_material = Column(String(100), nullable=True)
    pressure_class = Column(String(100), nullable=True)
    connection_type = Column(String(100), nullable=True)
    trim = Column(String(100), nullable=True)
    normalized_uom = Column(String(50), nullable=True)

    identity_key = Column(String(500), unique=True, nullable=False)
    status = Column(String(50), nullable=True)

    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    mappings = relationship("MaterialNationalMapping", back_populates="national_material")



class MatchRecommendation(Base):
    __tablename__ = "match_recommendation"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    source_material_id = Column(GUID(), ForeignKey("material.id", ondelete="RESTRICT"), nullable=False)
    candidate_material_id = Column(GUID(), ForeignKey("material.id", ondelete="RESTRICT"), nullable=False)
    classification = Column(String(50), nullable=False)
    confidence = Column(Numeric, nullable=True)
    evidence = Column(JSONB, nullable=True)
    explanation = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    __table_args__ = (
        CheckConstraint("source_material_id != candidate_material_id", name="chk_recommendation_not_self"),
        CheckConstraint("classification IN ('SAME', 'POTENTIALLY_EQUIVALENT', 'DIFFERENT')", name="chk_recommendation_classification"),
        Index("ix_match_rec_source_candidate", "source_material_id", "candidate_material_id"),
        Index("ix_match_rec_source", "source_material_id"),
        Index("ix_match_rec_candidate", "candidate_material_id"),
        Index("ix_match_rec_classification", "classification"),
    )


class MaterialNationalMapping(Base):
    __tablename__ = "material_national_mapping"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    material_id = Column(GUID(), ForeignKey("material.id", ondelete="RESTRICT"), nullable=False)
    national_material_id = Column(GUID(), ForeignKey("national_material.id", ondelete="RESTRICT"), nullable=False)
    basis = Column(String(50), nullable=False)
    status = Column(String(50), nullable=False)
    recommendation_id = Column(GUID(), ForeignKey("match_recommendation.id", ondelete="RESTRICT"), nullable=True)

    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    material = relationship("Material", back_populates="mappings")
    national_material = relationship("NationalMaterial", back_populates="mappings")

    __table_args__ = (
        CheckConstraint("basis IN ('AUTO_SAME', 'HUMAN_CONFIRMED_SAME', 'HUMAN_OVERRIDE')", name="chk_mapping_basis"),
        CheckConstraint("status IN ('ACTIVE', 'SUPERSEDED', 'INACTIVE')", name="chk_mapping_status"),
        Index("ix_mapping_material_id", "material_id"),
        Index("ix_mapping_national_material_id", "national_material_id"),
    )


def _enforce_single_active_mapping(connection, target):
    if target.status != "ACTIVE":
        return
    if not _SQLITE:
        return
    existing = connection.execute(
        select(MaterialNationalMapping.id).where(
            MaterialNationalMapping.material_id == target.material_id,
            MaterialNationalMapping.status == "ACTIVE",
        )
    ).scalar()
    if existing is not None and str(existing) != str(target.id):
        raise IntegrityError(
            statement=None,
            params=None,
            orig=Exception("Material already has an ACTIVE mapping. Unmap or explicitly remap first."),
            code="SQLITE_CONSTRAINT",
        )


@event.listens_for(MaterialNationalMapping, "before_insert")
def _material_national_mapping_before_insert(mapper, connection, target):
    _enforce_single_active_mapping(connection, target)


@event.listens_for(MaterialNationalMapping, "before_update")
def _material_national_mapping_before_update(mapper, connection, target):
    if getattr(target, "status", None) is not None:
        _enforce_single_active_mapping(connection, target)


class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    actor = Column(String(100), nullable=False)
    action = Column(String(100), nullable=False)
    entity_type = Column(String(100), nullable=False)
    entity_id = Column(String(100), nullable=False)
    before_state = Column(JSONB, nullable=True)
    after_state = Column(JSONB, nullable=True)
    reason = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    __table_args__ = (
        Index("ix_audit_entity", "entity_type", "entity_id"),
        Index("ix_audit_created_at", "created_at"),
    )
