import uuid
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models import CPSE, Material, MatchRecommendation, MaterialNationalMapping
from app.services.ai.extraction import (
    PatternMaterialExtractor,
    compare_material_profiles,
)
from app.services.ai.extraction_benchmark import (
    EXTRACTION_BENCHMARK_CASES,
    run_extraction_benchmark,
)
from app.services.ai.profile import AttributeState, ProfileAttribute


@pytest.fixture
def extractor():
    return PatternMaterialExtractor()


@pytest.fixture
def cpse(db):
    code = f"CPSE-EXTRACT-{uuid.uuid4().hex[:6]}"
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
        source_material_code=f"MAT-EXT-{uuid.uuid4().hex[:6]}",
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


def test_normal_industrial_description(extractor):
    text = "GATE VALVE DN50 CS CLASS150 RF"
    profile = extractor.extract(text)

    assert profile.category.is_known
    assert profile.category.value == "VALVE"
    assert profile.material_type.is_known
    assert profile.material_type.value == "GATE"
    assert profile.size.is_known
    assert profile.size.value == "DN50"
    assert profile.material_grade.is_known
    assert profile.material_grade.value == "CARBON_STEEL"
    assert profile.pressure_rating.is_known
    assert profile.pressure_rating.value == "CLASS150"
    assert profile.connection_type.is_known
    assert profile.connection_type.value == "RF"
    assert profile.extraction_confidence >= 0.85


def test_reordered_description(extractor):
    # Attributes listed in reverse order
    text = "RF CLASS150 CS DN50 GATE VALVE"
    profile = extractor.extract(text)

    assert profile.material_type.value == "GATE"
    assert profile.size.value == "DN50"
    assert profile.material_grade.value == "CARBON_STEEL"
    assert profile.pressure_rating.value == "CLASS150"
    assert profile.connection_type.value == "RF"


def test_abbreviations_and_fractions(extractor):
    text = "VLV, NDL, 1/2\", 6000#, NPT, SS 316"
    profile = extractor.extract(text)

    assert profile.material_type.value == "NEEDLE"
    assert profile.size.value == "DN15"
    assert profile.pressure_rating.value == "6000PSI"
    assert profile.connection_type.value == "NPT"
    assert profile.material_grade.value == "SS316"


def test_unit_variation(extractor):
    # 25 MM -> DN25, 800 LBS -> CLASS800, SW -> SOCKET_WELD
    text = "FORGED STEEL GATE VALVE 25 MM 800 LBS SOCKET WELD A105"
    profile = extractor.extract(text)

    assert profile.size.value == "DN25"
    assert profile.pressure_rating.value == "CLASS800"
    assert profile.connection_type.value == "SOCKET_WELD"
    assert profile.material_grade.value == "CARBON_STEEL"


def test_missing_attributes_remain_not_present(extractor):
    # Description lacks pressure, body metallurgy, and connection
    text = "BALL VALVE 2 IN"
    profile = extractor.extract(text)

    assert profile.category.value == "VALVE"
    assert profile.material_type.value == "BALL"
    assert profile.size.value == "DN50"

    # Crucial: Unstated attributes MUST NOT be guessed into KNOWN_VALUE
    assert profile.pressure_rating.state == AttributeState.NOT_PRESENT
    assert profile.pressure_rating.value is None
    assert profile.material_grade.state == AttributeState.NOT_PRESENT
    assert profile.material_grade.value is None
    assert profile.connection_type.state == AttributeState.NOT_PRESENT
    assert profile.connection_type.value is None
    assert profile.trim_material.state == AttributeState.NOT_PRESENT
    assert profile.trim_material.value is None


def test_explicit_unknown_vs_not_present(extractor):
    text = "GATE VALVE DN50 PRESSURE: UNKNOWN RF"
    profile = extractor.extract(text)

    # Pressure was explicitly stated as unknown
    assert profile.pressure_rating.state == AttributeState.UNKNOWN
    assert profile.pressure_rating.value is None
    assert profile.pressure_rating.raw_token == "PRESSURE: UNKNOWN"

    # Material was completely omitted
    assert profile.material_grade.state == AttributeState.NOT_PRESENT
    assert profile.material_grade.value is None


def test_conflicting_attributes_detection(extractor):
    # Description contains two contradictory body materials
    text_conflict_mat = "GATE VALVE 2 IN CS BODY ... SS316 BODY CLASS150 RF"
    profile_mat = extractor.extract(text_conflict_mat)
    assert profile_mat.material_grade.state == AttributeState.CONFLICTING
    assert profile_mat.material_grade.value is None

    # Description contains two contradictory sizes
    text_conflict_size = "BALL VALVE 2 IN ... 4 IN CS 150# RF"
    profile_size = extractor.extract(text_conflict_size)
    assert profile_size.size.state == AttributeState.CONFLICTING
    assert profile_size.size.value is None


def test_ai_vs_deterministic_comparison(db, cpse, extractor):
    # Deterministic normalized material with known fields
    mat = create_material(
        db, cpse,
        desc="GATE VALVE 2 IN CS 150# RF",
        category="VALVE",
        valve_type="GATE",
        size="DN50",
        body_material="CARBON_STEEL",
        pressure_class="CLASS150",
        connection_type="RF",
    )

    # Extract AI profile
    ai_profile = extractor.extract(mat.source_description)
    report = compare_material_profiles(mat, ai_profile)

    assert report.agreement_score >= 0.80
    assert "category" in report.agreed_attributes
    assert "valve_type" in report.agreed_attributes
    assert "size" in report.agreed_attributes
    assert "body_material" in report.agreed_attributes
    assert "pressure_class" in report.agreed_attributes
    assert "connection_type" in report.agreed_attributes
    assert len(report.disagreed_attributes) == 0


def test_ai_extraction_does_not_mutate_material(db, cpse, extractor):
    mat = create_material(
        db, cpse,
        desc="CHECK VALVE DN50 CS CLASS150",
        valve_type="CHECK",
        size="DN50",
    )

    old_desc = mat.source_description
    old_size = mat.size
    old_valve_type = mat.valve_type
    recs_before = db.query(MatchRecommendation).count()
    maps_before = db.query(MaterialNationalMapping).count()

    # Run AI extraction & comparison
    profile = extractor.extract(mat.source_description)
    report = compare_material_profiles(mat, profile)

    db.refresh(mat)

    # Invariants: Zero mutation of database records
    assert mat.source_description == old_desc
    assert mat.size == old_size
    assert mat.valve_type == old_valve_type
    assert db.query(MatchRecommendation).count() == recs_before
    assert db.query(MaterialNationalMapping).count() == maps_before


def test_ai_profile_api_endpoint(db, cpse):
    client = TestClient(app)
    mat = create_material(
        db, cpse,
        desc="BUTTERFLY VALVE DN100 CS CLASS150 RF",
        valve_type="BUTTERFLY",
        size="DN100",
    )

    resp = client.get(f"/api/v1/materials/{mat.id}/ai-profile")
    assert resp.status_code == 200
    body = resp.json()

    assert body["status"] == "success"
    assert body["material_id"] == str(mat.id)
    assert "summary" in body
    assert "agreed_attributes" in body
    assert "ai_profile" in body
    assert "deterministic_profile" in body
    assert body["summary"]["agreed_count"] >= 2


def test_run_entire_extraction_benchmark_suite():
    metrics = run_extraction_benchmark(EXTRACTION_BENCHMARK_CASES)

    assert metrics.total_cases == len(EXTRACTION_BENCHMARK_CASES)
    assert metrics.agreement_rate >= 0.90, f"Extraction agreement too low: {metrics.agreement_rate}"
    assert metrics.missing_field_detection_rate >= 0.90, "Missing fields not reliably detected"
    assert metrics.conflict_detection_rate == 1.0, "Conflicts not 100% detected"
    assert metrics.false_extraction_rate == 0.0, "False extractions detected"
