"""
Unit and integration tests for AI-assisted semantic reranking (Phase 3B).
"""

import uuid
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.models import CPSE, Material, MatchRecommendation, MaterialNationalMapping
from app.services.ai.reranking import (
    MaterialSemanticReranker,
    RerankedCandidate,
    SemanticRerankingReport,
    rerank_candidates_shadow,
)
from app.services.ai.reranking_benchmark import (
    RERANKING_BENCHMARK_SCENARIOS,
    run_reranking_benchmark,
)
from app.services.ai.shadow import HybridCandidate
from app.services.matching import create_match_recommendations


@pytest.fixture
def reranker():
    return MaterialSemanticReranker()


@pytest.fixture
def cpse_source(db):
    code = f"CPSE-RR-SRC-{uuid.uuid4().hex[:6]}"
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
            db.query(Material).filter(Material.cpse_id == c.id).delete(synchronize_session=False)
        db.delete(c)
        db.commit()
    except Exception:
        db.rollback()


@pytest.fixture
def cpse_target(db):
    code = f"CPSE-RR-TGT-{uuid.uuid4().hex[:6]}"
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
            db.query(Material).filter(Material.cpse_id == c.id).delete(synchronize_session=False)
        db.delete(c)
        db.commit()
    except Exception:
        db.rollback()


def create_material(db, cpse, desc: str, **kwargs) -> Material:
    mat = Material(
        id=uuid.uuid4(),
        cpse_id=cpse.id,
        source_material_code=f"MAT-RR-{uuid.uuid4().hex[:6]}",
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


def test_reranker_deterministic_output(reranker):
    src = Material(
        id=uuid.uuid4(),
        source_material_code="S-1",
        source_description="BALL VALVE DN50 CS CLASS150 RF",
        category="VALVE",
        valve_type="BALL", size="DN50", body_material="CARBON_STEEL",
    )
    c1 = Material(
        id=uuid.uuid4(),
        source_material_code="C-1",
        source_description="BALL VALVE 2 IN CS 150# RF",
        category="VALVE",
        valve_type="BALL", size="DN50", body_material="CARBON_STEEL",
    )
    c2 = Material(
        id=uuid.uuid4(),
        source_material_code="C-2",
        source_description="GLOBE VALVE DN50 CS CLASS150 RF",
        category="VALVE",
        valve_type="GLOBE", size="DN50", body_material="CARBON_STEEL",
    )

    reranked1, _, _ = reranker.rerank(src, [c1, c2])
    reranked2, _, _ = reranker.rerank(src, [c1, c2])

    assert [c.candidate_id for c in reranked1] == [c.candidate_id for c in reranked2]
    assert [c.ai_semantic_score for c in reranked1] == [c.ai_semantic_score for c in reranked2]


def test_candidates_receive_scores_and_correct_ordering(reranker):
    src = Material(
        id=uuid.uuid4(),
        source_material_code="S-1",
        source_description="GATE VALVE DN50 CS CLASS150 RF",
        category="VALVE",
        valve_type="GATE", size="DN50", body_material="CARBON_STEEL",
    )
    # Identical phrasing: highest similarity
    c_identical = Material(
        id=uuid.uuid4(),
        source_material_code="C-IDENTICAL",
        source_description="GATE VALVE DN50 CS CLASS150 RF",
        category="VALVE",
        valve_type="GATE", size="DN50", body_material="CARBON_STEEL",
    )
    # Unrelated equipment: lowest similarity
    c_unrelated = Material(
        id=uuid.uuid4(),
        source_material_code="C-UNRELATED",
        source_description="CENTRIFUGAL PUMP 100 M3/HR",
        category="PUMP",
    )

    # Initial order: unrelated first, identical second
    reranked, baseline, _ = reranker.rerank(src, [c_unrelated, c_identical])

    # In baseline, unrelated is position 1, identical is position 2
    assert baseline[0].candidate_id == c_unrelated.id
    assert baseline[1].candidate_id == c_identical.id

    # In reranked, identical moves to position 1, unrelated drops to position 2
    assert reranked[0].candidate_id == c_identical.id
    assert reranked[1].candidate_id == c_unrelated.id
    assert reranked[0].ai_semantic_score > reranked[1].ai_semantic_score
    assert reranked[0].rank_movement == 1  # moved from pos 2 to pos 1
    assert reranked[1].rank_movement == -1  # dropped from pos 1 to pos 2


def test_retrieval_origin_provenance_intact(reranker):
    src = Material(id=uuid.uuid4(), source_description="BALL VALVE DN50", category="VALVE")
    c_base = HybridCandidate(
        material=Material(id=uuid.uuid4(), source_description="BALL VALVE DN50", category="VALVE"),
        is_in_baseline=True,
        is_in_ai=False,
    )
    c_ai = HybridCandidate(
        material=Material(id=uuid.uuid4(), source_description="BALL VALVE DN50", category="VALVE"),
        is_in_baseline=False,
        is_in_ai=True,
    )
    c_both = HybridCandidate(
        material=Material(id=uuid.uuid4(), source_description="BALL VALVE DN50", category="VALVE"),
        is_in_baseline=True,
        is_in_ai=True,
    )

    reranked, _, _ = reranker.rerank(src, [c_base, c_ai, c_both])

    origins = {c.candidate_id: c.retrieval_origin for c in reranked}
    assert origins[c_base.candidate_id] == "BASELINE"
    assert origins[c_ai.candidate_id] == "AI_ONLY"
    assert origins[c_both.candidate_id] == "BOTH"


def test_hard_conflict_preserved_and_not_overridden_by_high_similarity(reranker):
    """
    CRITICAL ARCHITECTURAL TEST:
    A candidate that looks very similar semantically but has a hard engineering conflict
    (e.g. DN50 vs DN100 or SS316 vs CS) MUST NOT be classified as SAME.
    Its classification must remain DIFFERENT with confidence = 0.0.
    """
    src = Material(
        id=uuid.uuid4(),
        source_material_code="SRC-VLV",
        source_description="BALL VALVE DN50 CS CLASS150 RF",
        category="VALVE",
        valve_type="BALL", size="DN50", body_material="CARBON_STEEL", pressure_class="CLASS150",
    )
    # Hard size conflict: DN100 vs DN50
    cand_conflict = Material(
        id=uuid.uuid4(),
        source_material_code="CAND-CONFLICT",
        source_description="BALL VALVE DN100 CS CLASS150 RF",
        category="VALVE",
        valve_type="BALL", size="DN100", body_material="CARBON_STEEL", pressure_class="CLASS150",
    )

    reranked, _, _ = reranker.rerank(src, [cand_conflict])
    c = reranked[0]

    # Semantic similarity might be high because text differs by one number
    assert c.ai_semantic_score > 0.70
    # But engineering validation MUST identify the conflict
    assert not c.is_engineering_compatible
    assert any("size conflict" in conf.lower() for conf in c.hard_conflicts)
    # Deterministic classifier MUST reject it
    assert c.classification == "DIFFERENT"
    assert c.confidence == 0.0


def test_unknown_and_not_present_attributes_preserved(reranker):
    src = Material(
        id=uuid.uuid4(),
        source_material_code="SRC-INCOMPLETE",
        source_description="BALL VALVE 2 IN",
        category="VALVE",
        valve_type="BALL", size="DN50",
        # pressure, material, connection are NULL/None
    )
    cand = Material(
        id=uuid.uuid4(),
        source_material_code="CAND-INCOMPLETE",
        source_description="BALL VALVE 2 IN",
        category="VALVE",
        valve_type="BALL", size="DN50",
    )

    reranked, _, _ = reranker.rerank(src, [cand])
    c = reranked[0]

    # With missing attributes on both sides, classification is POTENTIALLY_EQUIVALENT, NOT SAME
    assert c.classification == "POTENTIALLY_EQUIVALENT"
    assert "missing information" in c.explanation.lower()


def test_semantic_reranking_diagnostic_endpoint(db, cpse_source, cpse_target):
    client = TestClient(app)
    src = create_material(db, cpse_source, "NEEDLE VALVE 1/2 IN SS316 6000# NPT", valve_type="NEEDLE", size="DN15")
    cand = create_material(db, cpse_target, "NEEDLE VALVE 1/2 IN SS316 6000# NPT", valve_type="NEEDLE", size="DN15")

    resp = client.get(f"/api/v1/materials/{src.id}/semantic-reranking")
    assert resp.status_code == 200
    data = resp.json()

    assert data["status"] == "success"
    assert data["source_material_id"] == str(src.id)
    assert "candidate_count" in data
    assert "reranked_candidates" in data
    assert "classification_distribution_reranked" in data


def test_diagnostic_endpoint_does_not_mutate_database(db, cpse_source, cpse_target):
    client = TestClient(app)
    src = create_material(db, cpse_source, "GATE VALVE DN50 CS CLASS150 RF", valve_type="GATE", size="DN50")
    cand = create_material(db, cpse_target, "GATE VALVE DN50 CS CLASS150 RF", valve_type="GATE", size="DN50")

    count_recs_before = db.query(MatchRecommendation).count()
    count_maps_before = db.query(MaterialNationalMapping).count()

    resp = client.get(f"/api/v1/materials/{src.id}/semantic-reranking")
    assert resp.status_code == 200

    # Assert zero persisted mutations
    assert db.query(MatchRecommendation).count() == count_recs_before
    assert db.query(MaterialNationalMapping).count() == count_maps_before


def test_production_matching_behavior_unchanged_by_reranking(db, cpse_source, cpse_target):
    """create_match_recommendations() must produce recommendations according to matching rules without mutation."""
    src = create_material(db, cpse_source, "BALL VALVE DN50 CS CLASS150 RF", valve_type="BALL", size="DN50")
    cand = create_material(db, cpse_target, "BALL VALVE DN50 CS CLASS150 RF", valve_type="BALL", size="DN50")

    # Production matching
    recs = create_match_recommendations(db, src)
    db.commit()

    assert len(recs) >= 1
    # Check that recommendations table has recommendations
    assert any(r.candidate_material_id == cand.id for r in recs)


def test_reranking_failure_falls_back_safely(db, cpse_source):
    """If semantic reranking encounters an error, shadow analysis returns safe error report without crashing."""
    src = create_material(db, cpse_source, "CHECK VALVE DN50", valve_type="CHECK")

    with patch.object(MaterialSemanticReranker, "rerank", side_effect=RuntimeError("Embedding model failure")):
        report = rerank_candidates_shadow(db, src, candidates=[])
        assert report.error is not None
        assert "Embedding model failure" in report.error


def test_benchmark_structure_and_ground_truth():
    """Verifies that the benchmark suite contains >= 10 independent scenarios with realistic ground truth."""
    scenarios = RERANKING_BENCHMARK_SCENARIOS
    assert len(scenarios) >= 10
    total_hard_negatives = 0

    for scen in scenarios:
        assert scen.scenario_id
        assert scen.scenario_name
        assert scen.source_description
        assert len(scen.candidate_pool) >= 2
        assert len(scen.expected_relevant_ids) >= 1

        cand_ids = [c["id"] for c in scen.candidate_pool]
        for rel_id in scen.expected_relevant_ids:
            assert rel_id in cand_ids

        total_hard_negatives += sum(1 for c in scen.candidate_pool if c.get("is_hard_negative"))

    assert total_hard_negatives >= 10, f"Expected realistic hard negatives pool, found {total_hard_negatives}"


def test_run_reranking_benchmark_suite():
    """Executes the complete multi-scenario reranking benchmark and verifies performance and safety."""
    metrics = run_reranking_benchmark(RERANKING_BENCHMARK_SCENARIOS)

    # 1. Independent scenario execution check
    assert metrics.total_scenarios >= 10
    assert metrics.total_scenarios == len(RERANKING_BENCHMARK_SCENARIOS)
    assert len(metrics.scenario_results) == metrics.total_scenarios

    # 2. Ranking metrics
    assert metrics.top1_accuracy_reranked >= 0.90, f"Expected top1 accuracy >= 0.90, got {metrics.top1_accuracy_reranked}"
    assert metrics.recall_at_1_reranked >= 0.90
    assert metrics.recall_at_3_reranked == 1.0
    assert metrics.mrr_reranked > metrics.mrr_baseline, "Reranked MRR should exceed baseline"
    assert metrics.scenarios_improved > 0
    assert metrics.scenarios_worsened == 0

    # 3. Critical Safety Invariants
    assert metrics.hard_negatives_total >= 10
    assert metrics.conflict_preservation_rate == 1.0, f"Expected 100% conflicts preserved, got {metrics.conflict_preservation_rate}"
    assert metrics.zero_false_same_rate == 1.0, f"Expected 0% false SAME on hard negatives, got {metrics.zero_false_same_rate}"
    assert metrics.false_same_count == 0, f"Zero false SAME invariant violated: {metrics.false_same_count}"

    # 4. Latency
    assert metrics.average_latency_ms < 500.0, f"Latency too high: {metrics.average_latency_ms}ms"
    assert metrics.max_latency_ms < 2000.0, f"Max latency too high: {metrics.max_latency_ms}ms"
