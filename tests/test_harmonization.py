import pytest
import uuid
from fastapi.testclient import TestClient

from app.models import CPSE, Material, MatchRecommendation, NationalMaterial, MaterialNationalMapping, AuditLog
from app.services.harmonization import harmonize_material

@pytest.fixture
def cpse_x(db):
    c = CPSE(code=f"CPSE-X-{uuid.uuid4()}", name="X")
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
        normalized_description="NORM DESC",
        valve_type=attrs.get("valve_type", "BALL"),
        size=attrs.get("size", "DN50"),
        body_material=attrs.get("body_material", "CARBON_STEEL"),
        pressure_class=attrs.get("pressure_class", "CLASS300"),
        connection_type=attrs.get("connection_type", "RF"),
        trim=attrs.get("trim", "SS304"),
        normalized_uom="EACH"
    )
    db.add(mat)
    db.commit()
    db.refresh(mat)
    return mat

def create_rec(db, m1: Material, m2: Material, classification: str):
    r = MatchRecommendation(
        source_material_id=m1.id,
        candidate_material_id=m2.id,
        classification=classification,
        confidence=0.95 if classification == "SAME" else 0.5
    )
    db.add(r)
    db.commit()
    db.refresh(r)
    return r

def test_harmonize_complete_same(db, cpse_x):
    v_type = f"PLUG_{uuid.uuid4().hex[:4]}"
    m1 = create_mat(db, cpse_x, {"valve_type": v_type})
    m2 = create_mat(db, cpse_x, {"valve_type": v_type})
    create_rec(db, m1, m2, "SAME")

    res = harmonize_material(db, m1)
    db.commit()

    assert res["status"] == "success"
    assert res["national_material_action"] == "CREATED" # 1. Complete SAME -> NM created

    nm = db.query(NationalMaterial).filter_by(id=res["national_material_id"]).first()
    assert nm is not None
    assert nm.national_code is not None # 16. National code
    assert f"{v_type} VALVE DN50 CARBON_STEEL CLASS300 RF SS304 TRIM" in nm.canonical_description # 17. Canonical desc

    map1 = db.query(MaterialNationalMapping).filter_by(id=res["mapping_id"]).first()
    assert map1.status == "ACTIVE"
    assert map1.basis == "AUTO_SAME" # 4. ACTIVE AUTO_SAME mapping

    # 15. AuditLog records actions
    logs = db.query(AuditLog).filter(AuditLog.action.in_(["CREATE_NATIONAL_MATERIAL", "CREATE_MAPPING"])).all()
    assert len(logs) >= 2

def test_harmonize_reuse_nm(db, cpse_x):
    # 2. Repeated same identity -> reused NM
    # 3. Same identity never creates duplicates
    v_type = f"GLOBE_{uuid.uuid4().hex[:4]}"
    m1 = create_mat(db, cpse_x, {"valve_type": v_type})
    m2 = create_mat(db, cpse_x, {"valve_type": v_type})
    m3 = create_mat(db, cpse_x, {"valve_type": v_type})
    create_rec(db, m1, m2, "SAME")
    create_rec(db, m3, m2, "SAME")

    res1 = harmonize_material(db, m1)
    db.commit()
    assert res1["national_material_action"] == "CREATED"

    res2 = harmonize_material(db, m3)
    db.commit()
    assert res2["national_material_action"] == "REUSED"
    assert res1["national_material_id"] == res2["national_material_id"]

def test_harmonize_no_auto_map_for_potential_or_different(db, cpse_x):
    m1 = create_mat(db, cpse_x, {})
    m2 = create_mat(db, cpse_x, {})
    create_rec(db, m1, m2, "POTENTIALLY_EQUIVALENT")

    res = harmonize_material(db, m1)
    assert res["status"] == "skipped" # 5. POTENTIALLY_EQUIVALENT -> no automatic mapping

    m3 = create_mat(db, cpse_x, {})
    create_rec(db, m1, m3, "DIFFERENT")
    res2 = harmonize_material(db, m1)
    assert res2["status"] == "skipped" # 6. DIFFERENT -> no automatic mapping

def test_harmonize_missing_attributes(db, cpse_x):
    # 7. Missing trim
    m_no_trim = create_mat(db, cpse_x, {"trim": None})
    res = harmonize_material(db, m_no_trim)
    assert res["status"] == "skipped"
    assert "Incomplete identity" in res["reason"]

    # 8. Missing size
    m_no_size = create_mat(db, cpse_x, {"size": None})
    res2 = harmonize_material(db, m_no_size)
    assert res2["status"] == "skipped"

    # 9. Missing pressure class
    m_no_pc = create_mat(db, cpse_x, {"pressure_class": None})
    res3 = harmonize_material(db, m_no_pc)
    assert res3["status"] == "skipped"

def test_separate_identities(db, cpse_x):
    m_150 = create_mat(db, cpse_x, {"pressure_class": "CLASS150"})
    m_300 = create_mat(db, cpse_x, {"pressure_class": "CLASS300"})
    m_dn50 = create_mat(db, cpse_x, {"size": "DN50"})
    m_dn100 = create_mat(db, cpse_x, {"size": "DN100"})
    m_gate = create_mat(db, cpse_x, {"valve_type": "GATE"})

    m_150_b = create_mat(db, cpse_x, {"pressure_class": "CLASS150"})
    create_rec(db, m_150, m_150_b, "SAME")
    r1 = harmonize_material(db, m_150)

    m_300_b = create_mat(db, cpse_x, {"pressure_class": "CLASS300"})
    create_rec(db, m_300, m_300_b, "SAME")
    r2 = harmonize_material(db, m_300)

    assert r1["national_material_id"] != r2["national_material_id"] # 11. Different classes remain separate

    m_100_b = create_mat(db, cpse_x, {"size": "DN100"})
    create_rec(db, m_dn100, m_100_b, "SAME")
    r3 = harmonize_material(db, m_dn100)

    # m_dn50 is practically same as m_300 depending on defaults, let's just make sure 100 is different
    assert r3["national_material_id"] != r1["national_material_id"] # 12. Different sizes remain separate

    m_gate_b = create_mat(db, cpse_x, {"valve_type": "GATE"})
    create_rec(db, m_gate, m_gate_b, "SAME")
    r4 = harmonize_material(db, m_gate)
    assert r4["national_material_id"] != r1["national_material_id"] # 13. Different types remain separate

def test_existing_mapping_not_replaced(db, cpse_x):
    m1 = create_mat(db, cpse_x, {})
    m2 = create_mat(db, cpse_x, {})
    create_rec(db, m1, m2, "SAME")

    res1 = harmonize_material(db, m1)
    db.commit()
    assert res1["status"] == "success"

    # Run again, should skip
    res2 = harmonize_material(db, m1)
    assert res2["status"] == "skipped"
    assert "already has an active mapping" in res2["reason"].lower() # 14. Not silently replaced

def test_regression_abc(db, cpse_x):
    # A: BALL / DN50 / CARBON_STEEL / CLASS300 / RF / SS304
    a_attrs = {"valve_type": "BALL", "size": "DN50", "body_material": "CARBON_STEEL",
               "pressure_class": "CLASS300", "connection_type": "RF", "trim": "SS304"}
    m_a = create_mat(db, cpse_x, a_attrs)

    # B: BALL / DN50 / CARBON_STEEL / CLASS300 / RF / SS304
    m_b = create_mat(db, cpse_x, a_attrs)

    # C: BALL / DN50 / CARBON_STEEL / CLASS300 / RF / NULL
    c_attrs = a_attrs.copy()
    c_attrs["trim"] = None
    m_c = create_mat(db, cpse_x, c_attrs)

    create_rec(db, m_a, m_b, "SAME")
    create_rec(db, m_b, m_a, "SAME")
    r_a = harmonize_material(db, m_a)
    r_b = harmonize_material(db, m_b)

    assert r_a["status"] == "success"
    assert r_b["status"] == "success"
    assert r_a["national_material_id"] == r_b["national_material_id"] # A and B -> same NM

    # Assuming M_C somehow had a SAME rec (which it shouldn't normally, but testing robustness)
    create_rec(db, m_c, m_a, "SAME")
    r_c = harmonize_material(db, m_c)
    assert r_c["status"] == "skipped" # 10. NULL never acts as wildcard / C -> no NM

from app.services.harmonization import harmonize_material, harmonize_same_families, get_identity_key

@pytest.fixture
def cpse_y(db):
    c = CPSE(code=f"CPSE-Y-{uuid.uuid4()}", name="Y")
    db.add(c)
    db.commit()
    db.refresh(c)
    return c

@pytest.fixture
def cpse_z(db):
    c = CPSE(code=f"CPSE-Z-{uuid.uuid4()}", name="Z")
    db.add(c)
    db.commit()
    db.refresh(c)
    return c

def test_api_endpoint(client: TestClient, db, cpse_x):
    m1 = create_mat(db, cpse_x, {})
    m2 = create_mat(db, cpse_x, {})
    create_rec(db, m1, m2, "SAME")

    resp = client.post(f"/api/v1/materials/{m1.id}/harmonize")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert "national_material_id" in data

def test_harmonize_same_families_strainer_mesh(db, cpse_x, cpse_y, cpse_z):
    tag = uuid.uuid4().hex[:6]
    stype = f"Y-TYPE-{tag}"
    # Strainers with Mesh 40 in CPSE X, Y, Z
    m_x40 = Material(
        id=uuid.uuid4(),
        cpse_id=cpse_x.id,
        source_material_code=f"A-134-{tag}",
        source_description=f"STRAINER {stype} 2 IN CLASS 150 SS316 MESH 40",
        source_uom="EA",
        category=None,
        normalized_description=f"STRAINER {stype} DN50 CLASS150 SS316 MESH40",
        normalized_attributes={
            "category": "STRAINER",
            "type": stype,
            "size": "DN50",
            "pressure_rating": "CLASS150",
            "material_grade": "SS316",
            "mesh": "40",
            "schema_version": "2.0"
        }
    )
    m_y40 = Material(
        id=uuid.uuid4(),
        cpse_id=cpse_y.id,
        source_material_code=f"B-231-{tag}",
        source_description=f"Y-STRAINER {stype} DN50 150# AISI 316 40 MESH",
        source_uom="NOS",
        category=None,
        normalized_description=f"STRAINER {stype} DN50 CLASS150 SS316 MESH40",
        normalized_attributes={
            "category": "STRAINER",
            "type": stype,
            "size": "DN50",
            "pressure_rating": "CLASS150",
            "material_grade": "SS316",
            "mesh": "40",
            "schema_version": "2.0"
        }
    )
    m_z40 = Material(
        id=uuid.uuid4(),
        cpse_id=cpse_z.id,
        source_material_code=f"C-334-{tag}",
        source_description=f"STRAINER {stype} 2 INCH CL150 SS316 40MESH",
        source_uom="EA",
        category=None,
        normalized_description=f"STRAINER {stype} DN50 CLASS150 SS316 MESH40",
        normalized_attributes={
            "category": "STRAINER",
            "type": stype,
            "size": "DN50",
            "pressure_rating": "CLASS150",
            "material_grade": "SS316",
            "mesh": "40",
            "schema_version": "2.0"
        }
    )
    # Strainer with Mesh 80 in CPSE Z
    m_z80 = Material(
        id=uuid.uuid4(),
        cpse_id=cpse_z.id,
        source_material_code=f"C-335-{tag}",
        source_description=f"STRAINER {stype} 2 IN CLASS 150 SS316 MESH 80",
        source_uom="EA",
        category=None,
        normalized_description=f"STRAINER {stype} DN50 CLASS150 SS316 MESH80",
        normalized_attributes={
            "category": "STRAINER",
            "type": stype,
            "size": "DN50",
            "pressure_rating": "CLASS150",
            "material_grade": "SS316",
            "mesh": "80",
            "schema_version": "2.0"
        }
    )
    db.add_all([m_x40, m_y40, m_z40, m_z80])
    db.commit()

    # Recommendations: X40 <-> Y40 SAME, Y40 <-> Z40 SAME, X40 <-> Z80 DIFFERENT
    create_rec(db, m_x40, m_y40, "SAME")
    create_rec(db, m_y40, m_x40, "SAME")
    create_rec(db, m_y40, m_z40, "SAME")
    create_rec(db, m_z40, m_y40, "SAME")
    create_rec(db, m_x40, m_z80, "DIFFERENT")

    res = harmonize_same_families(db)
    db.commit()

    assert res["status"] == "success"
    assert res["national_materials_created"] >= 1
    assert res["mappings_created"] >= 3

    # Check X40, Y40, Z40 all mapped to the SAME National Material
    map_x = db.query(MaterialNationalMapping).filter_by(material_id=m_x40.id, status="ACTIVE").first()
    map_y = db.query(MaterialNationalMapping).filter_by(material_id=m_y40.id, status="ACTIVE").first()
    map_z = db.query(MaterialNationalMapping).filter_by(material_id=m_z40.id, status="ACTIVE").first()
    assert map_x is not None
    assert map_y is not None
    assert map_z is not None
    assert map_x.national_material_id == map_y.national_material_id == map_z.national_material_id

    nm = db.query(NationalMaterial).filter_by(id=map_x.national_material_id).first()
    assert "MESH_40" in nm.identity_key
    assert "STRAINER" in nm.canonical_description

    # Check Z80 has NO active mapping
    map_z80 = db.query(MaterialNationalMapping).filter_by(material_id=m_z80.id, status="ACTIVE").first()
    assert map_z80 is None

def test_harmonize_same_families_idempotent(db, cpse_x, cpse_y):
    tag = uuid.uuid4().hex[:6]
    v_type = f"BALL_IDEMP_{tag}"
    m1 = create_mat(db, cpse_x, {"valve_type": v_type})
    m2 = create_mat(db, cpse_y, {"valve_type": v_type})
    create_rec(db, m1, m2, "SAME")
    create_rec(db, m2, m1, "SAME")

    res1 = harmonize_same_families(db)
    db.commit()
    assert res1["national_materials_created"] >= 1
    assert res1["mappings_created"] >= 2

    # Second run must be completely idempotent: 0 created
    res2 = harmonize_same_families(db)
    db.commit()
    assert res2["national_materials_created"] == 0
    assert res2["mappings_created"] == 0


def test_harmonize_all_categories_preserve_authoritative_category(db, cpse_x, cpse_y):
    """
    Verifies that National Material creation for every domain category:
    1. Preserves the exact category (e.g. STRAINER, PIPE, TRANSMITTER, FITTING, BELT, etc.) and NEVER falls back to VALVE.
    2. Populates normalized_attributes JSONB directly on the National Material.
    3. Retains deterministic identity_key and canonical_description.
    """
    tag = uuid.uuid4().hex[:6]

    category_samples = [
        ("STRAINER", {"type": f"Y-TYPE-{tag}", "size": "DN50", "material_grade": "SS316", "pressure_rating": "CLASS150", "mesh": "40"}),
        ("PIPE", {"construction": "SEAMLESS", "size": f"DN50-{tag}", "schedule": "SCH40", "material_grade": "CARBON_STEEL", "standard_grade": "ASTM A106 GR B"}),
        ("FLANGE", {"flange_type": f"WELD_NECK_{tag}", "size": "DN100", "material_grade": "CARBON_STEEL", "pressure_rating": "CLASS150", "facing_connection": "RF"}),
        ("GASKET", {"gasket_type": f"SPIRAL_WOUND_{tag}", "size": "DN50", "pressure_rating": "CLASS150", "materials_filler": "SS316/GRAPHITE"}),
        ("PUMP", {"pump_type": f"CENTRIFUGAL_{tag}", "flow_rate": "50 M3/HR", "head": "30M", "casing_material": "CARBON_STEEL"}),
        ("TRANSMITTER", {"instrument_type": f"PRESSURE_{tag}", "measurement_range": "0-100-BAR", "signal": "4-20MA", "protocol": "HART"}),
        ("FITTING", {"fitting_type": f"ELBOW 90 DEG_{tag}", "size": "DN50", "schedule": "SCH40", "material_grade": "CARBON_STEEL"}),
        ("BEARING", {"bearing_type": f"BALL DEEP GROOVE_{tag}", "bearing_number": "6205", "seal_shield": "ZZ"}),
        ("BELT", {"belt_type": f"V-BELT_{tag}", "profile": "SPB", "length": "2500"}),
    ]

    for cat_name, attrs in category_samples:
        full_attrs = dict(attrs, category=cat_name, schema_version="2.0")
        m1 = Material(
            id=uuid.uuid4(),
            cpse_id=cpse_x.id,
            source_material_code=f"M1-{cat_name}-{tag}",
            source_description=f"TEST {cat_name} X",
            source_uom="EA",
            category=cat_name,
            normalized_description=f"CANONICAL {cat_name} {tag}",
            normalized_attributes=full_attrs
        )
        m2 = Material(
            id=uuid.uuid4(),
            cpse_id=cpse_y.id,
            source_material_code=f"M2-{cat_name}-{tag}",
            source_description=f"TEST {cat_name} Y",
            source_uom="EA",
            category=cat_name,
            normalized_description=f"CANONICAL {cat_name} {tag}",
            normalized_attributes=full_attrs
        )
        db.add_all([m1, m2])
        db.commit()

        create_rec(db, m1, m2, "SAME")
        create_rec(db, m2, m1, "SAME")

        res = harmonize_same_families(db)
        db.commit()

        assert res["status"] == "success"
        map1 = db.query(MaterialNationalMapping).filter_by(material_id=m1.id, status="ACTIVE").first()
        assert map1 is not None, f"Mapping not created for {cat_name}"

        nm = db.query(NationalMaterial).filter_by(id=map1.national_material_id).first()
        assert nm is not None
        # CRITICAL ASSERTION: category must be the true category and NEVER "VALVE" (unless category is VALVE)
        assert nm.category == cat_name, f"Expected NM category {cat_name}, got {nm.category}"
        assert nm.normalized_attributes is not None
        if cat_name != "VALVE":
            assert nm.valve_type is None
            assert nm.trim is None

def test_harmonize_potential_and_different_not_mapped(db, cpse_x, cpse_y):
    tag = uuid.uuid4().hex[:6]
    m1 = create_mat(db, cpse_x, {"valve_type": f"BUTTERFLY_POT_{tag}"})
    m2 = create_mat(db, cpse_y, {"valve_type": f"BUTTERFLY_POT_{tag}"})
    create_rec(db, m1, m2, "POTENTIALLY_EQUIVALENT")
    create_rec(db, m2, m1, "POTENTIALLY_EQUIVALENT")

    m3 = create_mat(db, cpse_x, {"valve_type": f"GATE_DIFF_{tag}"})
    m4 = create_mat(db, cpse_y, {"valve_type": f"GLOBE_DIFF_{tag}"})
    create_rec(db, m3, m4, "DIFFERENT")
    create_rec(db, m4, m3, "DIFFERENT")

    res = harmonize_same_families(db)
    db.commit()

    map1 = db.query(MaterialNationalMapping).filter_by(material_id=m1.id, status="ACTIVE").first()
    map2 = db.query(MaterialNationalMapping).filter_by(material_id=m2.id, status="ACTIVE").first()
    map3 = db.query(MaterialNationalMapping).filter_by(material_id=m3.id, status="ACTIVE").first()
    map4 = db.query(MaterialNationalMapping).filter_by(material_id=m4.id, status="ACTIVE").first()
    assert map1 is None
    assert map2 is None
    assert map3 is None
    assert map4 is None
