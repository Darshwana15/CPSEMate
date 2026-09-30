import pytest
from app.services.ai.profile import (
    AttributeState,
    MaterialProfile,
    ProfileAttribute,
)


def test_profile_attribute_states():
    # 1. KNOWN_VALUE
    attr_known = ProfileAttribute.known("SS316", raw_token="316SS", confidence=0.95)
    assert attr_known.state == AttributeState.KNOWN_VALUE
    assert attr_known.value == "SS316"
    assert attr_known.raw_token == "316SS"
    assert attr_known.is_known is True
    assert attr_known.confidence == 0.95

    # 2. UNKNOWN
    attr_unknown = ProfileAttribute.unknown(raw_token="UNSPECIFIED")
    assert attr_unknown.state == AttributeState.UNKNOWN
    assert attr_unknown.value is None
    assert attr_unknown.raw_token == "UNSPECIFIED"
    assert attr_unknown.is_known is False

    # 3. NOT_PRESENT
    attr_np = ProfileAttribute.not_present()
    assert attr_np.state == AttributeState.NOT_PRESENT
    assert attr_np.value is None
    assert attr_np.is_known is False

    # 4. CONFLICTING
    attr_conf = ProfileAttribute.conflicting(raw_token="DN50 4 IN")
    assert attr_conf.state == AttributeState.CONFLICTING
    assert attr_conf.value is None
    assert attr_conf.is_known is False


def test_material_profile_serialization_roundtrip():
    profile = MaterialProfile(
        category=ProfileAttribute.known("VALVE"),
        material_type=ProfileAttribute.known("NEEDLE"),
        component_type=ProfileAttribute.known("NEEDLE VALVE"),
        size=ProfileAttribute.known("DN15"),
        pressure_rating=ProfileAttribute.known("6000PSI"),
        material_grade=ProfileAttribute.known("SS316"),
        connection_type=ProfileAttribute.known("NPT"),
        trim_material=ProfileAttribute.known("SS316"),
        normalized_uom=ProfileAttribute.known("EACH"),
        extraction_confidence=0.98,
        provenance_tokens=["NEEDLE", "VALVE", "1/2 IN", "SS316", "6000PSI", "NPT"],
    )

    data = profile.to_dict()
    assert data["schema_version"] == "2.0"
    assert data["category"]["value"] == "VALVE"
    assert data["pressure_rating"]["value"] == "6000PSI"

    # Reconstruct from dict
    reconstructed = MaterialProfile.from_dict(data)
    assert reconstructed.category.value == "VALVE"
    assert reconstructed.material_type.value == "NEEDLE"
    assert reconstructed.size.value == "DN15"
    assert reconstructed.pressure_rating.value == "6000PSI"
    assert reconstructed.material_grade.value == "SS316"
    assert reconstructed.connection_type.value == "NPT"
    assert reconstructed.trim_material.value == "SS316"
    assert reconstructed.normalized_uom.value == "EACH"
    assert reconstructed.has_complete_identity() is True


def test_canonical_string_generation():
    profile = MaterialProfile(
        category=ProfileAttribute.known("VALVE"),
        material_type=ProfileAttribute.known("BALL"),
        size=ProfileAttribute.known("DN50"),
        material_grade=ProfileAttribute.known("CARBON_STEEL"),
        pressure_rating=ProfileAttribute.known("CLASS300"),
        connection_type=ProfileAttribute.known("RF"),
        trim_material=ProfileAttribute.known("SS304"),
    )
    canonical = profile.to_canonical_string()
    assert "VALVE" in canonical
    assert "BALL" in canonical
    assert "DN50" in canonical
    assert "CARBON_STEEL" in canonical
    assert "CLASS300" in canonical
    assert "RF" in canonical
    assert "TRIM SS304" in canonical


def test_missing_attributes_and_incomplete_identity():
    # Trim is missing (NOT_PRESENT)
    profile = MaterialProfile(
        category=ProfileAttribute.known("VALVE"),
        material_type=ProfileAttribute.known("BALL"),
        size=ProfileAttribute.known("DN50"),
        material_grade=ProfileAttribute.known("CARBON_STEEL"),
        pressure_rating=ProfileAttribute.known("CLASS150"),
        connection_type=ProfileAttribute.known("RF"),
        trim_material=ProfileAttribute.not_present(),
    )
    assert profile.has_complete_identity() is False
    missing = profile.get_missing_attributes()
    assert "trim_material" in missing
    assert "size" not in missing


def test_from_material_fallback_simulation():
    class MockMaterial:
        category = "VALVE"
        valve_type = "GATE"
        size = "DN100"
        body_material = "CARBON_STEEL"
        pressure_class = "CLASS150"
        connection_type = "RF"
        trim = "SS316"
        normalized_uom = "EACH"
        normalized_attributes = None

    mock_mat = MockMaterial()
    profile = MaterialProfile.from_material(mock_mat)
    assert profile.category.value == "VALVE"
    assert profile.material_type.value == "GATE"
    assert profile.size.value == "DN100"
    assert profile.pressure_rating.value == "CLASS150"
    assert profile.material_grade.value == "CARBON_STEEL"
    assert profile.trim_material.value == "SS316"
    assert profile.has_complete_identity() is True

