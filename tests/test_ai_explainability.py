"""
Unit and integration tests for AI Explainability & Reviewer Intelligence (Phase 4).
"""

import uuid
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models import CPSE, Material, MatchRecommendation, MaterialNationalMapping, AuditLog
from app.services.ai.explainability import (
    AttributeComparisonItem,
    EngineeringConflictItem,
    MaterialExplanationService,
    RecommendationExplanation,
    SemanticEvidence,
)
from app.services.review import process_review_action


@pytest.fixture
def explanation_service():
    return MaterialExplanationService()


@pytest.fixture
def cpse_source(db):
    code = f"CPSE-EXP-SRC-{uuid.uuid4().hex[:6]}"
    c = CPSE(code=code, name=code)
    db.add(c)
    db.commit()
    db.refresh(c)
    yield c
    try:
        mat_ids = [m.id for m in db.query(Material).filter(Material.cpse_id == c.id).all()]
        if mat_ids:
            db.query(MatchRecommendation).filter(MatchRecommendation.source_material_id.in_(mat_ids)).delete(synchronize_session=False)
            db.query(MatchRecommendation).filter(MatchRecommendation.candidate_material_id.in_(mat_ids)).delete(synchronize_session=False)
            db.query(Material).filter(Material.id.in_(mat_ids)).delete(synchronize_session=False)
        db.delete(c)
        db.commit()
    except Exception:
        db.rollback()


@pytest.fixture
def cpse_target(db):
    code = f"CPSE-EXP-TGT-{uuid.uuid4().hex[:6]}"
    c = CPSE(code=code, name=code)
    db.add(c)
    db.commit()
    db.refresh(c)
    yield c
    try:
        mat_ids = [m.id for m in db.query(Material).filter(Material.cpse_id == c.id).all()]
        if mat_ids:
            db.query(MatchRecommendation).filter(MatchRecommendation.source_material_id.in_(mat_ids)).delete(synchronize_session=False)
            db.query(MatchRecommendation).filter(MatchRecommendation.candidate_material_id.in_(mat_ids)).delete(synchronize_session=False)
            db.query(Material).filter(Material.id.in_(mat_ids)).delete(synchronize_session=False)
        db.delete(c)
        db.commit()
    except Exception:
        db.rollback()


def create_material(db, cpse, desc: str, **kwargs) -> Material:
    mat = Material(
        id=uuid.uuid4(),
        cpse_id=cpse.id,
        source_material_code=f"MAT-EXP-{uuid.uuid4().hex[:6]}",
        source_description=desc,
        source_uom="EA",
        category=kwargs.get("category", "VALVE"),
        normalized_description=desc,
        normalized_uom="EA",
        valve_type=kwargs.get("valve_type"),
        size=kwargs.get("size"),
        body_material=kwargs.get("body_material"),
        pressure_class=kwargs.get("pressure_class"),
        connection_type=kwargs.get("connection_type"),
        trim=kwargs.get("trim"),
    )
    db.add(mat)
    db.commit()
    db.refresh(mat)
    return mat


def test_exact_equivalent_explanation(explanation_service):
    src = Material(
        id=uuid.uuid4(),
        source_material_code="SRC-EXACT",
        source_description="BALL VALVE DN50 CS CLASS150 RF SS304 TRIM",
        category="VALVE",
        valve_type="BALL", size="DN50", body_material="CARBON_STEEL",
        pressure_class="CLASS150", connection_type="RF", trim="SS304",
    )
    cand = Material(
        id=uuid.uuid4(),
        source_material_code="CAND-EXACT",
        source_description="BALL VALVE 2 IN CS 150# RF SS304 TRIM",
        category="VALVE",
        valve_type="BALL", size="DN50", body_material="CARBON_STEEL",
        pressure_class="CLASS150", connection_type="RF", trim="SS304",
    )

    exp = explanation_service.generate_explanation(src, cand)

    assert exp.classification == "SAME"
    assert exp.confidence >= 0.90
    assert exp.recommended_action == "AUTO_SAFE"
    assert len(exp.engineering_conflicts) == 0
    assert len(exp.conflicting_attributes) == 0
    assert "size" in exp.matching_attributes
    assert "valve_type" in exp.matching_attributes
    assert "pressure_class" in exp.matching_attributes
    assert exp.semantic_evidence.semantic_similarity_score > 0.85
    assert "SAFE" in exp.safety_assessment


def test_attribute_level_comparisons(explanation_service):
    src = Material(
        id=uuid.uuid4(),
        source_material_code="SRC-ATTRS",
        source_description="GATE VALVE DN50 CS CLASS150 RF SS316 TRIM",
        category="VALVE",
        valve_type="GATE", size="DN50", body_material="CARBON_STEEL",
        pressure_class="CLASS150", connection_type="RF", trim="SS316",
    )
    cand = Material(
        id=uuid.uuid4(),
        source_material_code="CAND-ATTRS",
        source_description="GATE VALVE DN50 CS CLASS150 RF SS316 TRIM",
        category="VALVE",
        valve_type="GATE", size="DN50", body_material="CARBON_STEEL",
        pressure_class="CLASS150", connection_type="RF", trim="SS316",
    )

    exp = explanation_service.generate_explanation(src, cand)
    attr_map = {a.attribute: a for a in exp.attribute_comparisons}

    assert "size" in attr_map
    assert attr_map["size"].status == "MATCH"
    assert "pressure_class" in attr_map
    assert attr_map["pressure_class"].status == "MATCH"
    assert "body_material" in attr_map
    assert attr_map["body_material"].status == "MATCH"


@pytest.mark.parametrize("source_attrs,cand_attrs,expected_conflict_keyword", [
    # 1. Metallurgy conflict: SS316 vs CARBON_STEEL
    (
        {"valve_type": "GATE", "size": "DN50", "body_material": "SS316", "pressure_class": "CLASS150", "connection_type": "RF"},
        {"valve_type": "GATE", "size": "DN50", "body_material": "CARBON_STEEL", "pressure_class": "CLASS150", "connection_type": "RF"},
        "material",
    ),
    # 2. Pressure conflict: CLASS150 vs CLASS600
    (
        {"valve_type": "BALL", "size": "DN50", "body_material": "CARBON_STEEL", "pressure_class": "CLASS150", "connection_type": "RF"},
        {"valve_type": "BALL", "size": "DN50", "body_material": "CARBON_STEEL", "pressure_class": "CLASS600", "connection_type": "RF"},
        "pressure",
    ),
    # 3. Size conflict: DN50 vs DN100
    (
        {"valve_type": "BALL", "size": "DN50", "body_material": "CARBON_STEEL", "pressure_class": "CLASS150", "connection_type": "RF"},
        {"valve_type": "BALL", "size": "DN100", "body_material": "CARBON_STEEL", "pressure_class": "CLASS150", "connection_type": "RF"},
        "size",
    ),
    # 4. Equipment type conflict: GATE vs GLOBE
    (
        {"valve_type": "GATE", "size": "DN50", "body_material": "CARBON_STEEL", "pressure_class": "CLASS150", "connection_type": "RF"},
        {"valve_type": "GLOBE", "size": "DN50", "body_material": "CARBON_STEEL", "pressure_class": "CLASS150", "connection_type": "RF"},
        "type",
    ),
    # 5. Connection conflict: RF vs NPT
    (
        {"valve_type": "CHECK", "size": "DN50", "body_material": "CARBON_STEEL", "pressure_class": "CLASS150", "connection_type": "RF"},
        {"valve_type": "CHECK", "size": "DN50", "body_material": "CARBON_STEEL", "pressure_class": "CLASS150", "connection_type": "NPT"},
        "connection",
    ),
])
def test_critical_safety_hard_engineering_conflicts(
    explanation_service,
    source_attrs,
    cand_attrs,
    expected_conflict_keyword,
):
    """
    CRITICAL NON-NEGOTIABLE SAFETY INVARIANT:
    Even when semantic description similarity is very high (>0.90),
    engineering conflicts MUST be caught, classification MUST be DIFFERENT,
    confidence MUST be 0.0, recommended action MUST be REJECT, and explanation
    MUST explicitly state the conflict.
    """
    src = Material(id=uuid.uuid4(), source_material_code="SRC", source_description="SRC DESC", category="VALVE", **source_attrs)
    cand = Material(id=uuid.uuid4(), source_material_code="CAND", source_description="CAND DESC", category="VALVE", **cand_attrs)

    exp = explanation_service.generate_explanation(src, cand)

    assert exp.classification == "DIFFERENT"
    assert exp.confidence == 0.0
    assert exp.recommended_action == "REJECT"
    assert len(exp.engineering_conflicts) >= 1
    assert any(expected_conflict_keyword in c.reason.lower() or expected_conflict_keyword in c.attribute.lower() for c in exp.engineering_conflicts)
    assert "REJECTION" in exp.safety_assessment


def test_unknown_and_missing_attributes_explanation(explanation_service):
    # Missing pressure and connection on both sides
    src = Material(
        id=uuid.uuid4(),
        source_material_code="SRC-INC",
        source_description="BALL VALVE 2 IN",
        category="VALVE",
        valve_type="BALL", size="DN50",
    )
    cand = Material(
        id=uuid.uuid4(),
        source_material_code="CAND-INC",
        source_description="BALL VALVE 2 IN",
        category="VALVE",
        valve_type="BALL", size="DN50",
    )

    exp = explanation_service.generate_explanation(src, cand)

    assert exp.classification == "POTENTIALLY_EQUIVALENT"
    assert exp.recommended_action == "REVIEW_REQUIRED"
    assert len(exp.unknown_or_missing_attributes) > 0
    assert "GOVERNANCE REQUIRED" in exp.safety_assessment

    attr_map = {a.attribute: a for a in exp.attribute_comparisons}
    assert attr_map["pressure_class"].status == "UNKNOWN"
    assert attr_map["connection_type"].status == "UNKNOWN"


def test_semantic_similarity_does_not_override_engineering_conflict(explanation_service):
    """
    Verifies that high semantic score is transparently reported as evidence,
    but the system clearly explains that semantic similarity != engineering equivalence.
    """
    src = Material(
        id=uuid.uuid4(),
        source_material_code="SRC",
        source_description="BALL VALVE DN50 CS CLASS150 RF",
        category="VALVE",
        valve_type="BALL", size="DN50", body_material="CARBON_STEEL", pressure_class="CLASS150", connection_type="RF",
    )
    # Different pressure class: CLASS600 vs CLASS150
    cand = Material(
        id=uuid.uuid4(),
        source_material_code="CAND",
        source_description="BALL VALVE 2 IN CS 600# RF",
        category="VALVE",
        valve_type="BALL", size="DN50", body_material="CARBON_STEEL", pressure_class="CLASS600", connection_type="RF",
    )

    exp = explanation_service.generate_explanation(src, cand)

    # Semantic similarity is high
    assert exp.semantic_evidence.semantic_similarity_score > 0.85
    # But engineering conflict dominates
    assert exp.classification == "DIFFERENT"
    assert exp.confidence == 0.0
    assert "does not equal engineering equivalence" in exp.semantic_evidence.summary


def test_ai_failure_safe_fallback(explanation_service):
    src = Material(
        id=uuid.uuid4(),
        source_material_code="SRC",
        source_description="GATE VALVE DN50",
        category="VALVE",
        valve_type="GATE", size="DN50",
    )
    cand = Material(
        id=uuid.uuid4(),
        source_material_code="CAND",
        source_description="GATE VALVE DN50",
        category="VALVE",
        valve_type="GATE", size="DN50",
    )

    with patch.object(explanation_service.embedding_service, "encode_one", side_effect=RuntimeError("Embedding hardware fault")):
        exp = explanation_service.generate_explanation(src, cand)

        assert exp.classification == "POTENTIALLY_EQUIVALENT" or exp.classification == "SAME"
        assert exp.error is not None
        assert "Embedding hardware fault" in exp.error
        assert "fallback" in exp.safety_assessment.lower()


def test_explanation_generation_does_not_mutate_state(db, cpse_source, cpse_target, explanation_service):
    src = create_material(db, cpse_source, "BALL VALVE DN50 CS CLASS150 RF", valve_type="BALL", size="DN50")
    cand = create_material(db, cpse_target, "BALL VALVE DN50 CS CLASS150 RF", valve_type="BALL", size="DN50")

    mat_count_before = db.query(Material).count()
    rec_count_before = db.query(MatchRecommendation).count()
    map_count_before = db.query(MaterialNationalMapping).count()
    audit_count_before = db.query(AuditLog).count()

    exp = explanation_service.generate_explanation(src, cand)

    # Invariants: Zero mutation of database records
    assert db.query(Material).count() == mat_count_before
    assert db.query(MatchRecommendation).count() == rec_count_before
    assert db.query(MaterialNationalMapping).count() == map_count_before
    assert db.query(AuditLog).count() == audit_count_before


def test_candidate_explanation_api_endpoint(db, cpse_source, cpse_target):
    client = TestClient(app)
    src = create_material(db, cpse_source, "GLOBE VALVE DN50 CS CLASS150 RF", valve_type="GLOBE", size="DN50")
    cand = create_material(db, cpse_target, "GLOBE VALVE DN50 CS CLASS150 RF", valve_type="GLOBE", size="DN50")

    resp = client.get(f"/api/v1/materials/{src.id}/candidate-explanation/{cand.id}")
    assert resp.status_code == 200
    data = resp.json()

    assert data["status"] == "success"
    assert data["source_material_id"] == str(src.id)
    assert data["candidate_material_id"] == str(cand.id)
    assert "classification" in data
    assert "confidence" in data
    assert "recommended_action" in data
    assert "attribute_comparisons" in data
    assert "engineering_conflicts" in data
    assert "semantic_evidence" in data
    assert "audit_trail" in data


def test_review_recommendation_explanation_api_endpoint(db, cpse_source, cpse_target):
    client = TestClient(app)
    src = create_material(db, cpse_source, "CHECK VALVE DN50 CS CLASS150 RF", valve_type="CHECK", size="DN50")
    cand = create_material(db, cpse_target, "CHECK VALVE DN50 CS CLASS150 RF", valve_type="CHECK", size="DN50")

    rec = MatchRecommendation(
        id=uuid.uuid4(),
        source_material_id=src.id,
        candidate_material_id=cand.id,
        classification="POTENTIALLY_EQUIVALENT",
        confidence=0.75,
        explanation="Same valve type and size.",
    )
    db.add(rec)
    db.commit()

    from app.core.config import settings

    resp = client.get(
        f"/api/v1/reviews/{rec.id}/explanation",
        headers={"X-Reviewer-Token": settings.reviewer_token},
    )
    assert resp.status_code == 200
    data = resp.json()

    assert data["status"] == "success"
    assert data["recommendation_id"] == str(rec.id)
    assert data["source_material_id"] == str(src.id)
    assert data["candidate_material_id"] == str(cand.id)
    assert "attribute_comparisons" in data
    assert "semantic_evidence" in data


def test_existing_reviewer_action_semantics_unchanged(db, cpse_source, cpse_target):
    src = create_material(db, cpse_source, "BALL VALVE DN50 CS CLASS150 RF", valve_type="BALL", size="DN50")
    cand = create_material(db, cpse_target, "BALL VALVE DN50 CS CLASS150 RF", valve_type="BALL", size="DN50")

    rec = MatchRecommendation(
        id=uuid.uuid4(),
        source_material_id=src.id,
        candidate_material_id=cand.id,
        classification="POTENTIALLY_EQUIVALENT",
        confidence=0.80,
    )
    db.add(rec)
    db.commit()

    # Perform existing human review action
    res = process_review_action(
        db=db,
        recommendation_id=rec.id,
        action="MARK_DIFFERENT",
        reason="Field inspection confirmed trim variation.",
        actor="reviewer-1",
    )

    assert res["status"] == "success"
    assert res["action"] == "MARK_DIFFERENT"

    # AuditLog must capture human action with reason while recommendation record remains immutable
    audit = db.query(AuditLog).filter(AuditLog.entity_id == str(rec.id)).first()
    assert audit is not None
    assert audit.action == "MARK_DIFFERENT"
    assert audit.actor == "reviewer-1"
    assert "Field inspection confirmed" in audit.reason
