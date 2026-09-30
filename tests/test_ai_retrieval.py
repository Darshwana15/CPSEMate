import uuid
import pytest
from fastapi.testclient import TestClient

from app.models import CPSE, Material, MatchRecommendation, MaterialNationalMapping
from app.services.ai.retrieval import (
    generate_semantic_candidates,
    compare_candidate_retrieval,
)
from app.main import app


@pytest.fixture
def cpse_a(db):
    c = CPSE(code=f"CPSE-A-{uuid.uuid4()}", name="CPSE Alpha")
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


@pytest.fixture
def cpse_b(db):
    c = CPSE(code=f"CPSE-B-{uuid.uuid4()}", name="CPSE Beta")
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


def create_test_mat(db, cpse, desc: str, cat: str = "VALVE", **kwargs) -> Material:
    mat = Material(
        id=uuid.uuid4(),
        cpse_id=cpse.id,
        source_material_code=f"MAT-{uuid.uuid4()}",
        source_description=desc,
        source_uom="EA",
        category=cat,
        normalized_description=desc,
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


def test_ai_candidate_retrieval_top_k(db, cpse_a, cpse_b):
    # Source material in CPSE A
    src = create_test_mat(
        db, cpse_a,
        desc="GATE VALVE DN50 CS CLASS150 RF SS316",
        valve_type="GATE", size="DN50", body_material="CARBON_STEEL",
        pressure_class="CLASS150", connection_type="RF", trim="SS316"
    )

    # 5 Candidate materials in CPSE B
    candidates = [
        create_test_mat(db, cpse_b, f"VALVE GATE DN50 CS 150# RF SS316 VARIANT {i}", valve_type="GATE", size="DN50")
        for i in range(5)
    ]

    # Test top_k=2 constraint
    top_2 = generate_semantic_candidates(db, src, top_k=2, min_similarity=0.0)
    assert len(top_2) <= 2

    # Test top_k=4 constraint
    top_4 = generate_semantic_candidates(db, src, top_k=4, min_similarity=0.0)
    assert len(top_4) <= 4

    # Assert sorted descending by similarity score
    scores = [c.similarity_score for c in top_4]
    assert scores == sorted(scores, reverse=True)


def test_ai_retrieval_same_cpse_and_self_exclusion(db, cpse_a, cpse_b):
    src = create_test_mat(
        db, cpse_a,
        desc="BALL VALVE 2 IN SS316 150# FLANGED",
        valve_type="BALL", size="DN50", body_material="SS316"
    )

    # Identical description in same CPSE (must be excluded)
    same_cpse_mat = create_test_mat(
        db, cpse_a,
        desc="BALL VALVE 2 IN SS316 150# FLANGED",
        valve_type="BALL", size="DN50", body_material="SS316"
    )

    # Similar description in other CPSE (must be included)
    other_cpse_mat = create_test_mat(
        db, cpse_b,
        desc="BALL VALVE DN50 SS316 CLASS150 RF",
        valve_type="BALL", size="DN50", body_material="SS316"
    )

    results = generate_semantic_candidates(db, src, top_k=10, min_similarity=0.0, candidate_cpse_id=cpse_b.id)
    result_ids = [c.material_id for c in results]

    assert src.id not in result_ids, "Self-matching must be strictly prohibited"
    assert same_cpse_mat.id not in result_ids, "Same-CPSE matching must be strictly prohibited"
    assert other_cpse_mat.id in result_ids, "Cross-CPSE candidate should be discovered"


def test_ai_retrieval_similarity_threshold(db, cpse_a, cpse_b):
    src = create_test_mat(db, cpse_a, desc="CENTRIFUGAL PUMP 50M3/HR CS", cat="PUMP")

    # High similarity candidate (PUMP)
    pump_cand = create_test_mat(db, cpse_b, desc="PUMP CENTRIFUGAL 50 M3/HR CARBON STEEL", cat="PUMP")

    # Very high threshold (e.g. 0.999) filters out non-identical vectors
    strict_results = generate_semantic_candidates(db, src, top_k=10, min_similarity=0.999, candidate_cpse_id=cpse_b.id)
    # Lenient threshold keeps it
    lenient_results = generate_semantic_candidates(db, src, top_k=10, min_similarity=0.10, candidate_cpse_id=cpse_b.id)

    assert len(strict_results) <= len(lenient_results)
    assert any(c.material_id == pump_cand.id for c in lenient_results)


def test_ai_retrieval_does_not_mutate_state(db, cpse_a, cpse_b):
    src = create_test_mat(db, cpse_a, desc="NEEDLE VALVE 1/2 IN SS316 6000PSI NPT")
    cand = create_test_mat(db, cpse_b, desc="VALVE NEEDLE 1/2IN SS316 6000# NPT")

    recs_before = db.query(MatchRecommendation).count()
    mappings_before = db.query(MaterialNationalMapping).count()

    results = generate_semantic_candidates(db, src, top_k=5)
    assert len(results) > 0

    recs_after = db.query(MatchRecommendation).count()
    mappings_after = db.query(MaterialNationalMapping).count()

    assert recs_before == recs_after, "AI candidate retrieval must not create recommendations"
    assert mappings_before == mappings_after, "AI candidate retrieval must not mutate mappings"


def test_compare_candidate_retrieval_parallel(db, cpse_a, cpse_b):
    src = create_test_mat(db, cpse_a, desc="GATE VALVE DN50 CS CLASS150 RF SS316", valve_type="GATE", size="DN50")
    cand1 = create_test_mat(db, cpse_b, desc="GATE VALVE DN50 CS CLASS150 RF SS316", valve_type="GATE", size="DN50")

    result = compare_candidate_retrieval(db, src, top_k=10, min_similarity=0.50)
    data = result.to_dict()

    assert data["source_material_id"] == str(src.id)
    assert data["baseline_candidate_count"] >= 1
    assert data["ai_candidate_count"] >= 1
    assert data["intersection_count"] >= 1
    assert 0.0 <= data["overlap_ratio"] <= 1.0
    assert "baseline_latency_ms" in data
    assert "ai_latency_ms" in data
    assert len(data["ai_candidates"]) >= 1
    assert len(data["baseline_candidates"]) >= 1


def test_candidate_comparison_endpoint(db, cpse_a, cpse_b):
    client = TestClient(app)
    src = create_test_mat(db, cpse_a, desc="BALL VALVE 2 IN CS 150# RF", valve_type="BALL")
    cand = create_test_mat(db, cpse_b, desc="VALVE BALL 2 INCH CS CLASS150 RF", valve_type="BALL")

    resp = client.get(f"/api/v1/materials/{src.id}/candidate-comparison?top_k=5&min_similarity=0.4")
    assert resp.status_code == 200
    body = resp.json()

    assert body["status"] == "success"
    assert body["source_material_id"] == str(src.id)
    assert body["ai_candidate_count"] >= 1
    assert "overlap_ratio" in body

