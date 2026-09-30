import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import CPSE, Material, NationalMaterial, MatchRecommendation, MaterialNationalMapping, AuditLog

REVIEWER_TOKEN = "mvp-secret-token"
AUTH_HEADERS = {"X-Reviewer-Token": REVIEWER_TOKEN}


def create_test_fixture(db: Session):
    """
    Creates a rich fixture with:
    - 2 CPSEs (CPSE_A, CPSE_B)
    - 3 Materials: Mat_A1, Mat_A2 in CPSE_A; Mat_B1 in CPSE_B
    - 1 NationalMaterial shared by Mat_A1 and Mat_B1
    - Mappings: Mat_A1 -> NM, Mat_B1 -> NM
    - Recommendations: Mat_A1 <-> Mat_B1 (SAME), Mat_A1 <-> Mat_A2 (POTENTIAL)
    - AuditLog entries for Mat_A1, CPSE_A
    """
    # 1. CPSEs
    cpse_a = CPSE(id=uuid.uuid4(), code=f"TEST-A-{uuid.uuid4().hex[:6]}", name="Test CPSE A")
    cpse_b = CPSE(id=uuid.uuid4(), code=f"TEST-B-{uuid.uuid4().hex[:6]}", name="Test CPSE B")
    db.add_all([cpse_a, cpse_b])
    db.flush()

    # 2. Materials
    mat_a1 = Material(
        id=uuid.uuid4(),
        cpse_id=cpse_a.id,
        source_material_code="MA-01",
        source_description="Test Valve A1",
        source_uom="EA",
        category="VALVE",
    )
    mat_a2 = Material(
        id=uuid.uuid4(),
        cpse_id=cpse_a.id,
        source_material_code="MA-02",
        source_description="Test Valve A2",
        source_uom="EA",
        category="VALVE",
    )
    mat_b1 = Material(
        id=uuid.uuid4(),
        cpse_id=cpse_b.id,
        source_material_code="MB-01",
        source_description="Test Valve B1",
        source_uom="EA",
        category="VALVE",
    )
    db.add_all([mat_a1, mat_a2, mat_b1])
    db.flush()

    # 3. National Material
    nm = NationalMaterial(
        id=uuid.uuid4(),
        national_code=f"NM-{uuid.uuid4().hex[:8].upper()}",
        category="VALVE",
        canonical_description="TEST CANONICAL VALVE",
        valve_type="BALL",
        size="DN50",
        body_material="CARBON_STEEL",
        pressure_class="CLASS300",
        connection_type="RF",
        trim="SS304",
        normalized_uom="EACH",
        identity_key=f"TEST_KEY_{uuid.uuid4().hex}",
        status="ACTIVE",
    )
    db.add(nm)
    db.flush()

    # 4. Recommendations
    rec_ab = MatchRecommendation(
        id=uuid.uuid4(),
        source_material_id=mat_a1.id,
        candidate_material_id=mat_b1.id,
        classification="SAME",
        confidence=0.95,
        explanation="Test match A1 vs B1",
    )
    rec_aa = MatchRecommendation(
        id=uuid.uuid4(),
        source_material_id=mat_a1.id,
        candidate_material_id=mat_a2.id,
        classification="POTENTIALLY_EQUIVALENT",
        confidence=0.70,
        explanation="Test match A1 vs A2",
    )
    db.add_all([rec_ab, rec_aa])
    db.flush()

    # 5. Mappings
    map_a1 = MaterialNationalMapping(
        id=uuid.uuid4(),
        material_id=mat_a1.id,
        national_material_id=nm.id,
        basis="AUTO_SAME",
        status="ACTIVE",
        recommendation_id=rec_ab.id,
    )
    map_b1 = MaterialNationalMapping(
        id=uuid.uuid4(),
        material_id=mat_b1.id,
        national_material_id=nm.id,
        basis="AUTO_SAME",
        status="ACTIVE",
    )
    db.add_all([map_a1, map_b1])
    db.flush()

    # 6. AuditLog entries
    audit_a = AuditLog(
        id=uuid.uuid4(),
        actor="system",
        action="IMPORT",
        entity_type="CPSE",
        entity_id=str(cpse_a.id),
        before_state=None,
        after_state={"name": "Test CPSE A"},
        reason="Initial setup",
    )
    audit_mat = AuditLog(
        id=uuid.uuid4(),
        actor="system",
        action="IMPORT",
        entity_type="MATERIAL",
        entity_id=str(mat_a1.id),
        before_state=None,
        after_state={"code": "MA-01"},
        reason="Initial ingestion",
    )
    db.add_all([audit_a, audit_mat])
    db.commit()

    return {
        "cpse_a": cpse_a,
        "cpse_b": cpse_b,
        "mat_a1": mat_a1,
        "mat_a2": mat_a2,
        "mat_b1": mat_b1,
        "nm": nm,
        "rec_ab": rec_ab,
        "rec_aa": rec_aa,
        "map_a1": map_a1,
        "map_b1": map_b1,
        "audit_a": audit_a,
        "audit_mat": audit_mat,
    }


def test_delete_cpse_auth_required(client: TestClient, db: Session):
    """DELETE /cpses/{id} requires valid reviewer token."""
    fixtures = create_test_fixture(db)
    cpse_id = str(fixtures["cpse_a"].id)

    # 1. No token
    res_no_auth = client.delete(f"/api/v1/cpses/{cpse_id}")
    assert res_no_auth.status_code == 401

    # 2. Invalid token
    res_bad_auth = client.delete(
        f"/api/v1/cpses/{cpse_id}",
        headers={"X-Reviewer-Token": "wrong-token"}
    )
    assert res_bad_auth.status_code == 401


def test_delete_cpse_not_found(client: TestClient):
    """DELETE /cpses/{id} returns 404 for non-existent CPSE."""
    random_id = str(uuid.uuid4())
    res = client.delete(f"/api/v1/cpses/{random_id}", headers=AUTH_HEADERS)
    assert res.status_code == 404
    assert res.json()["detail"] == "CPSE not found"


def test_delete_cpse_success_and_cleanup(client: TestClient, db: Session):
    """
    DELETE /cpses/{id} successfully:
    1. Removes the CPSE
    2. Removes all Materials belonging to the CPSE
    3. Removes dependent MatchRecommendations (both as source and as candidate)
    4. Removes dependent MaterialNationalMappings
    5. Preserves NationalMaterial
    6. Preserves AuditLog records
    7. Preserves unrelated CPSE and its materials/mappings
    """
    fixtures = create_test_fixture(db)
    cpse_a_id = fixtures["cpse_a"].id
    cpse_b_id = fixtures["cpse_b"].id
    mat_a1_id = fixtures["mat_a1"].id
    mat_a2_id = fixtures["mat_a2"].id
    mat_b1_id = fixtures["mat_b1"].id
    nm_id = fixtures["nm"].id
    rec_ab_id = fixtures["rec_ab"].id
    rec_aa_id = fixtures["rec_aa"].id
    map_a1_id = fixtures["map_a1"].id
    map_b1_id = fixtures["map_b1"].id
    audit_a_id = fixtures["audit_a"].id
    audit_mat_id = fixtures["audit_mat"].id

    res = client.delete(f"/api/v1/cpses/{str(cpse_a_id)}", headers=AUTH_HEADERS)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["deleted_id"] == str(cpse_a_id)
    assert data["deleted_type"] == "CPSE"

    # Verify DB state
    # 1. CPSE A deleted
    assert db.query(CPSE).filter(CPSE.id == cpse_a_id).first() is None

    # 2. Materials A1 and A2 deleted
    assert db.query(Material).filter(Material.id == mat_a1_id).first() is None
    assert db.query(Material).filter(Material.id == mat_a2_id).first() is None

    # 3. Recommendations involving A1 or A2 deleted
    assert db.query(MatchRecommendation).filter(MatchRecommendation.id == rec_ab_id).first() is None
    assert db.query(MatchRecommendation).filter(MatchRecommendation.id == rec_aa_id).first() is None

    # 4. Mapping for A1 deleted
    assert db.query(MaterialNationalMapping).filter(MaterialNationalMapping.id == map_a1_id).first() is None

    # 5. National Material preserved
    nm = db.query(NationalMaterial).filter(NationalMaterial.id == nm_id).first()
    assert nm is not None
    assert nm.status == "ACTIVE"

    # 6. AuditLog preserved
    assert db.query(AuditLog).filter(AuditLog.id == audit_a_id).first() is not None
    assert db.query(AuditLog).filter(AuditLog.id == audit_mat_id).first() is not None

    # 7. Unrelated CPSE B, Material B1, and Mapping B1 preserved
    assert db.query(CPSE).filter(CPSE.id == cpse_b_id).first() is not None
    assert db.query(Material).filter(Material.id == mat_b1_id).first() is not None
    assert db.query(MaterialNationalMapping).filter(MaterialNationalMapping.id == map_b1_id).first() is not None


def test_delete_material_auth_required(client: TestClient, db: Session):
    """DELETE /materials/{id} requires valid reviewer token."""
    fixtures = create_test_fixture(db)
    mat_id = str(fixtures["mat_a1"].id)

    # 1. No token
    res_no_auth = client.delete(f"/api/v1/materials/{mat_id}")
    assert res_no_auth.status_code == 401

    # 2. Invalid token
    res_bad_auth = client.delete(
        f"/api/v1/materials/{mat_id}",
        headers={"X-Reviewer-Token": "wrong-token"}
    )
    assert res_bad_auth.status_code == 401


def test_delete_material_not_found(client: TestClient):
    """DELETE /materials/{id} returns 404 for non-existent material."""
    random_id = str(uuid.uuid4())
    res = client.delete(f"/api/v1/materials/{random_id}", headers=AUTH_HEADERS)
    assert res.status_code == 404
    assert res.json()["detail"] == "Material not found"


def test_delete_material_success_and_cleanup(client: TestClient, db: Session):
    """
    DELETE /materials/{id} successfully:
    1. Removes the Material
    2. Removes dependent MatchRecommendations (as source and candidate)
    3. Removes dependent MaterialNationalMappings
    4. Preserves CPSE
    5. Preserves other Materials in the same CPSE
    6. Preserves NationalMaterial
    7. Preserves AuditLog records
    """
    fixtures = create_test_fixture(db)
    cpse_a_id = fixtures["cpse_a"].id
    mat_a1_id = fixtures["mat_a1"].id
    mat_a2_id = fixtures["mat_a2"].id
    mat_b1_id = fixtures["mat_b1"].id
    nm_id = fixtures["nm"].id
    rec_ab_id = fixtures["rec_ab"].id
    rec_aa_id = fixtures["rec_aa"].id
    map_a1_id = fixtures["map_a1"].id
    map_b1_id = fixtures["map_b1"].id
    audit_mat_id = fixtures["audit_mat"].id

    res = client.delete(f"/api/v1/materials/{str(mat_a1_id)}", headers=AUTH_HEADERS)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["deleted_id"] == str(mat_a1_id)
    assert data["deleted_type"] == "MATERIAL"

    # Verify DB state
    # 1. Material A1 deleted
    assert db.query(Material).filter(Material.id == mat_a1_id).first() is None

    # 2. Material A2 still exists in CPSE A
    assert db.query(Material).filter(Material.id == mat_a2_id).first() is not None
    assert db.query(CPSE).filter(CPSE.id == cpse_a_id).first() is not None

    # 3. Recommendations involving A1 deleted
    assert db.query(MatchRecommendation).filter(MatchRecommendation.id == rec_ab_id).first() is None
    assert db.query(MatchRecommendation).filter(MatchRecommendation.id == rec_aa_id).first() is None

    # 4. Mapping for A1 deleted
    assert db.query(MaterialNationalMapping).filter(MaterialNationalMapping.id == map_a1_id).first() is None

    # 5. Shared National Material preserved
    nm = db.query(NationalMaterial).filter(NationalMaterial.id == nm_id).first()
    assert nm is not None
    assert nm.status == "ACTIVE"

    # 6. Mapping for B1 to shared NM still exists
    assert db.query(MaterialNationalMapping).filter(MaterialNationalMapping.id == map_b1_id).first() is not None

    # 7. AuditLog preserved
    assert db.query(AuditLog).filter(AuditLog.id == audit_mat_id).first() is not None
