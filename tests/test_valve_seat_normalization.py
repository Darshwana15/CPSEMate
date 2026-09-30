import uuid
import pytest
from app.models import CPSE, Material
from app.services.normalization import (
    normalize_material_record,
    extract_seat_material,
    normalize_seat_material,
)
from app.services.matching import classify_match
from app.services.ai.validation import EngineeringKnowledgeEngine
from app.services.ai.profile import MaterialProfile, ProfileAttribute
from app.services.ai.explainability import MaterialExplanationService


@pytest.fixture
def test_cpse(db):
    cpse = CPSE(code=f"CPSE-SEAT-{uuid.uuid4().hex[:8]}", name="Test SEAT CPSE")
    db.add(cpse)
    db.commit()
    db.refresh(cpse)
    return cpse


def create_raw_material(db, cpse, desc: str, specs: str = None, uom: str = "EA") -> Material:
    mat = Material(
        id=uuid.uuid4(),
        cpse_id=cpse.id,
        source_material_code=f"M-{uuid.uuid4().hex[:8]}",
        source_description=desc,
        source_uom=uom,
        source_specifications=specs,
        category="VALVE",
        raw_source_data={"original": desc},
    )
    db.add(mat)
    db.commit()
    db.refresh(mat)
    return mat


def test_seat_material_normalization_helpers():
    assert normalize_seat_material("EPDM") == "EPDM"
    assert normalize_seat_material("TEFLON") == "PTFE"
    assert normalize_seat_material("PTFE") == "PTFE"
    assert normalize_seat_material("BUNA-N") == "NBR"
    assert normalize_seat_material("BUNA") == "NBR"
    assert normalize_seat_material("NBR") == "NBR"
    assert normalize_seat_material("VITON") == "VITON"
    assert normalize_seat_material("FKM") == "VITON"
    assert normalize_seat_material("NEOPRENE") == "NEOPRENE"


def test_extract_seat_material():
    # Explicit SEAT keyword
    assert extract_seat_material("BALL VALVE 2 IN CS PTFE SEAT") == "PTFE"
    assert extract_seat_material("GATE VALVE 4 IN CS SS316 TRIM TEFLON SEAT") == "PTFE"
    assert extract_seat_material("PLUG VALVE 3 IN CS EPDM SLEEVE") == "EPDM"
    assert extract_seat_material("BUTTERFLY VALVE 6 IN CI BUNA-N LINER") == "NBR"

    # Soft seat material on butterfly valve without explicit SEAT keyword
    assert extract_seat_material("BUTTERFLY VALVE 6 IN CAST IRON WAFER EPDM", valve_type="BUTTERFLY") == "EPDM"
    assert extract_seat_material("BUTTERFLY VALVE 6 IN CAST IRON WAFER PTFE", valve_type="BUTTERFLY") == "PTFE"
    assert extract_seat_material("BUTTERFLY VALVE 6 IN CAST IRON WAFER TEFLON", valve_type="BUTTERFLY") == "PTFE"
    assert extract_seat_material("BUTTERFLY VALVE 6 IN CAST IRON WAFER VITON", valve_type="BUTTERFLY") == "VITON"
    assert extract_seat_material("BUTTERFLY VALVE 6 IN CAST IRON WAFER", valve_type="BUTTERFLY") is None

    # Do not extract elastomer as seat on non-butterfly without explicit keyword
    assert extract_seat_material("BALL VALVE 2 IN CS SS316 TRIM", valve_type="BALL") is None


def test_explicit_trim_not_converted_to_seat(db, test_cpse):
    """Ball valve with SS316 trim should preserve trim=SS316 and seat_material=None."""
    mat = create_raw_material(db, test_cpse, "BALL VALVE 2 IN CLASS 150 FLANGED CS SS316 TRIM")
    normalize_material_record(db, mat)
    assert mat.category == "VALVE"
    assert mat.valve_type == "BALL"
    assert mat.body_material == "CARBON_STEEL"
    assert mat.trim == "SS316"
    assert mat.normalized_attributes.get("trim") == "SS316"
    assert mat.normalized_attributes.get("seat_material") is None


def test_butterfly_valve_epdm_seat(db, test_cpse):
    """Butterfly valve with EPDM should have seat_material=EPDM and trim=None."""
    mat = create_raw_material(db, test_cpse, "BUTTERFLY VALVE 6 IN CAST IRON WAFER EPDM")
    normalize_material_record(db, mat)
    assert mat.category == "VALVE"
    assert mat.valve_type == "BUTTERFLY"
    assert mat.body_material == "CAST_IRON"
    assert mat.connection_type == "WAFER"
    assert mat.trim is None
    assert mat.normalized_attributes.get("trim") is None
    assert mat.normalized_attributes.get("seat_material") == "EPDM"


def test_butterfly_valve_ptfe_and_teflon_seat(db, test_cpse):
    """Butterfly valve with PTFE or TEFLON should normalize seat_material to PTFE."""
    mat_ptfe = create_raw_material(db, test_cpse, "BUTTERFLY VALVE 6 IN CAST IRON WAFER PTFE")
    normalize_material_record(db, mat_ptfe)
    assert mat_ptfe.normalized_attributes.get("seat_material") == "PTFE"
    assert mat_ptfe.trim is None

    mat_teflon = create_raw_material(db, test_cpse, "BUTTERFLY VALVE 6 IN CAST IRON WAFER TEFLON")
    normalize_material_record(db, mat_teflon)
    assert mat_teflon.normalized_attributes.get("seat_material") == "PTFE"
    assert mat_teflon.trim is None


def test_butterfly_valve_missing_seat(db, test_cpse):
    """Butterfly valve without seat specified should have seat_material=None."""
    mat = create_raw_material(db, test_cpse, "BUTTERFLY VALVE 6 IN CAST IRON WAFER")
    normalize_material_record(db, mat)
    assert mat.category == "VALVE"
    assert mat.valve_type == "BUTTERFLY"
    assert mat.body_material == "CAST_IRON"
    assert mat.connection_type == "WAFER"
    assert mat.normalized_attributes.get("seat_material") is None


def test_explicit_seat_and_trim_coexist(db, test_cpse):
    """A valve specifying both TRIM and SEAT should extract both independently."""
    mat = create_raw_material(db, test_cpse, "GATE VALVE 4 IN CLASS 150 FLANGED CS SS316 TRIM PTFE SEAT")
    normalize_material_record(db, mat)
    assert mat.category == "VALVE"
    assert mat.trim == "SS316"
    assert mat.normalized_attributes.get("trim") == "SS316"
    assert mat.normalized_attributes.get("seat_material") == "PTFE"


def test_seat_material_matching_conflict_different():
    """Butterfly valve EPDM vs NBR seat material must produce hard conflict DIFFERENT with 0.0 confidence."""
    m_src = Material(
        id=uuid.uuid4(),
        cpse_id=uuid.uuid4(),
        source_material_code="SRC-BF-EPDM",
        source_description="BUTTERFLY VALVE 6 IN CAST IRON WAFER EPDM",
        normalized_description="VALVE BUTTERFLY DN150 CAST_IRON WAFER",
        category="VALVE",
        valve_type="BUTTERFLY",
        size="DN150",
        pressure_class=None,
        body_material="CAST_IRON",
        connection_type="WAFER",
        trim=None,
        normalized_attributes={
            "category": "VALVE",
            "valve_type": "BUTTERFLY",
            "size": "DN150",
            "body_material": "CAST_IRON",
            "connection_type": "WAFER",
            "seat_material": "EPDM"
        }
    )

    m_cand = Material(
        id=uuid.uuid4(),
        cpse_id=uuid.uuid4(),
        source_material_code="CAND-BF-NBR",
        source_description="BUTTERFLY VALVE 6 IN CAST IRON WAFER NBR",
        normalized_description="VALVE BUTTERFLY DN150 CAST_IRON WAFER",
        category="VALVE",
        valve_type="BUTTERFLY",
        size="DN150",
        pressure_class=None,
        body_material="CAST_IRON",
        connection_type="WAFER",
        trim=None,
        normalized_attributes={
            "category": "VALVE",
            "valve_type": "BUTTERFLY",
            "size": "DN150",
            "body_material": "CAST_IRON",
            "connection_type": "WAFER",
            "seat_material": "NBR"
        }
    )

    res = classify_match(m_src, m_cand)
    assert res["classification"] == "DIFFERENT"
    assert res["confidence"] == 0.0
    assert "seat material conflict" in res["explanation"].lower()


def test_seat_material_matching_same():
    """Butterfly valve EPDM vs EPDM must match as SAME when other key attributes match."""
    m_src = Material(
        id=uuid.uuid4(),
        cpse_id=uuid.uuid4(),
        source_material_code="SRC-BF-EPDM-1",
        source_description="BUTTERFLY VALVE 6 IN CAST IRON WAFER EPDM",
        normalized_description="VALVE BUTTERFLY DN150 CAST_IRON WAFER",
        category="VALVE",
        valve_type="BUTTERFLY",
        size="DN150",
        pressure_class="CLASS150",
        body_material="CAST_IRON",
        connection_type="WAFER",
        trim=None,
        normalized_attributes={
            "category": "VALVE",
            "valve_type": "BUTTERFLY",
            "size": "DN150",
            "pressure_class": "CLASS150",
            "body_material": "CAST_IRON",
            "connection_type": "WAFER",
            "seat_material": "EPDM"
        }
    )

    m_cand = Material(
        id=uuid.uuid4(),
        cpse_id=uuid.uuid4(),
        source_material_code="CAND-BF-EPDM-2",
        source_description="BUTTERFLY VALVE 6 IN CAST IRON WAFER EPDM",
        normalized_description="VALVE BUTTERFLY DN150 CAST_IRON WAFER",
        category="VALVE",
        valve_type="BUTTERFLY",
        size="DN150",
        pressure_class="CLASS150",
        body_material="CAST_IRON",
        connection_type="WAFER",
        trim=None,
        normalized_attributes={
            "category": "VALVE",
            "valve_type": "BUTTERFLY",
            "size": "DN150",
            "pressure_class": "CLASS150",
            "body_material": "CAST_IRON",
            "connection_type": "WAFER",
            "seat_material": "EPDM"
        }
    )

    res = classify_match(m_src, m_cand)
    assert res["classification"] == "SAME"
    assert res["confidence"] >= 0.9


def test_seat_material_asymmetric_prevents_same():
    """Butterfly valve with EPDM vs Butterfly valve without seat specified should NOT be SAME."""
    m_src = Material(
        id=uuid.uuid4(),
        cpse_id=uuid.uuid4(),
        source_material_code="SRC-BF-EPDM-3",
        source_description="BUTTERFLY VALVE 6 IN CAST IRON WAFER EPDM",
        normalized_description="VALVE BUTTERFLY DN150 CAST_IRON WAFER",
        category="VALVE",
        valve_type="BUTTERFLY",
        size="DN150",
        pressure_class="CLASS150",
        body_material="CAST_IRON",
        connection_type="WAFER",
        trim=None,
        normalized_attributes={
            "category": "VALVE",
            "valve_type": "BUTTERFLY",
            "size": "DN150",
            "pressure_class": "CLASS150",
            "body_material": "CAST_IRON",
            "connection_type": "WAFER",
            "seat_material": "EPDM"
        }
    )

    m_cand = Material(
        id=uuid.uuid4(),
        cpse_id=uuid.uuid4(),
        source_material_code="CAND-BF-NOSEAT",
        source_description="BUTTERFLY VALVE 6 IN CAST IRON WAFER",
        normalized_description="VALVE BUTTERFLY DN150 CAST_IRON WAFER",
        category="VALVE",
        valve_type="BUTTERFLY",
        size="DN150",
        pressure_class="CLASS150",
        body_material="CAST_IRON",
        connection_type="WAFER",
        trim=None,
        normalized_attributes={
            "category": "VALVE",
            "valve_type": "BUTTERFLY",
            "size": "DN150",
            "pressure_class": "CLASS150",
            "body_material": "CAST_IRON",
            "connection_type": "WAFER",
        }
    )

    res = classify_match(m_src, m_cand)
    assert res["classification"] == "POTENTIALLY_EQUIVALENT"


def test_engineering_validation_seat_material():
    eng = EngineeringKnowledgeEngine()

    # Conflict
    p_epdm = MaterialProfile(
        category=ProfileAttribute.known("VALVE"),
        material_type=ProfileAttribute.known("BUTTERFLY"),
        seat_material=ProfileAttribute.known("EPDM"),
    )
    p_nbr = MaterialProfile(
        category=ProfileAttribute.known("VALVE"),
        material_type=ProfileAttribute.known("BUTTERFLY"),
        seat_material=ProfileAttribute.known("NBR"),
    )
    res_diff = eng.validate_profiles(p_epdm, p_nbr)
    assert res_diff.is_compatible is False
    assert any("Seat material conflict: EPDM vs NBR" in c for c in res_diff.hard_conflicts)

    # Match
    p_epdm_2 = MaterialProfile(
        category=ProfileAttribute.known("VALVE"),
        material_type=ProfileAttribute.known("BUTTERFLY"),
        seat_material=ProfileAttribute.known("EPDM"),
    )
    res_same = eng.validate_profiles(p_epdm, p_epdm_2)
    assert "seat_material" in res_same.matching_attributes

    # Asymmetric
    p_no_seat = MaterialProfile(
        category=ProfileAttribute.known("VALVE"),
        material_type=ProfileAttribute.known("BUTTERFLY"),
    )
    res_asym = eng.validate_profiles(p_epdm, p_no_seat)
    assert "seat_material" in res_asym.asymmetric_attributes


def test_material_profile_serialization_roundtrip():
    norm_attrs = {
        "category": "VALVE",
        "valve_type": "BUTTERFLY",
        "size": "DN150",
        "seat_material": "EPDM",
        "liner_material": "EPDM"
    }
    m = Material(
        id=uuid.uuid4(),
        cpse_id=uuid.uuid4(),
        source_material_code="TEST-BF",
        source_description="BUTTERFLY VALVE 6 IN CAST IRON WAFER EPDM",
        normalized_description="VALVE BUTTERFLY DN150 CAST_IRON WAFER",
        normalized_attributes=norm_attrs
    )
    profile = MaterialProfile.from_material(m)
    assert profile.seat_material is not None
    assert profile.seat_material.value == "EPDM"

    p_dict = profile.to_dict()
    assert p_dict["seat_material"]["value"] == "EPDM"

    canon_str = profile.to_canonical_string()
    assert "SEAT EPDM" in canon_str


def test_explainability_seat_material_conflict():
    m_src = Material(
        id=uuid.uuid4(),
        cpse_id=uuid.uuid4(),
        source_material_code="SRC",
        source_description="BUTTERFLY VALVE 6 IN CAST IRON WAFER EPDM",
        normalized_description="VALVE BUTTERFLY DN150 CAST_IRON WAFER",
        category="VALVE",
        valve_type="BUTTERFLY",
        size="DN150",
        body_material="CAST_IRON",
        connection_type="WAFER",
        normalized_attributes={
            "category": "VALVE",
            "valve_type": "BUTTERFLY",
            "size": "DN150",
            "body_material": "CAST_IRON",
            "connection_type": "WAFER",
            "seat_material": "EPDM"
        }
    )
    m_cand = Material(
        id=uuid.uuid4(),
        cpse_id=uuid.uuid4(),
        source_material_code="CAND",
        source_description="BUTTERFLY VALVE 6 IN CAST IRON WAFER NBR",
        normalized_description="VALVE BUTTERFLY DN150 CAST_IRON WAFER",
        category="VALVE",
        valve_type="BUTTERFLY",
        size="DN150",
        body_material="CAST_IRON",
        connection_type="WAFER",
        normalized_attributes={
            "category": "VALVE",
            "valve_type": "BUTTERFLY",
            "size": "DN150",
            "body_material": "CAST_IRON",
            "connection_type": "WAFER",
            "seat_material": "NBR"
        }
    )

    svc = MaterialExplanationService()
    explanation = svc.generate_explanation(
        source=m_src,
        candidate=m_cand,
    )
    assert any(c.attribute == "seat_material" for c in explanation.attribute_comparisons)
    assert any(conf.attribute == "seat_material" or "seat" in conf.reason.lower() for conf in explanation.engineering_conflicts)


def test_full_pipeline_persistence_and_matching(db, test_cpse):
    """
    Verifies that the full application normalization path in sih_test:
    1. Persists normalized_attributes with trim=NULL and seat_material=EPDM into the database.
    2. Correctly extracts valve_type, size, body_material, connection_type for A-107, A-108, B-206, and C-309.
    3. Re-queries persisted rows from PostgreSQL to guarantee storage fidelity.
    4. Evaluates matching:
       - Identical EPDM resilient valves match as SAME.
       - Conflicting seat materials (EPDM vs NBR) produce DIFFERENT with 0.0 confidence.
       - Missing seat material (EPDM vs NULL) produces POTENTIALLY_EQUIVALENT without wildcard treatment.
    """
    mat_a107 = create_raw_material(db, test_cpse, "BUTTERFLY VALVE 6 IN CAST IRON WAFER EPDM")
    mat_a108 = create_raw_material(db, test_cpse, "BUTTERFLY VALVE 8 IN CAST IRON WAFER EPDM")
    mat_b206 = create_raw_material(db, test_cpse, "B/F VALVE 150MM CI WAFER TYPE EPDM SEAT")
    mat_c309 = create_raw_material(db, test_cpse, 'BUTTERFLY VLV 6" C.I. WAFER EPDM')

    for m in [mat_a107, mat_a108, mat_b206, mat_c309]:
        normalize_material_record(db, m)

    db.commit()

    # Re-query from DB to verify persistence in PostgreSQL
    saved_a107 = db.query(Material).filter(Material.id == mat_a107.id).first()
    saved_a108 = db.query(Material).filter(Material.id == mat_a108.id).first()
    saved_b206 = db.query(Material).filter(Material.id == mat_b206.id).first()
    saved_c309 = db.query(Material).filter(Material.id == mat_c309.id).first()

    # A-107
    assert saved_a107.normalized_attributes.get("trim") is None
    assert saved_a107.normalized_attributes.get("seat_material") == "EPDM"
    assert saved_a107.valve_type == "BUTTERFLY"
    assert saved_a107.body_material == "CAST_IRON"
    assert saved_a107.size == "DN150"
    assert saved_a107.connection_type == "WAFER"

    # A-108
    assert saved_a108.normalized_attributes.get("trim") is None
    assert saved_a108.normalized_attributes.get("seat_material") == "EPDM"
    assert saved_a108.valve_type == "BUTTERFLY"
    assert saved_a108.body_material == "CAST_IRON"
    assert saved_a108.size == "DN200"
    assert saved_a108.connection_type == "WAFER"

    # B-206
    assert saved_b206.normalized_attributes.get("trim") is None
    assert saved_b206.normalized_attributes.get("seat_material") == "EPDM"
    assert saved_b206.valve_type == "BUTTERFLY"
    assert saved_b206.body_material == "CAST_IRON"
    assert saved_b206.size == "DN150"
    assert saved_b206.connection_type == "WAFER"

    # C-309
    assert saved_c309.normalized_attributes.get("trim") is None
    assert saved_c309.normalized_attributes.get("seat_material") == "EPDM"
    assert saved_c309.valve_type == "BUTTERFLY"
    assert saved_c309.body_material == "CAST_IRON"
    assert saved_c309.size == "DN150"
    assert saved_c309.connection_type == "WAFER"

    # Matching: identical EPDM resilient valves eligible for SAME when all hard engineering attributes agree
    mat_full_src = create_raw_material(db, test_cpse, "BUTTERFLY VALVE 6 IN CLASS 150 CAST IRON WAFER EPDM")
    mat_full_cand = create_raw_material(db, test_cpse, "BUTTERFLY VALVE DN150 150# CI WAFER EPDM")
    normalize_material_record(db, mat_full_src)
    normalize_material_record(db, mat_full_cand)
    db.commit()
    res_full_same = classify_match(mat_full_src, mat_full_cand)
    assert res_full_same["classification"] == "SAME"
    assert res_full_same["confidence"] >= 0.90

    # Matching: A-107 vs B-206 (both missing pressure_class -> POTENTIALLY_EQUIVALENT)
    res_a107_b206 = classify_match(saved_a107, saved_b206)
    assert res_a107_b206["classification"] == "POTENTIALLY_EQUIVALENT"

    # Matching: A-107 vs C-309 (both missing pressure_class -> POTENTIALLY_EQUIVALENT)
    res_a107_c309 = classify_match(saved_a107, saved_c309)
    assert res_a107_c309["classification"] == "POTENTIALLY_EQUIVALENT"

    # Matching: A-107 vs A-108 (Size conflict: DN150 vs DN200)
    res_a107_a108 = classify_match(saved_a107, saved_a108)
    assert res_a107_a108["classification"] == "DIFFERENT"
    assert res_a107_a108["confidence"] == 0.0

    # Matching: EPDM vs NBR conflict
    mat_nbr = create_raw_material(db, test_cpse, "BUTTERFLY VALVE 6 IN CAST IRON WAFER NBR")
    normalize_material_record(db, mat_nbr)
    db.commit()
    res_epdm_nbr = classify_match(saved_a107, mat_nbr)
    assert res_epdm_nbr["classification"] == "DIFFERENT"
    assert res_epdm_nbr["confidence"] == 0.0
    assert "seat material conflict" in res_epdm_nbr["explanation"].lower()

    # Matching: EPDM vs NULL (no wildcard)
    mat_no_seat = create_raw_material(db, test_cpse, "BUTTERFLY VALVE 6 IN CAST IRON WAFER")
    normalize_material_record(db, mat_no_seat)
    db.commit()
    res_epdm_none = classify_match(saved_a107, mat_no_seat)
    assert res_epdm_none["classification"] == "POTENTIALLY_EQUIVALENT"
    assert res_epdm_none["classification"] != "SAME"
