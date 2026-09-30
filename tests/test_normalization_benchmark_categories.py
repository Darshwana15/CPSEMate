import uuid
import pytest
from app.models import Material, MatchRecommendation, CPSE
from app.services.normalization import normalize_material_record, extract_category_attributes, detect_category
from app.services.review import get_review_queue
from app.services.ai.explainability import MaterialExplanationService


@pytest.fixture
def test_cpse(db):
    cpse = CPSE(code=f"CPSE-BENCH-{uuid.uuid4().hex[:6]}", name="Test Benchmark CPSE")
    db.add(cpse)
    db.commit()
    db.refresh(cpse)
    return cpse


def test_1_strainer_extraction(db, test_cpse):
    """Test 1: STRAINER category detection and attribute extraction."""
    desc = "STRAINER Y-TYPE 2 IN CLASS 150 SS316 MESH 80"
    cat = detect_category(desc)
    assert cat == "STRAINER"
    attrs, _ = extract_category_attributes("STRAINER", desc)
    assert attrs["category"] == "STRAINER"
    assert attrs["type"] == "Y-TYPE"
    assert attrs["size"] == "DN50"
    assert attrs["pressure_rating"] == "CLASS150"
    assert attrs["material_grade"] == "SS316"
    assert attrs["mesh"] == "80"


def test_2_strainer_mesh_extraction(db, test_cpse):
    """Test 2: STRAINER mesh extraction across different formats."""
    # format 1: MESH 80
    attrs1, _ = extract_category_attributes("STRAINER", "STRAINER Y-TYPE 2 IN MESH 80")
    assert attrs1["mesh"] == "80"
    # format 2: 40 MESH
    attrs2, _ = extract_category_attributes("STRAINER", "Y-STRAINER DN50 40 MESH")
    assert attrs2["mesh"] == "40"
    # format 3: MESH100
    attrs3, _ = extract_category_attributes("STRAINER", "STRAINER BASKET DN100 MESH100")
    assert attrs3["mesh"] == "100"


def test_3_c335_normalized_attributes(db, test_cpse):
    """Test 3: C-335 normalized attributes match requirements."""
    mat = Material(
        id=uuid.uuid4(),
        cpse_id=test_cpse.id,
        source_material_code="C-335",
        source_description="STRAINER Y-TYPE 2 IN CLASS 150 SS316 MESH 80",
        source_uom="EA",
        category=None,
        raw_source_data={"code": "C-335"}
    )
    db.add(mat)
    db.commit()

    normalize_material_record(db, mat)
    db.commit()
    db.refresh(mat)

    assert mat.normalized_attributes is not None
    n = mat.normalized_attributes
    assert n["category"] == "STRAINER"
    assert n["type"] == "Y-TYPE"
    assert n["size"] == "DN50"
    assert n["pressure_rating"] == "CLASS150"
    assert n["material_grade"] == "SS316"
    assert n["mesh"] == "80"


def test_4_b231_normalized_attributes(db, test_cpse):
    """Test 4: B-231 normalized attributes match requirements."""
    mat = Material(
        id=uuid.uuid4(),
        cpse_id=test_cpse.id,
        source_material_code="B-231",
        source_description="Y-STRAINER DN50 150# AISI 316 40 MESH",
        source_uom="EA",
        category=None,
        raw_source_data={"code": "B-231"}
    )
    db.add(mat)
    db.commit()

    normalize_material_record(db, mat)
    db.commit()
    db.refresh(mat)

    assert mat.normalized_attributes is not None
    n = mat.normalized_attributes
    assert n["category"] == "STRAINER"
    assert n["type"] == "Y-TYPE"
    assert n["size"] == "DN50"
    assert n["pressure_rating"] == "CLASS150"
    assert n["material_grade"] == "SS316"
    assert n["mesh"] == "40"


def test_5_mesh80_vs_mesh40_distinguishable(db, test_cpse):
    """Test 5: C-335 (mesh 80) and B-231 (mesh 40) are distinguishable and flag conflict in explanation."""
    mat_c = Material(
        id=uuid.uuid4(),
        cpse_id=test_cpse.id,
        source_material_code="C-335",
        source_description="STRAINER Y-TYPE 2 IN CLASS 150 SS316 MESH 80",
        source_uom="EA",
        category=None,
    )
    mat_b = Material(
        id=uuid.uuid4(),
        cpse_id=test_cpse.id,
        source_material_code="B-231",
        source_description="Y-STRAINER DN50 150# AISI 316 40 MESH",
        source_uom="EA",
        category=None,
    )
    db.add_all([mat_c, mat_b])
    db.commit()

    normalize_material_record(db, mat_c)
    normalize_material_record(db, mat_b)
    db.commit()

    assert mat_c.normalized_attributes["mesh"] == "80"
    assert mat_b.normalized_attributes["mesh"] == "40"
    assert mat_c.normalized_attributes["mesh"] != mat_b.normalized_attributes["mesh"]

    # Explainability check
    service = MaterialExplanationService()
    explanation = service.generate_explanation(mat_c, mat_b)
    comp_map = {item.attribute: item for item in explanation.attribute_comparisons}
    assert "mesh" in comp_map
    assert comp_map["mesh"].status == "CONFLICT"
    assert comp_map["mesh"].source_value == "80"
    assert comp_map["mesh"].candidate_value == "40"


def test_6_pipe_extraction(db, test_cpse):
    """Test 6: PIPE category and attributes extraction."""
    desc = "SEAMLESS PIPE 2 IN SCH 40 ASTM A106 GR B"
    assert detect_category(desc) == "PIPE"
    attrs, _ = extract_category_attributes("PIPE", desc)
    assert attrs["construction"] == "SEAMLESS"
    assert attrs["size"] == "DN50"
    assert attrs["schedule"] == "SCH40"
    assert attrs["standard_grade"] == "ASTM A106 GR B"


def test_7_flange_extraction(db, test_cpse):
    """Test 7: FLANGE category and attributes extraction."""
    desc = "WELD NECK FLANGE DN100 CLASS 150 RF CS A105"
    assert detect_category(desc) == "FLANGE"
    attrs, _ = extract_category_attributes("FLANGE", desc)
    assert attrs["flange_type"] == "WELD_NECK"
    assert attrs["size"] == "DN100"
    assert attrs["pressure_rating"] == "CLASS150"
    assert attrs["facing_connection"] == "RF"
    assert attrs["material_grade"] == "CARBON_STEEL"


def test_8_gasket_extraction(db, test_cpse):
    """Test 8: GASKET category and attributes extraction."""
    desc = "SPIRAL WOUND GASKET DN50 CLASS 300 SS316 GRAPHITE"
    assert detect_category(desc) == "GASKET"
    attrs, _ = extract_category_attributes("GASKET", desc)
    assert attrs["gasket_type"] == "SPIRAL_WOUND"
    assert attrs["size"] == "DN50"
    assert attrs["pressure_rating"] == "CLASS300"
    assert attrs["materials_filler"] == "SS316/GRAPHITE"


def test_9_pump_extraction(db, test_cpse):
    """Test 9: PUMP category and attributes extraction."""
    desc = "CENTRIFUGAL PUMP 50 M3/HR 40M HEAD CAST STEEL"
    assert detect_category(desc) == "PUMP"
    attrs, _ = extract_category_attributes("PUMP", desc)
    assert attrs["pump_type"] == "CENTRIFUGAL"
    assert attrs["flow_rate"] == "50 M3/HR"
    assert attrs["head"] == "40M"
    assert attrs["casing_material"] == "CARBON_STEEL"


def test_10_transmitter_extraction(db, test_cpse):
    """Test 10: TRANSMITTER category and attributes extraction."""
    desc = "PRESSURE TRANSMITTER 0-10 BAR 4-20MA HART"
    assert detect_category(desc) == "TRANSMITTER"
    attrs, _ = extract_category_attributes("TRANSMITTER", desc)
    assert attrs["instrument_type"] == "PRESSURE"
    assert "10" in attrs["measurement_range"]
    assert attrs["signal"] == "4-20MA"
    assert attrs["protocol"] == "HART"


def test_11_oring_extraction(db, test_cpse):
    """Test 11: O-RING category and attributes extraction."""
    desc = "O-RING VITON 50MM ID X 5MM CS"
    assert detect_category(desc) == "O-RING"
    attrs, _ = extract_category_attributes("O-RING", desc)
    assert attrs["material_elastomer"] == "VITON"
    assert attrs["inner_diameter"] == "50MM"
    assert attrs["cross_section"] == "5MM"


def test_12_fastener_extraction(db, test_cpse):
    """Test 12: FASTENER category and attributes extraction."""
    desc = "STUD BOLT M20 X 100MM B7/2H WITH 2 NUTS"
    assert detect_category(desc) == "FASTENER"
    attrs, _ = extract_category_attributes("FASTENER", desc)
    assert attrs["type"] == "STUD_BOLT"
    assert attrs["size"] == "M20"
    assert attrs["length"] == "100MM"
    assert attrs["grade"] == "B7/2H"
    assert attrs["nut_specification"] == "2 NUTS"


def test_13_motor_extraction(db, test_cpse):
    """Test 13: MOTOR category and attributes extraction."""
    desc = "INDUCTION MOTOR 3PH 15KW 415V 1500RPM IE3"
    assert detect_category(desc) == "MOTOR"
    attrs, _ = extract_category_attributes("MOTOR", desc)
    assert attrs["motor_type"] == "INDUCTION"
    assert attrs["phase"] == "3PH"
    assert attrs["power"] == "15KW"
    assert attrs["voltage"] == "415V"
    assert attrs["speed"] == "1500RPM"
    assert attrs["efficiency"] == "IE3"


def test_14_bearing_extraction(db, test_cpse):
    """Test 14: BEARING category and attributes extraction."""
    desc = "BALL BEARING 6205-2RS"
    assert detect_category(desc) == "BEARING"
    attrs, _ = extract_category_attributes("BEARING", desc)
    assert attrs["bearing_type"] == "BALL DEEP GROOVE"
    assert attrs["bearing_number"] == "6205"
    assert attrs["seal_shield"] == "2RS"


def test_15_belt_extraction(db, test_cpse):
    """Test 15: BELT category and attributes extraction."""
    desc = "V-BELT SPB 2500"
    assert detect_category(desc) == "BELT"
    attrs, _ = extract_category_attributes("BELT", desc)
    assert attrs["belt_type"] == "V-BELT"
    assert attrs["profile"] == "SPB"
    assert attrs["length"] == "2500"


def test_16_to_19_review_queue_counts_and_filters(db, test_cpse):
    """Tests 16-19: Review Queue ALL, POTENTIAL, DIFFERENT, and MAPPED filters."""
    # Create isolated materials and recommendations with valid source_uom
    m_src1 = Material(id=uuid.uuid4(), cpse_id=test_cpse.id, source_material_code="RQ-S1", source_description="MAT 1", source_uom="EA")
    m_cand1 = Material(id=uuid.uuid4(), cpse_id=test_cpse.id, source_material_code="RQ-C1", source_description="MAT 2", source_uom="EA")
    m_cand2 = Material(id=uuid.uuid4(), cpse_id=test_cpse.id, source_material_code="RQ-C2", source_description="MAT 3", source_uom="EA")
    db.add_all([m_src1, m_cand1, m_cand2])
    db.commit()

    rec_pe = MatchRecommendation(
        id=uuid.uuid4(),
        source_material_id=m_src1.id,
        candidate_material_id=m_cand1.id,
        classification="POTENTIALLY_EQUIVALENT",
        confidence=0.75,
        explanation="Partial match"
    )
    rec_diff = MatchRecommendation(
        id=uuid.uuid4(),
        source_material_id=m_src1.id,
        candidate_material_id=m_cand2.id,
        classification="DIFFERENT",
        confidence=0.20,
        explanation="Distinct items"
    )
    db.add_all([rec_pe, rec_diff])
    db.commit()

    # 16. Queue ALL
    q_all = get_review_queue(db, limit=500, cpse_id=test_cpse.id)
    rec_ids = [item["recommendation_id"] for item in q_all]
    assert str(rec_pe.id) in rec_ids
    assert str(rec_diff.id) in rec_ids

    # 17. Queue POTENTIAL
    q_pe = get_review_queue(db, limit=500, classification="POTENTIALLY_EQUIVALENT", cpse_id=test_cpse.id)
    pe_ids = [item["recommendation_id"] for item in q_pe]
    assert str(rec_pe.id) in pe_ids
    assert str(rec_diff.id) not in pe_ids

    # 18. Queue DIFFERENT
    q_diff = get_review_queue(db, limit=500, classification="DIFFERENT", cpse_id=test_cpse.id)
    diff_ids = [item["recommendation_id"] for item in q_diff]
    assert str(rec_diff.id) in diff_ids
    assert str(rec_pe.id) not in diff_ids

    # 19. Queue MAPPED presence check
    from app.models import NationalMaterial, MaterialNationalMapping
    nm = NationalMaterial(
        id=uuid.uuid4(),
        national_code=f"NM-{uuid.uuid4().hex[:6]}",
        identity_key=f"KEY-{uuid.uuid4()}",
        canonical_description="NM DESC",
        category="VALVE",
        valve_type="BALL",
        size="DN50",
        body_material="CARBON_STEEL",
        pressure_class="CLASS300",
        connection_type="RF",
        trim="SS304",
        normalized_uom="EACH",
        status="ACTIVE"
    )
    db.add(nm)
    db.flush()
    mapping = MaterialNationalMapping(
        id=uuid.uuid4(),
        material_id=m_src1.id,
        national_material_id=nm.id,
        basis="HUMAN_CONFIRMED_SAME",
        status="ACTIVE",
        recommendation_id=rec_pe.id
    )
    db.add(mapping)
    db.commit()

    q_mapped_check = get_review_queue(db, limit=500, cpse_id=test_cpse.id)
    rec_pe_in_queue = next(item for item in q_mapped_check if item["recommendation_id"] == str(rec_pe.id))
    assert rec_pe_in_queue["mapping_status"] == "MAPPED"
    assert rec_pe_in_queue["national_material_code"] == nm.national_code


def test_20_existing_valve_normalization_regressions(db, test_cpse):
    """Test 20: Existing valve normalization behavior remains perfectly intact."""
    v = Material(
        id=uuid.uuid4(),
        cpse_id=test_cpse.id,
        source_material_code="VALVE-REG-1",
        source_description="BALL VALVE 2 IN CS CLASS300 RF SS316",
        source_uom="EA",
        category=None,
    )
    db.add(v)
    db.commit()

    normalize_material_record(db, v)
    db.commit()
    db.refresh(v)

    assert v.category == "VALVE"
    assert v.valve_type == "BALL"
    assert v.size == "DN50"
    assert v.body_material == "CARBON_STEEL"
    assert v.pressure_class == "CLASS300"
    assert v.connection_type == "RF"
    assert v.trim == "SS316"
    assert v.normalized_uom == "EACH"
    assert v.normalized_attributes["category"] == "VALVE"
