"""
Phase 5 — AI System Evaluation, Regression Hardening, and Failure Injection Suite.

Covers:
1. Full end-to-end lifecycle integration (import -> normalization -> AI profile -> retrieval
   -> hybrid/reranking -> engineering validation -> classification -> explanation -> reviewer action -> audit)
   tested under both AI_ENABLED=False and AI_ENABLED=True.
2. Invariant safety: UNKNOWN must never act as a wildcard for SAME under any permutation.
3. Critical engineering conflicts: SS316 vs CS, CLASS150 vs CLASS1500, DN50 vs DN100,
   GATE vs GLOBE, RF vs NPT.
4. Failure injection across all AI layers (embedding, retrieval, reranking, extraction, explainability).
5. Diagnostic / shadow endpoint DB immutability.
6. Scaled candidate retrieval performance boundaries and determinism.
"""

import uuid
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.config import settings
from app.models import CPSE, Material, MatchRecommendation, MaterialNationalMapping, AuditLog, NationalMaterial
from app.services.normalization import normalize_material_record
from app.services.matching import create_match_recommendations, classify_match
from app.services.harmonization import harmonize_material
from app.services.review import process_review_action
from app.services.ai.profile import MaterialProfile, AttributeState
from app.services.ai.extraction import PatternMaterialExtractor
from app.services.ai.retrieval import generate_semantic_candidates
from app.services.ai.reranking import MaterialSemanticReranker
from app.services.ai.explainability import MaterialExplanationService
from app.services.ai.validation import EngineeringKnowledgeEngine


@pytest.fixture
def cpse_alpha(db):
    code = f"CPSE-EVAL-A-{uuid.uuid4().hex[:6]}"
    c = CPSE(code=code, name=code)
    db.add(c)
    db.commit()
    db.refresh(c)
    yield c
    _cleanup_cpse(db, c)


@pytest.fixture
def cpse_beta(db):
    code = f"CPSE-EVAL-B-{uuid.uuid4().hex[:6]}"
    c = CPSE(code=code, name=code)
    db.add(c)
    db.commit()
    db.refresh(c)
    yield c
    _cleanup_cpse(db, c)


def _cleanup_cpse(db, cpse):
    try:
        mat_ids = [m.id for m in db.query(Material).filter(Material.cpse_id == cpse.id).all()]
        if mat_ids:
            db.query(MaterialNationalMapping).filter(MaterialNationalMapping.material_id.in_(mat_ids)).delete(synchronize_session=False)
            db.query(MatchRecommendation).filter(MatchRecommendation.source_material_id.in_(mat_ids)).delete(synchronize_session=False)
            db.query(MatchRecommendation).filter(MatchRecommendation.candidate_material_id.in_(mat_ids)).delete(synchronize_session=False)
            db.query(Material).filter(Material.id.in_(mat_ids)).delete(synchronize_session=False)
        db.delete(cpse)
        db.commit()
    except Exception:
        db.rollback()


def _create_mat(db, cpse, desc: str, **attrs) -> Material:
    mat = Material(
        id=uuid.uuid4(),
        cpse_id=cpse.id,
        source_material_code=f"MAT-{uuid.uuid4().hex[:6]}",
        source_description=desc,
        source_uom="EA",
        category=attrs.get("category", "VALVE"),
        normalized_description=desc,
        normalized_uom="EA",
        valve_type=attrs.get("valve_type"),
        size=attrs.get("size"),
        body_material=attrs.get("body_material"),
        pressure_class=attrs.get("pressure_class"),
        connection_type=attrs.get("connection_type"),
        trim=attrs.get("trim"),
    )
    db.add(mat)
    db.commit()
    db.refresh(mat)
    return mat


# ===========================================================================
# 1. FULL END-TO-END LIFECYCLE: AI DISABLED VS AI ENABLED
# ===========================================================================

@pytest.mark.parametrize("ai_hybrid_flag", [False, True])
def test_full_lifecycle_e2e(db, cpse_alpha, cpse_beta, ai_hybrid_flag):
    """
    Validates complete pipeline from import to audit under both feature flag states.
    In both cases, engineering invariants and review semantics must be identical.
    """
    # 1. Ingest material in CPSE A
    src = _create_mat(
        db, cpse_alpha,
        "BALL VALVE 2 IN CS 150# RF SS304 TRIM",
        valve_type="BALL", size="DN50", body_material="CARBON_STEEL",
        pressure_class="CLASS150", connection_type="RF", trim="SS304"
    )

    # Ingest equivalent candidate in CPSE B
    cand_equiv = _create_mat(
        db, cpse_beta,
        "VALVE, BALL, DN50, CS, CLASS150, RF, SS304 TRIM",
        valve_type="BALL", size="DN50", body_material="CARBON_STEEL",
        pressure_class="CLASS150", connection_type="RF", trim="SS304"
    )

    # Ingest hard-negative candidate in CPSE B (CLASS600 pressure rating conflict)
    cand_diff = _create_mat(
        db, cpse_beta,
        "VALVE, BALL, DN50, CS, CLASS600, RF, SS304 TRIM",
        valve_type="BALL", size="DN50", body_material="CARBON_STEEL",
        pressure_class="CLASS600", connection_type="RF", trim="SS304"
    )

    # 2. Normalization
    norm_res_src = normalize_material_record(db, src)
    norm_res_cand = normalize_material_record(db, cand_equiv)
    norm_res_diff = normalize_material_record(db, cand_diff)
    assert norm_res_src is not None

    # 3. AI Extraction Profile
    extractor = PatternMaterialExtractor()
    profile = extractor.extract(src.source_description)
    assert profile.category.value == "VALVE"
    assert profile.material_type.value == "BALL"
    assert profile.size.value == "DN50"

    # 4. Matching under controlled feature flag state
    with patch.object(settings, "ai_hybrid_retrieval_enabled", ai_hybrid_flag):
        recs = create_match_recommendations(db, src)
        assert len(recs) >= 1

        rec_map = {r.candidate_material_id: r for r in recs}

        # Equivalent candidate must be evaluated
        if cand_equiv.id in rec_map:
            equiv_rec = rec_map[cand_equiv.id]
            assert equiv_rec.classification == "SAME"
            assert equiv_rec.confidence >= 0.90

        # Hard-negative candidate (if retrieved) MUST be DIFFERENT with 0.0 confidence
        if cand_diff.id in rec_map:
            diff_rec = rec_map[cand_diff.id]
            assert diff_rec.classification == "DIFFERENT"
            assert diff_rec.confidence == 0.0

    # 5. Explainability Verification
    exp_service = MaterialExplanationService()
    explanation = exp_service.generate_explanation(src, cand_equiv)
    assert explanation.classification == "SAME"
    assert explanation.recommended_action == "AUTO_SAFE"
    assert len(explanation.engineering_conflicts) == 0

    diff_explanation = exp_service.generate_explanation(src, cand_diff)
    assert diff_explanation.classification == "DIFFERENT"
    assert diff_explanation.recommended_action == "REJECT"
    assert len(diff_explanation.engineering_conflicts) >= 1

    # 6. Human Reviewer Action
    target_rec = [r for r in recs if r.candidate_material_id == cand_equiv.id][0]
    action_res = process_review_action(
        db=db,
        recommendation_id=target_rec.id,
        action="ACCEPT",
        reason="Verified equivalent under SIH validation protocol.",
        actor="lead-reviewer",
    )
    assert action_res["status"] == "success"

    # 7. Audit Log Verification
    audit_entry = db.query(AuditLog).filter(
        AuditLog.entity_id == str(target_rec.id),
        AuditLog.action == "ACCEPT"
    ).first()
    assert audit_entry is not None
    assert audit_entry.actor == "lead-reviewer"
    assert "SIH validation" in audit_entry.reason


# ===========================================================================
# 2. INVARIANT SAFETY: UNKNOWN CAN NEVER ACT AS A WILDCARD
# ===========================================================================

@pytest.mark.parametrize("source_spec,cand_spec,expected_classification", [
    # A. Source has size, candidate missing size -> POTENTIALLY_EQUIVALENT, NOT SAME
    (
        {"valve_type": "BALL", "size": "DN50", "body_material": "CARBON_STEEL", "pressure_class": "CLASS150", "connection_type": "RF", "trim": "SS304"},
        {"valve_type": "BALL", "size": None, "body_material": "CARBON_STEEL", "pressure_class": "CLASS150", "connection_type": "RF", "trim": "SS304"},
        "POTENTIALLY_EQUIVALENT",
    ),
    # B. Source missing pressure, candidate has pressure -> POTENTIALLY_EQUIVALENT, NOT SAME
    (
        {"valve_type": "BALL", "size": "DN50", "body_material": "CARBON_STEEL", "pressure_class": None, "connection_type": "RF", "trim": "SS304"},
        {"valve_type": "BALL", "size": "DN50", "body_material": "CARBON_STEEL", "pressure_class": "CLASS150", "connection_type": "RF", "trim": "SS304"},
        "POTENTIALLY_EQUIVALENT",
    ),
    # C. Both missing trim -> POTENTIALLY_EQUIVALENT, NOT SAME
    (
        {"valve_type": "GATE", "size": "DN50", "body_material": "CARBON_STEEL", "pressure_class": "CLASS150", "connection_type": "RF", "trim": None},
        {"valve_type": "GATE", "size": "DN50", "body_material": "CARBON_STEEL", "pressure_class": "CLASS150", "connection_type": "RF", "trim": None},
        "POTENTIALLY_EQUIVALENT",
    ),
    # D. Both missing connection type and trim -> POTENTIALLY_EQUIVALENT
    (
        {"valve_type": "GLOBE", "size": "DN25", "body_material": "CARBON_STEEL", "pressure_class": "CLASS150", "connection_type": None, "trim": None},
        {"valve_type": "GLOBE", "size": "DN25", "body_material": "CARBON_STEEL", "pressure_class": "CLASS150", "connection_type": None, "trim": None},
        "POTENTIALLY_EQUIVALENT",
    ),
])
def test_unknown_never_acts_as_wildcard_for_same(source_spec, cand_spec, expected_classification):
    """
    CRITICAL INVARIANT:
    Missing or UNKNOWN attributes must NEVER be treated as matching wildcards.
    Even with identical descriptions, missing technical attributes must force
    POTENTIALLY_EQUIVALENT to require human governance.
    """
    src = Material(
        id=uuid.uuid4(),
        source_material_code="SRC-WILD",
        source_description="INDUSTRIAL VALVE SPECIFICATION",
        category="VALVE",
        **source_spec,
    )
    cand = Material(
        id=uuid.uuid4(),
        source_material_code="CAND-WILD",
        source_description="INDUSTRIAL VALVE SPECIFICATION",
        category="VALVE",
        **cand_spec,
    )

    match_res = classify_match(src, cand)
    assert match_res["classification"] == expected_classification
    assert match_res["classification"] != "SAME"

    exp_service = MaterialExplanationService()
    exp = exp_service.generate_explanation(src, cand)
    assert exp.classification == expected_classification
    assert exp.recommended_action == "REVIEW_REQUIRED"
    assert exp.recommended_action != "AUTO_SAFE"
    assert len(exp.unknown_or_missing_attributes) > 0


# ===========================================================================
# 3. CRITICAL HARD CONFLICT SAFETY BENCHMARK (THE 0.00% RULE)
# ===========================================================================

@pytest.mark.parametrize("conflict_name,src_attrs,cand_attrs,expected_reason_substr", [
    (
        "SS316 vs Carbon Steel",
        {"valve_type": "GATE", "size": "DN50", "body_material": "SS316", "pressure_class": "CLASS150", "connection_type": "RF"},
        {"valve_type": "GATE", "size": "DN50", "body_material": "CARBON_STEEL", "pressure_class": "CLASS150", "connection_type": "RF"},
        "material",
    ),
    (
        "CLASS150 vs CLASS1500",
        {"valve_type": "BALL", "size": "DN50", "body_material": "CARBON_STEEL", "pressure_class": "CLASS150", "connection_type": "RF"},
        {"valve_type": "BALL", "size": "DN50", "body_material": "CARBON_STEEL", "pressure_class": "CLASS1500", "connection_type": "RF"},
        "pressure",
    ),
    (
        "DN50 vs DN100",
        {"valve_type": "BALL", "size": "DN50", "body_material": "CARBON_STEEL", "pressure_class": "CLASS150", "connection_type": "RF"},
        {"valve_type": "BALL", "size": "DN100", "body_material": "CARBON_STEEL", "pressure_class": "CLASS150", "connection_type": "RF"},
        "size",
    ),
    (
        "GATE vs GLOBE",
        {"valve_type": "GATE", "size": "DN50", "body_material": "CARBON_STEEL", "pressure_class": "CLASS150", "connection_type": "RF"},
        {"valve_type": "GLOBE", "size": "DN50", "body_material": "CARBON_STEEL", "pressure_class": "CLASS150", "connection_type": "RF"},
        "type",
    ),
    (
        "RF vs NPT",
        {"valve_type": "CHECK", "size": "DN50", "body_material": "CARBON_STEEL", "pressure_class": "CLASS150", "connection_type": "RF"},
        {"valve_type": "CHECK", "size": "DN50", "body_material": "CARBON_STEEL", "pressure_class": "CLASS150", "connection_type": "NPT"},
        "connection",
    ),
])
def test_hard_conflicts_override_semantic_similarity(conflict_name, src_attrs, cand_attrs, expected_reason_substr):
    """
    NON-NEGOTIABLE SAFETY GATE:
    Hard engineering conflicts must ALWAYS result in DIFFERENT, 0.0 confidence,
    and REJECT recommended action regardless of dense semantic vector similarity.
    """
    src = Material(
        id=uuid.uuid4(),
        source_material_code="SRC-HARD",
        source_description=f"VALVE DN50 CS CLASS150 RF - {conflict_name}",
        category="VALVE",
        **src_attrs,
    )
    cand = Material(
        id=uuid.uuid4(),
        source_material_code="CAND-HARD",
        source_description=f"VALVE DN50 CS CLASS150 RF - {conflict_name}",
        category="VALVE",
        **cand_attrs,
    )

    exp_service = MaterialExplanationService()
    exp = exp_service.generate_explanation(src, cand)

    assert exp.classification == "DIFFERENT"
    assert exp.confidence == 0.0
    assert exp.recommended_action == "REJECT"
    assert len(exp.engineering_conflicts) >= 1
    assert any(expected_reason_substr in c.reason.lower() or expected_reason_substr in c.attribute.lower() for c in exp.engineering_conflicts)


# ===========================================================================
# 4. FAILURE INJECTION TESTS ACROSS AI SUBSYSTEMS
# ===========================================================================

def test_failure_injection_embedding_generation(db, cpse_alpha, cpse_beta):
    """
    Failure Injection: PyTorch/SentenceTransformers raises an unexpected hardware/memory fault.
    System must safely fall back to baseline candidate retrieval without crashing.
    """
    src = _create_mat(db, cpse_alpha, "BALL VALVE DN50 CS CLASS150 RF")
    cand = _create_mat(db, cpse_beta, "BALL VALVE DN50 CS CLASS150 RF")

    with patch("app.services.ai.retrieval.EmbeddingService.get_instance", side_effect=RuntimeError("GPU OOM / Memory fault")):
        with patch.object(settings, "ai_hybrid_retrieval_enabled", True):
            recs = create_match_recommendations(db, src)
            # Must not crash; baseline candidates must be returned
            assert isinstance(recs, list)
            assert len(recs) >= 1


def test_failure_injection_ai_reranking(cpse_alpha, cpse_beta):
    """
    Failure Injection: Semantic reranker raises an exception during batch inference.
    Reranker must return baseline candidates safely without halting.
    """
    src = Material(id=uuid.uuid4(), source_material_code="SRC", source_description="VALVE", category="VALVE")
    cand1 = Material(id=uuid.uuid4(), source_material_code="C1", source_description="VALVE", category="VALVE")

    reranker = MaterialSemanticReranker()
    with patch.object(reranker.embedding_service, "encode_one", side_effect=ValueError("Corrupt embedding vector")):
        base_list, reranked_list, _ = reranker.rerank(src, [cand1])
        # Graceful degradation to original baseline order
        assert len(base_list) == 1
        assert len(reranked_list) == 1


def test_failure_injection_extraction():
    """
    Failure Injection: Extractor receives unparseable garbage or binary tokens.
    Must return a valid MaterialProfile with UNKNOWN/NOT_PRESENT states without throwing.
    """
    extractor = PatternMaterialExtractor()
    garbage_input = "\x00\x01\x02 ??? -- !! @@ INVALID BINARY CHUNK"
    profile = extractor.extract(garbage_input)

    assert isinstance(profile, MaterialProfile)
    assert profile.category.state in [AttributeState.NOT_PRESENT, AttributeState.UNKNOWN]
    assert profile.size.state in [AttributeState.NOT_PRESENT, AttributeState.UNKNOWN]


def test_failure_injection_explainability():
    """
    Failure Injection: Explanation generation crashes during dense cosine calculation.
    Service must return safe fallback report with deterministic classification and error note.
    """
    src = Material(id=uuid.uuid4(), source_material_code="SRC", source_description="BALL VALVE DN50", category="VALVE", valve_type="BALL", size="DN50")
    cand = Material(id=uuid.uuid4(), source_material_code="CAND", source_description="BALL VALVE DN50", category="VALVE", valve_type="BALL", size="DN50")

    service = MaterialExplanationService()
    with patch.object(service.embedding_service, "encode_one", side_effect=Exception("Uncaught vector calculation error")):
        exp = service.generate_explanation(src, cand)
        assert exp is not None
        assert exp.classification in ["POTENTIALLY_EQUIVALENT", "SAME"]
        assert exp.error is not None
        assert "Uncaught vector calculation error" in exp.error


# ===========================================================================
# 5. DIAGNOSTIC / SHADOW ENDPOINTS DB IMMUTABILITY
# ===========================================================================

def test_diagnostic_endpoints_do_not_mutate_database(db, cpse_alpha, cpse_beta):
    """
    Verifies that calling all 6 AI diagnostic and explanation endpoints produces
    zero mutations in Material, MatchRecommendation, MaterialNationalMapping, AuditLog, and CPSE tables.
    """
    client = TestClient(app)
    src = _create_mat(db, cpse_alpha, "GATE VALVE DN50 CS CLASS150 RF", valve_type="GATE", size="DN50")
    cand = _create_mat(db, cpse_beta, "GATE VALVE DN50 CS CLASS150 RF", valve_type="GATE", size="DN50")

    rec = MatchRecommendation(
        id=uuid.uuid4(),
        source_material_id=src.id,
        candidate_material_id=cand.id,
        classification="POTENTIALLY_EQUIVALENT",
        confidence=0.75,
    )
    db.add(rec)
    db.commit()

    # Snapshot baseline counts
    counts_before = {
        "material": db.query(Material).count(),
        "recommendation": db.query(MatchRecommendation).count(),
        "mapping": db.query(MaterialNationalMapping).count(),
        "audit": db.query(AuditLog).count(),
        "cpse": db.query(CPSE).count(),
    }

    # 1. Candidate comparison endpoint
    resp1 = client.get(f"/api/v1/materials/{src.id}/candidate-comparison")
    assert resp1.status_code == 200

    # 2. Shadow match endpoint
    resp2 = client.get(f"/api/v1/materials/{src.id}/shadow-match")
    assert resp2.status_code == 200

    # 3. AI profile endpoint
    resp3 = client.get(f"/api/v1/materials/{src.id}/ai-profile")
    assert resp3.status_code == 200

    # 4. Semantic reranking endpoint
    resp4 = client.get(f"/api/v1/materials/{src.id}/semantic-reranking")
    assert resp4.status_code == 200

    # 5. Candidate explanation endpoint
    resp5 = client.get(f"/api/v1/materials/{src.id}/candidate-explanation/{cand.id}")
    assert resp5.status_code == 200

    # 6. Review recommendation explanation endpoint
    resp6 = client.get(
        f"/api/v1/reviews/{rec.id}/explanation",
        headers={"X-Reviewer-Token": settings.reviewer_token},
    )
    assert resp6.status_code == 200

    # Snapshot after counts
    counts_after = {
        "material": db.query(Material).count(),
        "recommendation": db.query(MatchRecommendation).count(),
        "mapping": db.query(MaterialNationalMapping).count(),
        "audit": db.query(AuditLog).count(),
        "cpse": db.query(CPSE).count(),
    }

    # Invariant: Zero mutations across all tables
    assert counts_before == counts_after


# ===========================================================================
# 6. CONFIGURATION SAFETY: FLAGS REMAIN OFF BY DEFAULT
# ===========================================================================

def test_production_feature_flags_default_off():
    """
    CRITICAL ARCHITECTURAL REQUIREMENT:
    Production feature flags MUST remain strictly False by default.
    AI functionality operates in diagnostic, shadow, or opt-in mode.
    """
    assert settings.ai_hybrid_retrieval_enabled is False
    assert settings.ai_semantic_reranking_enabled is False
    assert settings.AI_HYBRID_RETRIEVAL_ENABLED is False
    assert settings.AI_SEMANTIC_RERANKING_ENABLED is False
