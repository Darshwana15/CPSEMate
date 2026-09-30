import pytest
import uuid
from app.models import CPSE, Material
from app.services.matching import classify_match, generate_candidates, get_material_category
from app.services.ai.validation import EngineeringKnowledgeEngine
from app.services.ai.profile import MaterialProfile
from app.services.ai.explainability import MaterialExplanationService

@pytest.fixture
def cpse_alpha(db):
    c = CPSE(code=f"CPSE-ALPHA-{uuid.uuid4()}", name="ALPHA")
    db.add(c)
    db.commit()
    db.refresh(c)
    return c

@pytest.fixture
def cpse_beta(db):
    c = CPSE(code=f"CPSE-BETA-{uuid.uuid4()}", name="BETA")
    db.add(c)
    db.commit()
    db.refresh(c)
    return c

def test_strainer_mesh_conflict():
    """Strainer A (mesh 40) vs Strainer C (mesh 80) must be DIFFERENT with mesh conflict."""
    m_src = Material(
        id=uuid.uuid4(),
        cpse_id=uuid.uuid4(),
        source_material_code="A-134",
        source_description='Y-STRAINER 2" 150# SS316 40 MESH',
        normalized_description="STRAINER Y-TYPE DN50 CLASS150 SS316 MESH40",
        normalized_attributes={
            "category": "STRAINER",
            "type": "Y-TYPE",
            "size": "DN50",
            "pressure_rating": "CLASS150",
            "material_grade": "SS316",
            "mesh": "40"
        }
    )

    m_cand = Material(
        id=uuid.uuid4(),
        cpse_id=uuid.uuid4(),
        source_material_code="C-335",
        source_description="STRAINER Y-TYPE 2 IN CLASS 150 SS316 MESH 80",
        normalized_description="STRAINER Y-TYPE DN50 CLASS150 SS316 MESH80",
        normalized_attributes={
            "category": "STRAINER",
            "type": "Y-TYPE",
            "size": "DN50",
            "pressure_rating": "CLASS150",
            "material_grade": "SS316",
            "mesh": "80"
        }
    )

    res = classify_match(m_src, m_cand)
    assert res["classification"] == "DIFFERENT"
    assert res["confidence"] == 0.0
    assert "mesh conflict" in res["explanation"].lower()
    assert "40 vs 80" in res["explanation"]

def test_strainer_identical_mesh():
    """Strainer A (mesh 40) vs Strainer B (mesh 40) must match as SAME."""
    m_src = Material(
        id=uuid.uuid4(),
        cpse_id=uuid.uuid4(),
        source_material_code="A-134",
        source_description='Y-STRAINER 2" 150# SS316 40 MESH',
        normalized_description="STRAINER Y-TYPE DN50 CLASS150 SS316 MESH40",
        normalized_attributes={
            "category": "STRAINER",
            "type": "Y-TYPE",
            "size": "DN50",
            "pressure_rating": "CLASS150",
            "material_grade": "SS316",
            "mesh": "40"
        }
    )

    m_cand = Material(
        id=uuid.uuid4(),
        cpse_id=uuid.uuid4(),
        source_material_code="B-231",
        source_description="Y-STRAINER DN50 150# AISI 316 40 MESH",
        normalized_description="STRAINER Y-TYPE DN50 CLASS150 SS316 MESH40",
        normalized_attributes={
            "category": "STRAINER",
            "type": "Y-TYPE",
            "size": "DN50",
            "pressure_rating": "CLASS150",
            "material_grade": "SS316",
            "mesh": "40"
        }
    )

    res = classify_match(m_src, m_cand)
    assert res["classification"] == "SAME"
    assert res["confidence"] >= 0.90
    assert "Same strainer type, size, pressure rating, material grade and mesh" in res["explanation"]

def test_category_conflict_between_different_equipment():
    """A Strainer and a Valve should immediately conflict at category level."""
    m_strainer = Material(
        id=uuid.uuid4(),
        cpse_id=uuid.uuid4(),
        source_material_code="ST-1",
        source_description="Y-STRAINER DN50",
        normalized_attributes={"category": "STRAINER", "type": "Y-TYPE", "size": "DN50"}
    )
    m_valve = Material(
        id=uuid.uuid4(),
        cpse_id=uuid.uuid4(),
        source_material_code="VL-1",
        category="VALVE",
        source_description="BALL VALVE DN50",
        normalized_attributes={"category": "VALVE", "valve_type": "BALL", "size": "DN50"}
    )

    res = classify_match(m_strainer, m_valve)
    assert res["classification"] == "DIFFERENT"
    assert res["confidence"] == 0.0
    assert "category conflict" in res["explanation"].lower() or "category mismatch" in res["explanation"].lower()

def test_gasket_matching():
    """Test GASKET category matching."""
    g1 = Material(
        id=uuid.uuid4(),
        cpse_id=uuid.uuid4(),
        source_material_code="G-1",
        category="GASKET",
        normalized_description="GASKET SPIRAL_WOUND DN50 CLASS150 SS316/GRAPHITE",
        normalized_attributes={
            "category": "GASKET",
            "gasket_type": "SPIRAL_WOUND",
            "size": "DN50",
            "pressure_rating": "CLASS150",
            "materials_filler": "SS316/GRAPHITE"
        }
    )
    g2 = Material(
        id=uuid.uuid4(),
        cpse_id=uuid.uuid4(),
        source_material_code="G-2",
        category="GASKET",
        normalized_description="GASKET SPIRAL_WOUND DN50 CLASS150 SS316/GRAPHITE",
        normalized_attributes={
            "category": "GASKET",
            "gasket_type": "SPIRAL_WOUND",
            "size": "DN50",
            "pressure_rating": "CLASS150",
            "materials_filler": "SS316/GRAPHITE"
        }
    )
    res = classify_match(g1, g2)
    assert res["classification"] == "SAME"
    assert res["confidence"] >= 0.90
    assert "gasket type" in res["explanation"].lower()

    # Pressure conflict
    g3 = Material(
        id=uuid.uuid4(),
        cpse_id=uuid.uuid4(),
        source_material_code="G-3",
        category="GASKET",
        normalized_attributes={
            "category": "GASKET",
            "gasket_type": "SPIRAL_WOUND",
            "size": "DN50",
            "pressure_rating": "CLASS300",
            "materials_filler": "SS316/GRAPHITE"
        }
    )
    res_diff = classify_match(g1, g3)
    assert res_diff["classification"] == "DIFFERENT"
    assert "pressure rating conflict" in res_diff["explanation"].lower()

def test_bearing_matching():
    """Test BEARING category matching."""
    b1 = Material(
        id=uuid.uuid4(),
        cpse_id=uuid.uuid4(),
        source_material_code="B-1",
        category="BEARING",
        normalized_description="BEARING BALL DEEP GROOVE 6205 2RS",
        normalized_attributes={
            "category": "BEARING",
            "bearing_type": "BALL DEEP GROOVE",
            "bearing_number": "6205",
            "seal_shield": "2RS"
        }
    )
    b2 = Material(
        id=uuid.uuid4(),
        cpse_id=uuid.uuid4(),
        source_material_code="B-2",
        category="BEARING",
        normalized_description="BEARING BALL DEEP GROOVE 6205 2RS",
        normalized_attributes={
            "category": "BEARING",
            "bearing_type": "BALL DEEP GROOVE",
            "bearing_number": "6205",
            "seal_shield": "2RS"
        }
    )
    res = classify_match(b1, b2)
    assert res["classification"] == "SAME"
    assert res["confidence"] >= 0.90

    # Differing bearing number
    b3 = Material(
        id=uuid.uuid4(),
        cpse_id=uuid.uuid4(),
        source_material_code="B-3",
        category="BEARING",
        normalized_attributes={
            "category": "BEARING",
            "bearing_type": "BALL DEEP GROOVE",
            "bearing_number": "6206",
            "seal_shield": "2RS"
        }
    )
    res_diff = classify_match(b1, b3)
    assert res_diff["classification"] == "DIFFERENT"
    assert "bearing number conflict" in res_diff["explanation"].lower()

def test_generate_candidates_isolates_non_valve_categories(db, cpse_alpha, cpse_beta):
    """Ensure candidate generation pulls only matching category for non-valve materials."""
    st_alpha = Material(
        id=uuid.uuid4(),
        cpse_id=cpse_alpha.id,
        source_material_code=f"ST-A-{uuid.uuid4()}",
        source_description='Y-STRAINER 2" 150#',
        source_uom="EA",
        normalized_attributes={"category": "STRAINER", "type": "Y-TYPE", "size": "DN50"}
    )
    db.add(st_alpha)

    # Strainer in CPSE Beta
    st_beta = Material(
        id=uuid.uuid4(),
        cpse_id=cpse_beta.id,
        source_material_code=f"ST-B-{uuid.uuid4()}",
        source_description="Y-STRAINER DN50 150#",
        source_uom="EA",
        normalized_attributes={"category": "STRAINER", "type": "Y-TYPE", "size": "DN50"}
    )
    db.add(st_beta)

    # Bearing in CPSE Beta (NULL category column, category in JSON)
    br_beta = Material(
        id=uuid.uuid4(),
        cpse_id=cpse_beta.id,
        source_material_code=f"BR-B-{uuid.uuid4()}",
        source_description="BEARING 6205",
        source_uom="EA",
        normalized_attributes={"category": "BEARING", "bearing_number": "6205"}
    )
    db.add(br_beta)
    db.commit()

    candidates = generate_candidates(db, st_alpha)
    cand_ids = [c.id for c in candidates]

    assert st_beta.id in cand_ids
    assert br_beta.id not in cand_ids

def test_engineering_validation_and_explainability_for_strainers():
    """Verify EngineeringKnowledgeEngine and MaterialExplanationService for strainers."""
    s1 = Material(
        id=uuid.uuid4(),
        cpse_id=uuid.uuid4(),
        source_material_code="S-1",
        source_description="STRAINER 2 INCH 150# MESH 40",
        normalized_attributes={"category": "STRAINER", "type": "Y-TYPE", "size": "DN50", "pressure_rating": "CLASS150", "mesh": "40"}
    )
    s2 = Material(
        id=uuid.uuid4(),
        cpse_id=uuid.uuid4(),
        source_material_code="S-2",
        source_description="STRAINER 2 INCH 150# MESH 80",
        normalized_attributes={"category": "STRAINER", "type": "Y-TYPE", "size": "DN50", "pressure_rating": "CLASS150", "mesh": "80"}
    )

    val_res = EngineeringKnowledgeEngine.validate_materials(s1, s2)
    assert not val_res.is_compatible
    assert any("mesh conflict" in c.lower() for c in val_res.hard_conflicts)

    svc = MaterialExplanationService()
    exp = svc.generate_explanation(s1, s2)
    assert exp.classification == "DIFFERENT"
    assert any(c.attribute == "mesh" for c in exp.engineering_conflicts)
    assert any(item.attribute == "mesh" for item in exp.attribute_comparisons)
