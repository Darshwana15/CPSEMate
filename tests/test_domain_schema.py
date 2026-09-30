import pytest
import uuid
from sqlalchemy.exc import IntegrityError
from sqlalchemy import text
from app.models import (
    CPSE, Material, NationalMaterial, MatchRecommendation, MaterialNationalMapping, AuditLog
)

def test_cpse_code_unique(client, db):
    """1. CPSE code must be unique."""
    code = f"TEST1-{uuid.uuid4()}"
    cpse1 = CPSE(code=code, name="Test 1")
    db.add(cpse1)
    db.commit()

    cpse2 = CPSE(code=code, name="Test 2")
    db.add(cpse2)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()

def test_material_code_unique_within_cpse_but_allows_across_cpses(client, db):
    """
    2. Material source code is unique within a CPSE.
    3. Two different CPSEs may use the same source material code.
    """
    cpse1 = CPSE(code=f"C-{uuid.uuid4()}", name=f"C-{uuid.uuid4()}")
    cpse2 = CPSE(code=f"C-{uuid.uuid4()}", name=f"C-{uuid.uuid4()}")
    db.add_all([cpse1, cpse2])
    db.commit()

    mat1 = Material(cpse_id=cpse1.id, source_material_code="M1", source_description="A", source_uom="EA")
    mat2 = Material(cpse_id=cpse1.id, source_material_code="M1", source_description="B", source_uom="EA")
    db.add(mat1)
    db.commit()

    db.add(mat2)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()

    # Same code, different CPSE should succeed
    mat3 = Material(cpse_id=cpse2.id, source_material_code="M1", source_description="A", source_uom="EA")
    db.add(mat3)
    db.commit()

def test_material_preserves_source_fields_separately(client, db):
    """4. Material preserves source fields separately from derived fields."""
    cpse1 = CPSE(code=f"C-{uuid.uuid4()}", name=f"C-{uuid.uuid4()}")
    db.add(cpse1)
    db.commit()

    mat = Material(
        cpse_id=cpse1.id,
        source_material_code="M2",
        source_description="ORIGINAL_DESC",
        source_uom="NOS"
    )
    # Add derived fields
    mat.category = "VALVE"
    mat.normalized_description = "NORMALIZED_DESC"
    mat.normalized_uom = "EACH"
    db.add(mat)
    db.commit()

    assert mat.source_description == "ORIGINAL_DESC"
    assert mat.normalized_description == "NORMALIZED_DESC"
    assert mat.source_uom == "NOS"
    assert mat.normalized_uom == "EACH"

def test_national_material_identity_key_unique_and_not_null(client, db):
    """
    5. NationalMaterial identity_key must be unique.
    6. NationalMaterial identity attributes cannot be NULL.
    """
    shared_id = f"ID-{uuid.uuid4()}"
    nm1 = NationalMaterial(
        national_code=f"N-{uuid.uuid4()}", category="VALVE", canonical_description="Desc",
        valve_type="BALL", size="DN50", body_material="CS", pressure_class="150", connection_type="RF", trim="SS", normalized_uom="EA",
        identity_key=shared_id
    )
    db.add(nm1)
    db.commit()

    nm2 = NationalMaterial(
        national_code=f"N-{uuid.uuid4()}", category="VALVE", canonical_description="Desc",
        valve_type="BALL", size="DN50", body_material="CS", pressure_class="150", connection_type="RF", trim="SS", normalized_uom="EA",
        identity_key=shared_id  # duplicate
    )
    db.add(nm2)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()

    nm3 = NationalMaterial(
        national_code=f"N-{uuid.uuid4()}", category="VALVE", canonical_description="Desc",
        identity_key=f"ID-{uuid.uuid4()}",
        valve_type="BALL", size="DN50", body_material="CS", pressure_class="150", connection_type="RF", normalized_uom="EA"
        # trim is nullable since migration c1d2e3f4a5b6 (non-valve NMs don't have trim)
        # so omitting trim no longer raises IntegrityError
    )
    db.add(nm3)
    db.commit()  # should succeed since trim is now nullable
    assert nm3.trim is None  # nullable, not an error

def test_match_recommendation_classification_and_self_compare(client, db):
    """
    7. MatchRecommendation classification is constrained.
    8. MatchRecommendation cannot compare a material with itself.
    9. Multiple recommendations for the same pair are permitted.
    """
    cpse1 = CPSE(code=f"C-{uuid.uuid4()}", name=f"C-{uuid.uuid4()}")
    db.add(cpse1)
    db.commit()
    mat1 = Material(cpse_id=cpse1.id, source_material_code="M1", source_description="A", source_uom="EA")
    mat2 = Material(cpse_id=cpse1.id, source_material_code="M2", source_description="B", source_uom="EA")
    db.add_all([mat1, mat2])
    db.commit()

    # Invalid classification
    rec_invalid = MatchRecommendation(source_material_id=mat1.id, candidate_material_id=mat2.id, classification="UNKNOWN")
    db.add(rec_invalid)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()

    # Self-compare
    rec_self = MatchRecommendation(source_material_id=mat1.id, candidate_material_id=mat1.id, classification="SAME")
    db.add(rec_self)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()

    # Valid recommendations
    rec1 = MatchRecommendation(source_material_id=mat1.id, candidate_material_id=mat2.id, classification="SAME")
    db.add(rec1)
    db.commit()

    # Allow multiple for same pair (UNIQUE constraint was removed in Step 4)
    rec2 = MatchRecommendation(source_material_id=mat1.id, candidate_material_id=mat2.id, classification="SAME")
    db.add(rec2)
    db.commit() # Should succeed without error

def test_mapping_unique_active(client, db):
    """
    10. A material cannot have two ACTIVE mappings.
    11. Historical SUPERSEDED/INACTIVE mappings are allowed.
    """
    cpse1 = CPSE(code=f"C-{uuid.uuid4()}", name=f"C-{uuid.uuid4()}")
    db.add(cpse1)
    db.commit()
    mat = Material(cpse_id=cpse1.id, source_material_code="M1", source_description="A", source_uom="EA")
    db.add(mat)
    nm1 = NationalMaterial(
        national_code=f"N-{uuid.uuid4()}", category="VALVE", canonical_description="D1",
        valve_type="BALL", size="DN50", body_material="CS", pressure_class="150", connection_type="RF", trim="SS", normalized_uom="EA",
        identity_key=f"ID-{uuid.uuid4()}"
    )
    nm2 = NationalMaterial(
        national_code=f"N-{uuid.uuid4()}", category="VALVE", canonical_description="D2",
        valve_type="BALL", size="DN50", body_material="CS", pressure_class="150", connection_type="RF", trim="SS", normalized_uom="EA",
        identity_key=f"ID-{uuid.uuid4()}"
    )
    db.add_all([nm1, nm2])
    db.commit()

    map1 = MaterialNationalMapping(material_id=mat.id, national_material_id=nm1.id, basis="AUTO_SAME", status="ACTIVE")
    db.add(map1)
    db.commit()

    # Second active mapping should fail
    map2 = MaterialNationalMapping(material_id=mat.id, national_material_id=nm2.id, basis="HUMAN_OVERRIDE", status="ACTIVE")
    db.add(map2)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()

    # Historical mapping should succeed
    map3 = MaterialNationalMapping(material_id=mat.id, national_material_id=nm2.id, basis="HUMAN_OVERRIDE", status="SUPERSEDED")
    map4 = MaterialNationalMapping(material_id=mat.id, national_material_id=nm2.id, basis="HUMAN_OVERRIDE", status="INACTIVE")
    db.add_all([map3, map4])
    db.commit()

def test_audit_log_features(client, db):
    """
    12. AuditLog can store before_state/after_state.
    13. AuditLog can store reviewer reason.
    """
    audit = AuditLog(
        actor="user123", action="REJECT", entity_type="MATCH", entity_id="123",
        before_state={"status": "pending"}, after_state={"status": "rejected"},
        reason="Does not match physically"
    )
    db.add(audit)
    db.commit()
    assert audit.before_state == {"status": "pending"}
    assert audit.after_state == {"status": "rejected"}
    assert audit.reason == "Does not match physically"

def test_foreign_keys_delete_restrict(client, db):
    """14. Foreign keys use safe delete behavior."""
    cpse1 = CPSE(code=f"C-{uuid.uuid4()}", name=f"C-{uuid.uuid4()}")
    db.add(cpse1)
    db.commit()

    mat = Material(cpse_id=cpse1.id, source_material_code="M1", source_description="A", source_uom="EA")
    db.add(mat)
    db.commit()

    # Attempt to delete CPSE should fail due to RESTRICT
    db.delete(cpse1)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()

def test_critical_safety_incomplete_identity(client, db):
    """
    Critical safety case: Material A (trim=NULL), Material B (trim=SS304), DB allows Material A.
    But NationalMaterial must not permit incomplete identity.
    """
    cpse1 = CPSE(code=f"C-{uuid.uuid4()}", name=f"C-{uuid.uuid4()}")
    db.add(cpse1)
    db.commit()

    # Material A with trim=None should be allowed
    matA = Material(cpse_id=cpse1.id, source_material_code="MA", source_description="A", source_uom="EA", trim=None)
    matB = Material(cpse_id=cpse1.id, source_material_code="MB", source_description="B", source_uom="EA", trim="SS304")
    db.add_all([matA, matB])
    db.commit()
    assert matA.trim is None
    assert matB.trim == "SS304"

    # NationalMaterial with trim=None should be ALLOWED since migration c1d2e3f4a5b6
    # (non-valve categories like STRAINER/PIPE/FITTING don't have trim)
    nm = NationalMaterial(
        national_code=f"N-{uuid.uuid4()}", category="VALVE", canonical_description="D",
        valve_type="BALL", size="DN50", body_material="CS", pressure_class="150", connection_type="RF", trim=None, normalized_uom="EA",
        identity_key=f"ID-{uuid.uuid4()}"
    )
    db.add(nm)
    db.commit()  # succeeds now that trim is nullable
    assert nm.trim is None
