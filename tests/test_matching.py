import pytest
import uuid
from fastapi.testclient import TestClient

from app.models import CPSE, Material, MatchRecommendation
from app.services.matching import classify_match, create_match_recommendations, generate_candidates

@pytest.fixture
def cpse_a(db):
    c = CPSE(code=f"CPSE-A-{uuid.uuid4()}", name="A")
    db.add(c)
    db.commit()
    db.refresh(c)
    return c

@pytest.fixture
def cpse_b(db):
    c = CPSE(code=f"CPSE-B-{uuid.uuid4()}", name="B")
    db.add(c)
    db.commit()
    db.refresh(c)
    return c

def create_mat(db, cpse, attrs: dict) -> Material:
    mat = Material(
        id=uuid.uuid4(),
        cpse_id=cpse.id,
        source_material_code=f"M-{uuid.uuid4()}",
        source_description=attrs.get("desc", "TEST VALVE"),
        source_uom="EA",
        category="VALVE",
        normalized_description=attrs.get("norm_desc", attrs.get("desc", "TEST VALVE")),
        valve_type=attrs.get("valve_type"),
        size=attrs.get("size"),
        body_material=attrs.get("body_material"),
        pressure_class=attrs.get("pressure_class"),
        connection_type=attrs.get("connection_type"),
        trim=attrs.get("trim")
    )
    db.add(mat)
    db.commit()
    db.refresh(mat)
    return mat

def test_exact_equivalent(db, cpse_a, cpse_b):
    attrs = {
        "desc": "BALL VALVE DN50",
        "valve_type": "BALL", "size": "DN50", "body_material": "CARBON_STEEL",
        "pressure_class": "CLASS150", "connection_type": "RF", "trim": "SS304"
    }
    m1 = create_mat(db, cpse_a, attrs)
    m2 = create_mat(db, cpse_b, attrs)

    result = classify_match(m1, m2)
    assert result["classification"] == "SAME"
    assert result["confidence"] >= 0.90
    assert "Same valve type, size, body material, pressure class, connection type and trim" in result["explanation"]

def test_description_formatting_diff_same_attributes(db, cpse_a, cpse_b):
    attrs1 = {
        "desc": "BALL VALVE DN50 CS CL150 RF SS304",
        "norm_desc": "BALL VALVE DN50 CS CL150 RF SS304",
        "valve_type": "BALL", "size": "DN50", "body_material": "CARBON_STEEL",
        "pressure_class": "CLASS150", "connection_type": "RF", "trim": "SS304"
    }
    attrs2 = attrs1.copy()
    attrs2["desc"] = "VALVE, BALL, DN50, C.S., 150#, R.F., 304SS"
    attrs2["norm_desc"] = "VALVE BALL DN50 CS 150 RF 304SS" # similar but not exact

    m1 = create_mat(db, cpse_a, attrs1)
    m2 = create_mat(db, cpse_b, attrs2)

    result = classify_match(m1, m2)
    assert result["classification"] == "SAME"
    assert "Same valve type, size, body material, pressure class, connection type and trim" in result["explanation"]

def test_hard_conflicts(db, cpse_a, cpse_b):
    base = {
        "valve_type": "BALL", "size": "DN50", "body_material": "CARBON_STEEL",
        "pressure_class": "CLASS150", "connection_type": "RF", "trim": "SS304"
    }
    m1 = create_mat(db, cpse_a, base)

    # 3. CLASS150 vs CLASS300
    c3 = base.copy(); c3["pressure_class"] = "CLASS300"
    m_c3 = create_mat(db, cpse_b, c3)
    assert classify_match(m1, m_c3)["classification"] == "DIFFERENT"
    assert "pressure class conflict" in classify_match(m1, m_c3)["explanation"].lower()

    # 4. DN50 vs DN100
    c4 = base.copy(); c4["size"] = "DN100"
    m_c4 = create_mat(db, cpse_b, c4)
    assert classify_match(m1, m_c4)["classification"] == "DIFFERENT"

    # 5. BALL vs GATE
    c5 = base.copy(); c5["valve_type"] = "GATE"
    m_c5 = create_mat(db, cpse_b, c5)
    assert classify_match(m1, m_c5)["classification"] == "DIFFERENT"

    # 6. RF vs SOCKET_WELD
    c6 = base.copy(); c6["connection_type"] = "SOCKET_WELD"
    m_c6 = create_mat(db, cpse_b, c6)
    assert classify_match(m1, m_c6)["classification"] == "DIFFERENT"

def test_missing_trim_regression(db, cpse_a, cpse_b):
    # Regression test specified in prompt
    a_attrs = {
        "desc": "BALL / DN50 / CARBON_STEEL / CLASS300 / RF / NULL",
        "valve_type": "BALL", "size": "DN50", "body_material": "CARBON_STEEL",
        "pressure_class": "CLASS300", "connection_type": "RF", "trim": None
    }
    b_attrs = {
        "desc": "BALL / DN50 / CARBON_STEEL / CLASS300 / RF / SS304",
        "valve_type": "BALL", "size": "DN50", "body_material": "CARBON_STEEL",
        "pressure_class": "CLASS300", "connection_type": "RF", "trim": "SS304"
    }
    m_a = create_mat(db, cpse_a, a_attrs)
    m_b = create_mat(db, cpse_b, b_attrs)

    result = classify_match(m_a, m_b)
    # 7. Same known attributes but missing trim -> not automatic SAME
    # 8. NULL never acts as wildcard
    assert result["classification"] != "SAME"
    assert result["classification"] == "POTENTIALLY_EQUIVALENT"
    assert "missing information for trim" in result["explanation"].lower()


def test_missing_both_sides_regression(db, cpse_a, cpse_b):
    # Regression test specified in prompt:
    # identical descriptions, five attributes match, trim missing on BOTH sides.
    # Result must NOT be SAME.
    attrs = {
        "desc": "BALL VALVE DN50 CS CLASS300 RF",
        "valve_type": "BALL", "size": "DN50", "body_material": "CARBON_STEEL",
        "pressure_class": "CLASS300", "connection_type": "RF", "trim": None
    }
    m_a = create_mat(db, cpse_a, attrs)
    m_b = create_mat(db, cpse_b, attrs)

    result = classify_match(m_a, m_b)
    assert result["classification"] != "SAME"
    assert result["classification"] == "POTENTIALLY_EQUIVALENT"

def test_weak_and_intermediate_similarity(db, cpse_a, cpse_b):
    # Weak
    m1 = create_mat(db, cpse_a, {"desc": "BALL VALVE DN50", "valve_type": "BALL", "size": "DN50"})
    m2 = create_mat(db, cpse_b, {"desc": "COMPLETELY DIFFERENT THING", "valve_type": "GATE"})
    res_weak = classify_match(m1, m2)
    assert res_weak["classification"] == "DIFFERENT" # 9. Weak similarity -> DIFFERENT

    # Intermediate (some missing, similar desc)
    m3 = create_mat(db, cpse_b, {"desc": "BALL VALVE 50MM", "valve_type": "BALL", "size": "DN50"})
    res_inter = classify_match(m1, m3)
    assert res_inter["classification"] == "POTENTIALLY_EQUIVALENT" # 10. Intermediate -> POTENTIAL

def test_confidence_and_evidence_storage(db, cpse_a, cpse_b):
    m1 = create_mat(db, cpse_a, {"valve_type": "BALL", "size": "DN50"})
    m2 = create_mat(db, cpse_b, {"valve_type": "BALL", "size": "DN50"})

    res = classify_match(m1, m2)
    assert 0.0 <= res["confidence"] <= 1.0 # 11. Confidence 0..1
    assert "valve_type" in res["evidence"]["attributes"] # 12. Evidence is stored
    assert "explanation" in res # 13. Explanation stored

def test_material_cannot_match_itself(db, cpse_a):
    m1 = create_mat(db, cpse_a, {"valve_type": "BALL"})

    recs = create_match_recommendations(db, m1)
    assert not any(r.candidate_material_id == m1.id for r in recs) # 14. Cannot match itself

def test_multiple_recommendations_allowed(db, cpse_a, cpse_b):
    m1 = create_mat(db, cpse_a, {"valve_type": "BALL"})
    m2 = create_mat(db, cpse_b, {"valve_type": "BALL"})

    # Manually create two recommendations for same pair
    rec1 = MatchRecommendation(
        source_material_id=m1.id, candidate_material_id=m2.id,
        classification="POTENTIALLY_EQUIVALENT"
    )
    rec2 = MatchRecommendation(
        source_material_id=m1.id, candidate_material_id=m2.id,
        classification="SAME"
    )
    db.add_all([rec1, rec2])
    db.commit() # 15. Multiple recommendations allowed (no UniqueConstraint exception)

def test_recommendation_persistence(db, cpse_a, cpse_b):
    m1 = create_mat(db, cpse_a, {"valve_type": "BALL", "size": "DN50"})
    m2 = create_mat(db, cpse_b, {"valve_type": "BALL", "size": "DN50"})

    recs = create_match_recommendations(db, m1)
    db.commit()
    assert any(r.candidate_material_id == m2.id for r in recs)

    saved = db.query(MatchRecommendation).filter_by(source_material_id=m1.id, candidate_material_id=m2.id).first()
    assert saved is not None
    assert saved.classification == "POTENTIALLY_EQUIVALENT" # 16. Persistence works

def test_hard_conflict_overrides_text_similarity(db, cpse_a, cpse_b):
    # Almost identical text, but hard conflicting size
    m1 = create_mat(db, cpse_a, {"desc": "VALVE 12345", "size": "DN50"})
    m2 = create_mat(db, cpse_b, {"desc": "VALVE 12345", "size": "DN100"})

    res = classify_match(m1, m2)
    assert res["classification"] == "DIFFERENT" # 17. Hard conflict overrides
    assert res["confidence"] == 0.0

def test_api_endpoint(client: TestClient, db, cpse_a, cpse_b):
    m1 = create_mat(db, cpse_a, {"valve_type": "BALL"})
    m2 = create_mat(db, cpse_b, {"valve_type": "BALL"})

    resp = client.post(f"/api/v1/materials/{m1.id}/match")
    assert resp.status_code == 200
    data = resp.json()
    assert data["candidate_count"] > 0
    assert data["recommendations_created"] > 0
    assert any(r["candidate_id"] == str(m2.id) for r in data["recommendations"])

def test_same_cpse_and_self_candidate_exclusion(db, cpse_a, cpse_b):
    # Material in CPSE A (source)
    m_src = create_mat(db, cpse_a, {"desc": "GATE VALVE DN50 CS CLASS150 RF SS316", "valve_type": "GATE", "size": "DN50"})
    # Material in CPSE A (same CPSE candidate)
    m_same_cpse = create_mat(db, cpse_a, {"desc": "GATE VALVE DN50 CS CLASS150 RF SS316", "valve_type": "GATE", "size": "DN50"})
    # Material in CPSE B (different CPSE candidate)
    m_other_cpse = create_mat(db, cpse_b, {"desc": "GATE VALVE DN50 CS CLASS150 RF SS316", "valve_type": "GATE", "size": "DN50"})

    # Check generate_candidates output directly
    candidates = generate_candidates(db, m_src)
    cand_ids = [c.id for c in candidates]

    assert m_src.id not in cand_ids, "Source material itself must be excluded from candidates"
    assert m_same_cpse.id not in cand_ids, "Candidate from same CPSE must be excluded from candidates"
    assert m_other_cpse.id in cand_ids, "Valid candidate from another CPSE must be included"

    # Check create_match_recommendations output
    recs = create_match_recommendations(db, m_src)
    rec_cand_ids = [r.candidate_material_id for r in recs]

    assert m_src.id not in rec_cand_ids, "Source material itself must never be recommended"
    assert m_same_cpse.id not in rec_cand_ids, "Material from same CPSE must never be recommended"
    assert m_other_cpse.id in rec_cand_ids, "Material from another CPSE must be recommended"
