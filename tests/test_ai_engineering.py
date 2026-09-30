import pytest

from app.services.ai.profile import MaterialProfile, ProfileAttribute
from app.services.ai.validation import EngineeringKnowledgeEngine, ValidationResult


def test_metallurgy_conflicts_and_synonyms():
    # 1. Exact match via synonym (WCB == CARBON_STEEL)
    p1 = MaterialProfile(material_grade=ProfileAttribute.known("WCB"))
    p2 = MaterialProfile(material_grade=ProfileAttribute.known("CARBON STEEL"))
    res = EngineeringKnowledgeEngine.validate_profiles(p1, p2)
    assert res.is_compatible is True
    assert "material_grade" in res.matching_attributes

    # 2. Hard conflict: Carbon Steel vs SS316
    p3 = MaterialProfile(material_grade=ProfileAttribute.known("SS316"))
    res_cs_ss = EngineeringKnowledgeEngine.validate_profiles(p1, p3)
    assert res_cs_ss.is_compatible is False
    assert any("metallurgy conflict" in c.lower() for c in res_cs_ss.hard_conflicts)

    # 3. Hard conflict: SS304 vs SS316
    p4 = MaterialProfile(material_grade=ProfileAttribute.known("SS304"))
    res_304_316 = EngineeringKnowledgeEngine.validate_profiles(p3, p4)
    assert res_304_316.is_compatible is False
    assert any("metallurgy conflict" in c.lower() for c in res_304_316.hard_conflicts)


def test_size_conflicts_and_conversions():
    # 1. 2 IN vs DN50 (Equivalent)
    p1 = MaterialProfile(size=ProfileAttribute.known("2 IN"))
    p2 = MaterialProfile(size=ProfileAttribute.known("DN50"))
    res = EngineeringKnowledgeEngine.validate_profiles(p1, p2)
    assert res.is_compatible is True
    assert "size" in res.matching_attributes

    # 2. DN50 vs DN100 (Conflict)
    p3 = MaterialProfile(size=ProfileAttribute.known("DN100"))
    res_diff = EngineeringKnowledgeEngine.validate_profiles(p2, p3)
    assert res_diff.is_compatible is False
    assert any("size conflict" in c.lower() for c in res_diff.hard_conflicts)


def test_pressure_rating_conflicts():
    # 1. 150# vs CLASS150 (Equivalent)
    p1 = MaterialProfile(pressure_rating=ProfileAttribute.known("150#"))
    p2 = MaterialProfile(pressure_rating=ProfileAttribute.known("CLASS150"))
    res = EngineeringKnowledgeEngine.validate_profiles(p1, p2)
    assert res.is_compatible is True
    assert "pressure_rating" in res.matching_attributes

    # 2. 150 PSI vs 6000 PSI (Conflict)
    p_low = MaterialProfile(pressure_rating=ProfileAttribute.known("150 PSI"))
    p_high = MaterialProfile(pressure_rating=ProfileAttribute.known("6000 PSI"))
    res_press = EngineeringKnowledgeEngine.validate_profiles(p_low, p_high)
    assert res_press.is_compatible is False
    assert any("pressure rating conflict" in c.lower() for c in res_press.hard_conflicts)

    # 3. CLASS150 vs CLASS300 (Conflict)
    p3 = MaterialProfile(pressure_rating=ProfileAttribute.known("CLASS300"))
    res_cl = EngineeringKnowledgeEngine.validate_profiles(p2, p3)
    assert res_cl.is_compatible is False


def test_equipment_and_connection_conflicts():
    # 1. BALL vs GATE valve conflict
    p_ball = MaterialProfile(material_type=ProfileAttribute.known("BALL"))
    p_gate = MaterialProfile(material_type=ProfileAttribute.known("GATE"))
    res_type = EngineeringKnowledgeEngine.validate_profiles(p_ball, p_gate)
    assert res_type.is_compatible is False
    assert any("type conflict" in c.lower() for c in res_type.hard_conflicts)

    # 2. NPT vs FLANGED connection conflict
    p_npt = MaterialProfile(connection_type=ProfileAttribute.known("NPT"))
    p_flg = MaterialProfile(connection_type=ProfileAttribute.known("FLANGED"))
    res_conn = EngineeringKnowledgeEngine.validate_profiles(p_npt, p_flg)
    assert res_conn.is_compatible is False
    assert any("connection type conflict" in c.lower() for c in res_conn.hard_conflicts)


def test_asymmetric_missing_attributes():
    # Source has trim SS316, Candidate has NOT_PRESENT
    p_src = MaterialProfile(
        category=ProfileAttribute.known("VALVE"),
        size=ProfileAttribute.known("DN50"),
        trim_material=ProfileAttribute.known("SS316"),
    )
    p_cand = MaterialProfile(
        category=ProfileAttribute.known("VALVE"),
        size=ProfileAttribute.known("DN50"),
        trim_material=ProfileAttribute.not_present(),
    )
    res = EngineeringKnowledgeEngine.validate_profiles(p_src, p_cand)
    # No hard conflict, but asymmetric missing attribute
    assert res.is_compatible is True
    assert "trim_material" in res.asymmetric_attributes
    assert "size" in res.matching_attributes

