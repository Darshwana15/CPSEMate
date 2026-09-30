import uuid
import pytest
from fastapi.testclient import TestClient

from app.models import CPSE, Material, MatchRecommendation, MaterialNationalMapping
from app.services.ai.shadow import (
    generate_hybrid_candidates,
    run_shadow_matching_analysis,
)
from app.services.matching import create_match_recommendations
from app.main import app


@pytest.fixture
def cpse_source(db):
    c = CPSE(code=f"CPSE-SRC-SHADOW-{uuid.uuid4().hex[:6]}", name="Source CPSE")
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


@pytest.fixture
def cpse_target(db):
    c = CPSE(code=f"CPSE-TGT-SHADOW-{uuid.uuid4().hex[:6]}", name="Target CPSE")
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


def create_material(db, cpse, desc: str, cat: str = "VALVE", **kwargs) -> Material:
    mat = Material(
        id=uuid.uuid4(),
        cpse_id=cpse.id,
        source_material_code=f"MAT-SHADOW-{uuid.uuid4().hex[:6]}",
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


def test_baseline_preserved_and_ai_only_added_in_hybrid(db, cpse_source, cpse_target):
    # Source material: BALL VALVE
    src = create_material(
        db, cpse_source,
        desc="BALL VALVE DN50 CS CLASS150 RF SS316",
        valve_type="BALL", size="DN50", body_material="CARBON_STEEL",
        pressure_class="CLASS150", connection_type="RF", trim="SS316"
    )

    # Candidate 1: Standard BALL VALVE (captured by both baseline and AI)
    cand_both = create_material(
        db, cpse_target,
        desc="BALL VALVE DN50 CS CLASS150 RF SS316",
        valve_type="BALL", size="DN50", body_material="CARBON_STEEL",
        pressure_class="CLASS150", connection_type="RF", trim="SS316"
    )

    # Candidate 2: Misspelled/Permuted BALL VALVE with no valve_type set, but category VALVE
    # Baseline query pulls it if valve_type is None
    cand_base = create_material(
        db, cpse_target,
        desc="VALVE BALL DN50 150# RF CARBON STEEL",
        valve_type=None, size="DN50"
    )

    # Candidate 3: Misfiled under category GASKET (baseline query misses it because category != VALVE),
    # but semantic retrieval discovers it with category_filter=False
    cand_ai = create_material(
        db, cpse_target,
        desc="BALL VALVE 2 IN CS 150# RF TRIM 316SS",
        cat="GASKET", valve_type="BALL", size="DN50"
    )

    # Run hybrid candidate generation with category_filter=False to test union
    hybrid_cands, _ = generate_hybrid_candidates(
        db=db,
        source=src,
        top_k=10,
        min_similarity=0.40,
        category_filter=False,
        candidate_cpse_id=cpse_target.id,
    )

    cand_ids = [c.candidate_id for c in hybrid_cands]

    # 1. Baseline candidates preserved
    assert cand_both.id in cand_ids
    assert cand_base.id in cand_ids

    # 2. AI-only candidate added
    assert cand_ai.id in cand_ids

    # 3. Provenance tracking
    cand_ai_hybrid = next(c for c in hybrid_cands if c.candidate_id == cand_ai.id)
    assert cand_ai_hybrid.origin == "AI_ONLY"
    assert cand_ai_hybrid.is_in_baseline is False
    assert cand_ai_hybrid.is_in_ai is True


def test_hybrid_candidate_deduplication(db, cpse_source, cpse_target):
    src = create_material(db, cpse_source, "GATE VALVE DN100 CS CLASS150", valve_type="GATE")
    cand = create_material(db, cpse_target, "GATE VALVE DN100 CS CLASS150", valve_type="GATE")

    hybrid_cands, _ = generate_hybrid_candidates(
        db=db,
        source=src,
        top_k=10,
        min_similarity=0.50,
        candidate_cpse_id=cpse_target.id,
    )

    # Candidate matches both baseline SQL and AI embeddings
    matching_cands = [c for c in hybrid_cands if c.candidate_id == cand.id]
    assert len(matching_cands) == 1, "Duplicate candidates must be deduplicated in hybrid union"
    assert matching_cands[0].origin == "BOTH"


def test_same_cpse_and_self_exclusion_in_hybrid(db, cpse_source, cpse_target):
    src = create_material(db, cpse_source, "NEEDLE VALVE 1/2 IN SS316 6000PSI NPT", valve_type="NEEDLE")
    same_cpse = create_material(db, cpse_source, "NEEDLE VALVE 1/2 IN SS316 6000PSI NPT", valve_type="NEEDLE")
    other_cpse = create_material(db, cpse_target, "NEEDLE VALVE 1/2 IN SS316 6000PSI NPT", valve_type="NEEDLE")

    hybrid_cands, _ = generate_hybrid_candidates(
        db=db,
        source=src,
        top_k=10,
        min_similarity=0.20,
    )
    cand_ids = [c.candidate_id for c in hybrid_cands]

    assert src.id not in cand_ids, "Self-matching must be strictly excluded from hybrid union"
    assert same_cpse.id not in cand_ids, "Same-CPSE candidate must be strictly excluded from hybrid union"
    assert other_cpse.id in cand_ids, "Valid cross-CPSE candidate must be included"


def test_hybrid_and_shadow_does_not_mutate_database(db, cpse_source, cpse_target):
    src = create_material(db, cpse_source, "CHECK VALVE DN50 CS CLASS150", valve_type="CHECK")
    cand = create_material(db, cpse_target, "CHECK VALVE DN50 CS CLASS150", valve_type="CHECK")

    recs_before = db.query(MatchRecommendation).count()
    maps_before = db.query(MaterialNationalMapping).count()

    # 1. Run hybrid generation
    generate_hybrid_candidates(db, src, top_k=5, candidate_cpse_id=cpse_target.id)
    # 2. Run shadow matching analysis
    report = run_shadow_matching_analysis(db, src, top_k=5, candidate_cpse_id=cpse_target.id)

    assert report.hybrid_candidate_count >= 1

    recs_after = db.query(MatchRecommendation).count()
    maps_after = db.query(MaterialNationalMapping).count()

    assert recs_before == recs_after, "Shadow matching must NEVER write MatchRecommendation rows"
    assert maps_before == maps_after, "Shadow matching must NEVER write MaterialNationalMapping rows"


def test_hard_engineering_conflicts_rejected_in_shadow(db, cpse_source, cpse_target):
    src = create_material(
        db, cpse_source,
        desc="BALL VALVE DN50 CS CLASS150 RF",
        valve_type="BALL", size="DN50", body_material="CARBON_STEEL",
        pressure_class="CLASS150", connection_type="RF"
    )

    # Candidate with hard size conflict (DN100 / 4 IN)
    cand_hard_neg = create_material(
        db, cpse_target,
        desc="BALL VALVE DN100 CS CLASS150 RF",
        valve_type="BALL", size="DN100", body_material="CARBON_STEEL",
        pressure_class="CLASS150", connection_type="RF"
    )

    report = run_shadow_matching_analysis(db, src, top_k=5, min_similarity=0.40, candidate_cpse_id=cpse_target.id)
    hn_shadow = next((r for r in report.hybrid_recommendations if r.candidate_id == cand_hard_neg.id), None)

    assert hn_shadow is not None
    # Must NOT be SAME
    assert hn_shadow.classification != "SAME"
    assert hn_shadow.classification == "DIFFERENT"
    assert any("size conflict" in c.lower() for c in hn_shadow.hard_conflicts)


def test_production_recommendation_behavior_unchanged(db, cpse_source, cpse_target):
    src = create_material(db, cpse_source, "GLOBE VALVE DN50 CS CLASS150", valve_type="GLOBE")
    cand = create_material(db, cpse_target, "GLOBE VALVE DN50 CS CLASS150", valve_type="GLOBE")

    # Call production create_match_recommendations
    recs = create_match_recommendations(db, src)
    db.commit()

    # Verify baseline production recommendation persisted
    assert len(recs) >= 1
    assert any(r.candidate_material_id == cand.id for r in recs)

    # Calling shadow analysis does not disrupt or duplicate persisted recommendations
    report = run_shadow_matching_analysis(db, src, top_k=5, candidate_cpse_id=cpse_target.id)
    assert report.baseline_candidate_count >= 1

    count_in_db = db.query(MatchRecommendation).filter(MatchRecommendation.source_material_id == src.id).count()
    assert count_in_db == len(recs), "Shadow analysis must not alter persisted recommendation counts"


def test_shadow_match_api_endpoint(db, cpse_source, cpse_target):
    client = TestClient(app)
    src = create_material(db, cpse_source, "BUTTERFLY VALVE DN100 CS CLASS150", valve_type="BUTTERFLY")
    cand = create_material(db, cpse_target, "BUTTERFLY VALVE DN100 CS CLASS150", valve_type="BUTTERFLY")

    resp = client.get(f"/api/v1/materials/{src.id}/shadow-match?top_k=5&min_similarity=0.4")
    assert resp.status_code == 200
    body = resp.json()

    assert body["status"] == "success"
    assert body["source_material_id"] == str(src.id)
    assert "baseline_candidate_count" in body
    assert "hybrid_candidate_count" in body
    assert "baseline_distribution" in body
    assert "hybrid_distribution" in body
    assert "delta_distribution" in body
    assert "latencies_ms" in body

