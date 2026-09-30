import pytest
import uuid
from fastapi.testclient import TestClient

from app.models import CPSE, Material, AuditLog
from app.services.normalization import normalize_material_record

@pytest.fixture
def test_cpse(db):
    cpse = CPSE(code=f"CPSE-NORM-{uuid.uuid4()}", name="Test NORM CPSE")
    db.add(cpse)
    db.commit()
    db.refresh(cpse)
    return cpse

def create_raw_material(db, cpse, desc: str, specs: str = None, uom: str = "EA") -> Material:
    mat = Material(
        id=uuid.uuid4(),
        cpse_id=cpse.id,
        source_material_code=f"M-{uuid.uuid4()}",
        source_description=desc,
        source_uom=uom,
        source_specifications=specs,
        category="VALVE",
        raw_source_data={"original": desc}
    )
    db.add(mat)
    db.commit()
    db.refresh(mat)
    return mat

def test_norm_valve_types(db, test_cpse):
    mat1 = create_raw_material(db, test_cpse, "BALL VALVE DN50")
    normalize_material_record(db, mat1)
    assert mat1.valve_type == "BALL"

    mat2 = create_raw_material(db, test_cpse, "GATE VALVE CS")
    normalize_material_record(db, mat2)
    assert mat2.valve_type == "GATE"

def test_norm_body_materials(db, test_cpse):
    mat1 = create_raw_material(db, test_cpse, "VALVE CS CLASS 150")
    normalize_material_record(db, mat1)
    assert mat1.body_material == "CARBON_STEEL"

    mat2 = create_raw_material(db, test_cpse, "VALVE SS CLASS 300")
    normalize_material_record(db, mat2)
    assert mat2.body_material == "STAINLESS_STEEL"

def test_norm_pressure_classes(db, test_cpse):
    mat1 = create_raw_material(db, test_cpse, "VALVE CLASS150")
    normalize_material_record(db, mat1)
    assert mat1.pressure_class == "CLASS150"

    mat2 = create_raw_material(db, test_cpse, "VALVE CLASS 150")
    normalize_material_record(db, mat2)
    assert mat2.pressure_class == "CLASS150"

    mat3 = create_raw_material(db, test_cpse, "VALVE 150#")
    normalize_material_record(db, mat3)
    assert mat3.pressure_class == "CLASS150"

    mat4 = create_raw_material(db, test_cpse, "VALVE CLASS300")
    normalize_material_record(db, mat4)
    assert mat4.pressure_class == "CLASS300"

    mat5 = create_raw_material(db, test_cpse, "VALVE 300#")
    normalize_material_record(db, mat5)
    assert mat5.pressure_class == "CLASS300"

def test_norm_sizes(db, test_cpse):
    mat1 = create_raw_material(db, test_cpse, "VALVE DN50")
    normalize_material_record(db, mat1)
    assert mat1.size == "DN50"

    mat2 = create_raw_material(db, test_cpse, "VALVE 50MM")
    normalize_material_record(db, mat2)
    assert mat2.size == "DN50"

    mat3 = create_raw_material(db, test_cpse, "VALVE 2 IN")
    normalize_material_record(db, mat3)
    assert mat3.size == "DN50"

def test_norm_connections(db, test_cpse):
    mat1 = create_raw_material(db, test_cpse, "VALVE RF")
    normalize_material_record(db, mat1)
    assert mat1.connection_type == "RF"

    mat2 = create_raw_material(db, test_cpse, "VALVE RAISED FACE")
    normalize_material_record(db, mat2)
    assert mat2.connection_type == "RF"

    mat3 = create_raw_material(db, test_cpse, "VALVE SOCKET WELD")
    normalize_material_record(db, mat3)
    assert mat3.connection_type == "SOCKET_WELD"

def test_norm_trim(db, test_cpse):
    mat1 = create_raw_material(db, test_cpse, "VALVE SS304 TRIM")
    normalize_material_record(db, mat1)
    assert mat1.trim == "SS304"

    mat2 = create_raw_material(db, test_cpse, "VALVE 316 TRIM")
    normalize_material_record(db, mat2)
    assert mat2.trim == "SS316"

    mat3 = create_raw_material(db, test_cpse, "VALVE", specs="TRIM 8")
    normalize_material_record(db, mat3)
    assert mat3.trim == "8"

    mat_missing = create_raw_material(db, test_cpse, "VALVE SS CS")
    normalize_material_record(db, mat_missing)
    assert mat_missing.trim is None

def test_ss_trim_normalization_regression_cases(db, test_cpse):
    # 1. BALL VALVE DN100 CS CLASS600 RF 316SS -> trim == SS316
    m1 = create_raw_material(db, test_cpse, "BALL VALVE DN100 CS CLASS600 RF 316SS")
    normalize_material_record(db, m1)
    assert m1.trim == "SS316"
    assert m1.body_material == "CARBON_STEEL"

    # 2. BALL VALVE DN100 CS CLASS600 RF SS316 -> trim == SS316
    m2 = create_raw_material(db, test_cpse, "BALL VALVE DN100 CS CLASS600 RF SS316")
    normalize_material_record(db, m2)
    assert m2.trim == "SS316"
    assert m2.body_material == "CARBON_STEEL"

    # 3. BALL VALVE DN100 CS CLASS600 RF 316 SS -> trim == SS316
    m3 = create_raw_material(db, test_cpse, "BALL VALVE DN100 CS CLASS600 RF 316 SS")
    normalize_material_record(db, m3)
    assert m3.trim == "SS316"
    assert m3.body_material == "CARBON_STEEL"

    # 4. BALL VALVE DN100 CS CLASS600 RF SS 316 -> trim == SS316
    m4 = create_raw_material(db, test_cpse, "BALL VALVE DN100 CS CLASS600 RF SS 316")
    normalize_material_record(db, m4)
    assert m4.trim == "SS316"
    assert m4.body_material == "CARBON_STEEL"

    # 5. BALL VALVE DN50 CARBON STEEL CLASS300 RF SS304 -> trim == SS304
    m5 = create_raw_material(db, test_cpse, "BALL VALVE DN50 CARBON STEEL CLASS300 RF SS304")
    normalize_material_record(db, m5)
    assert m5.trim == "SS304"
    assert m5.body_material == "CARBON_STEEL"

    # 6. BALL VALVE DN50 CARBON STEEL CLASS300 RF 304SS -> trim == SS304
    m6 = create_raw_material(db, test_cpse, "BALL VALVE DN50 CARBON STEEL CLASS300 RF 304SS")
    normalize_material_record(db, m6)
    assert m6.trim == "SS304"
    assert m6.body_material == "CARBON_STEEL"

    # 7. VALVE GATE 100MM STAINLESS STEEL CL150 RAISED FACE 316SS -> trim == SS316
    m7 = create_raw_material(db, test_cpse, "VALVE GATE 100MM STAINLESS STEEL CL150 RAISED FACE 316SS")
    normalize_material_record(db, m7)
    assert m7.trim == "SS316"
    assert m7.body_material == "STAINLESS_STEEL"
    assert m7.valve_type == "GATE"
    assert m7.size == "DN100"
    assert m7.pressure_class == "CLASS150"
    assert m7.connection_type == "RF"

    # 8. BALL VALVE 4 IN CS CLASS600 RF SS316 TRIM -> trim == SS316
    m8 = create_raw_material(db, test_cpse, "BALL VALVE 4 IN CS CLASS600 RF SS316 TRIM")
    normalize_material_record(db, m8)
    assert m8.trim == "SS316"
    assert m8.body_material == "CARBON_STEEL"
    assert m8.valve_type == "BALL"
    assert m8.size == "DN100"
    assert m8.pressure_class == "CLASS600"
    assert m8.connection_type == "RF"

def test_norm_missing_attributes_are_null(db, test_cpse):
    mat = create_raw_material(db, test_cpse, "VALVE")
    normalize_material_record(db, mat)
    assert mat.size is None
    assert mat.pressure_class is None
    assert mat.body_material is None

def test_norm_ss_does_not_become_ss304(db, test_cpse):
    mat = create_raw_material(db, test_cpse, "VALVE SS")
    normalize_material_record(db, mat)
    assert mat.body_material == "STAINLESS_STEEL"
    assert mat.body_material != "SS304"

def test_norm_class150_vs_class300(db, test_cpse):
    mat1 = create_raw_material(db, test_cpse, "CLASS150")
    mat2 = create_raw_material(db, test_cpse, "CLASS300")
    normalize_material_record(db, mat1)
    normalize_material_record(db, mat2)
    assert mat1.pressure_class != mat2.pressure_class

def test_norm_uom(db, test_cpse):
    mat_ea = create_raw_material(db, test_cpse, "V", uom="EA")
    mat_nos = create_raw_material(db, test_cpse, "V", uom="NOS")
    mat_pcs = create_raw_material(db, test_cpse, "V", uom="PCS")
    mat_unknown = create_raw_material(db, test_cpse, "V", uom="UNKNOWN_UOM")

    for mat in [mat_ea, mat_nos, mat_pcs, mat_unknown]:
        normalize_material_record(db, mat)

    assert mat_ea.normalized_uom == "EACH"
    assert mat_nos.normalized_uom == "EACH"
    assert mat_pcs.normalized_uom == "EACH"
    assert mat_unknown.normalized_uom is None
    assert mat_unknown.source_uom == "UNKNOWN_UOM"

def test_norm_source_data_unchanged(db, test_cpse):
    desc = "  BALL VALVE  2 IN CS  "
    mat = create_raw_material(db, test_cpse, desc)
    normalize_material_record(db, mat)

    assert mat.source_description == desc
    assert mat.normalized_description == "BALL VALVE 2 IN CS"
    assert mat.raw_source_data == {"original": desc}

def test_norm_is_idempotent(db, test_cpse):
    mat = create_raw_material(db, test_cpse, "BALL VALVE 2 IN CS CLASS150")

    audit1 = normalize_material_record(db, mat)
    db.commit()
    assert audit1 is not None
    assert mat.valve_type == "BALL"

    # Run again
    audit2 = normalize_material_record(db, mat)
    db.commit()
    assert audit2 is None # No changes means no new audit log
    assert mat.valve_type == "BALL"

# --- SAFETY TESTS ---

def test_critical_safety_1_no_inferred_trim(db, test_cpse):
    # "BALL VALVE 2 IN CS CLASS300 RF"
    mat = create_raw_material(db, test_cpse, "BALL VALVE 2 IN CS CLASS300 RF")
    normalize_material_record(db, mat)
    assert mat.valve_type == "BALL"
    assert mat.size == "DN50"
    assert mat.body_material == "CARBON_STEEL"
    assert mat.pressure_class == "CLASS300"
    assert mat.connection_type == "RF"
    assert mat.trim is None

def test_critical_safety_2_pressure_classes_distinct(db, test_cpse):
    mat_a = create_raw_material(db, test_cpse, "BALL VALVE 2 IN CS CLASS150 RF")
    mat_b = create_raw_material(db, test_cpse, "BALL VALVE 2 IN CS CLASS300 RF")
    normalize_material_record(db, mat_a)
    normalize_material_record(db, mat_b)

    assert mat_a.pressure_class == "CLASS150"
    assert mat_b.pressure_class == "CLASS300"

def test_critical_safety_3_trim_vs_body(db, test_cpse):
    mat1 = create_raw_material(db, test_cpse, "BALL VALVE 2 IN CS CLASS300 RF SS304 TRIM")
    normalize_material_record(db, mat1)
    assert mat1.trim == "SS304"
    assert mat1.body_material == "CARBON_STEEL"

    mat2 = create_raw_material(db, test_cpse, "BALL VALVE 2 IN SS CLASS300 RF")
    normalize_material_record(db, mat2)
    assert mat2.body_material == "STAINLESS_STEEL"
    assert mat2.trim is None

def test_api_endpoint(client: TestClient, db, test_cpse):
    mat = create_raw_material(db, test_cpse, "GATE VALVE")

    response = client.post(f"/api/v1/materials/{mat.id}/normalize")
    assert response.status_code == 200

    db.refresh(mat)
    assert mat.valve_type == "GATE"
    assert mat.category == "VALVE"

    logs = db.query(AuditLog).filter(AuditLog.entity_id == str(mat.id)).all()
    assert len(logs) == 1
    assert logs[0].action == "NORMALIZE"

def test_regression_patch_5d_case1(db, test_cpse):
    # Case 1: BALL VALVE 2 IN CS CLASS300 RF SS304 TRIM
    mat = Material(
        id=uuid.uuid4(),
        cpse_id=test_cpse.id,
        source_material_code="CASE-1",
        source_description="BALL VALVE 2 IN CS CLASS300 RF SS304 TRIM",
        source_uom="EA",
        category=None,
        raw_source_data={"original": "BALL VALVE 2 IN CS CLASS300 RF SS304 TRIM"}
    )
    db.add(mat)
    db.commit()

    normalize_material_record(db, mat)
    db.commit()
    db.refresh(mat)

    assert mat.category == "VALVE"
    assert mat.valve_type == "BALL"
    assert mat.size == "DN50"
    assert mat.body_material == "CARBON_STEEL"
    assert mat.pressure_class == "CLASS300"
    assert mat.connection_type == "RF"
    assert mat.trim == "SS304"
    assert mat.normalized_uom == "EACH"
    assert mat.normalized_description == "BALL VALVE 2 IN CS CLASS300 RF SS304 TRIM"

def test_regression_patch_5d_case2(db, test_cpse):
    # Case 2: BALL VLV DN50 CARBON STEEL CLASS 300 RF SS304
    mat = Material(
        id=uuid.uuid4(),
        cpse_id=test_cpse.id,
        source_material_code="CASE-2",
        source_description="BALL VLV DN50 CARBON STEEL CLASS 300 RF SS304",
        source_uom="EA",
        category=None,
        raw_source_data={"original": "BALL VLV DN50 CARBON STEEL CLASS 300 RF SS304"}
    )
    db.add(mat)
    db.commit()

    normalize_material_record(db, mat)
    db.commit()
    db.refresh(mat)

    assert mat.category == "VALVE"
    assert mat.valve_type == "BALL"
    assert mat.size == "DN50"
    assert mat.body_material == "CARBON_STEEL"
    assert mat.pressure_class == "CLASS300"
    assert mat.connection_type == "RF"
    assert mat.trim == "SS304"
    assert mat.normalized_uom == "EACH"
    assert mat.normalized_description == "BALL VLV DN50 CARBON STEEL CLASS 300 RF SS304"

def test_regression_patch_5e_category_pump(db, test_cpse):
    # 3. CENTRIFUGAL PUMP 50GPM 100PSI CS
    mat = Material(
        id=uuid.uuid4(),
        cpse_id=test_cpse.id,
        source_material_code="PUMP-1",
        source_description="CENTRIFUGAL PUMP 50GPM 100PSI CS",
        source_uom="EA",
        category=None,
        raw_source_data={"original": "CENTRIFUGAL PUMP 50GPM 100PSI CS"}
    )
    db.add(mat)
    db.commit()

    normalize_material_record(db, mat)
    db.commit()
    db.refresh(mat)

    assert mat.category == "PUMP"
    assert mat.valve_type is None
    assert mat.size is None
    assert mat.pressure_class is None
    assert mat.body_material == "CARBON_STEEL"
    assert mat.connection_type is None
    assert mat.trim is None
    assert mat.normalized_uom == "EACH"
    assert mat.normalized_description == "CENTRIFUGAL PUMP 50GPM 100PSI CS"

def test_regression_patch_5e_category_gasket(db, test_cpse):
    # 4. SPIRAL WOUND GASKET DN50 CLASS 300 CS/PTFE
    mat = Material(
        id=uuid.uuid4(),
        cpse_id=test_cpse.id,
        source_material_code="GASKET-1",
        source_description="SPIRAL WOUND GASKET DN50 CLASS 300 CS/PTFE",
        source_uom="EA",
        category=None,
        raw_source_data={"original": "SPIRAL WOUND GASKET DN50 CLASS 300 CS/PTFE"}
    )
    db.add(mat)
    db.commit()

    normalize_material_record(db, mat)
    db.commit()
    db.refresh(mat)

    assert mat.category == "GASKET"
    assert mat.valve_type is None
    assert mat.size == "DN50"
    assert mat.pressure_class == "CLASS300"
    assert mat.body_material == "CARBON_STEEL"
    assert mat.connection_type is None
    assert mat.trim is None
    assert mat.normalized_uom == "EACH"
    assert mat.normalized_description == "SPIRAL WOUND GASKET DN50 CLASS 300 CS/PTFE"

def test_regression_patch_5e_category_flange(db, test_cpse):
    # 5. WELD NECK FLANGE DN100 CS CLASS150
    mat = Material(
        id=uuid.uuid4(),
        cpse_id=test_cpse.id,
        source_material_code="FLANGE-1",
        source_description="WELD NECK FLANGE DN100 CS CLASS150",
        source_uom="EA",
        category=None,
        raw_source_data={"original": "WELD NECK FLANGE DN100 CS CLASS150"}
    )
    db.add(mat)
    db.commit()

    normalize_material_record(db, mat)
    db.commit()
    db.refresh(mat)

    assert mat.category == "FLANGE"
    assert mat.valve_type is None
    assert mat.size == "DN100"
    assert mat.pressure_class == "CLASS150"
    assert mat.body_material == "CARBON_STEEL"
    assert mat.trim is None
    assert mat.normalized_uom == "EACH"
    assert mat.normalized_description == "WELD NECK FLANGE DN100 CS CLASS150"

def test_regression_patch_5e_category_bearing(db, test_cpse):
    # 6. ROLLER BEARING 6204-2RS
    mat = Material(
        id=uuid.uuid4(),
        cpse_id=test_cpse.id,
        source_material_code="BEARING-1",
        source_description="ROLLER BEARING 6204-2RS",
        source_uom="EA",
        category=None,
        raw_source_data={"original": "ROLLER BEARING 6204-2RS"}
    )
    db.add(mat)
    db.commit()

    normalize_material_record(db, mat)
    db.commit()
    db.refresh(mat)

    assert mat.category == "BEARING"
    assert mat.valve_type is None
    assert mat.size is None
    assert mat.pressure_class is None
    assert mat.body_material is None
    assert mat.connection_type is None
    assert mat.trim is None
    assert mat.normalized_uom == "EACH"
    assert mat.normalized_description == "ROLLER BEARING 6204-2RS"

def test_regression_patch_5e_ball_bearing_not_valve(db, test_cpse):
    # BALL BEARING should be BEARING and have valve_type is None
    mat = Material(
        id=uuid.uuid4(),
        cpse_id=test_cpse.id,
        source_material_code="BEARING-2",
        source_description="BALL BEARING 6205",
        source_uom="EA",
        category=None,
        raw_source_data={"original": "BALL BEARING 6205"}
    )
    db.add(mat)
    db.commit()

    normalize_material_record(db, mat)
    db.commit()
    db.refresh(mat)

    assert mat.category == "BEARING"
    assert mat.valve_type is None

def test_regression_patch_5e_category_fastener(db, test_cpse):
    # 7. HEX BOLT M16 X 50MM SS304
    mat = Material(
        id=uuid.uuid4(),
        cpse_id=test_cpse.id,
        source_material_code="BOLT-1",
        source_description="HEX BOLT M16 X 50MM SS304",
        source_uom="EA",
        category=None,
        raw_source_data={"original": "HEX BOLT M16 X 50MM SS304"}
    )
    db.add(mat)
    db.commit()

    normalize_material_record(db, mat)
    db.commit()
    db.refresh(mat)

    assert mat.category == "FASTENER"
    assert mat.valve_type is None
    assert mat.size is None
    assert mat.pressure_class is None
    assert mat.body_material == "SS304"
    assert mat.connection_type is None
    assert mat.trim is None
    assert mat.normalized_uom == "EACH"
    assert mat.normalized_description == "HEX BOLT M16 X 50MM SS304"


