import uuid
import pytest
from app.models import MaterialNationalMapping, Material, NationalMaterial, CPSE

def test_mapping_history(client, db):
    cpse = CPSE(code=f"TEST_CPSE_MAP_{uuid.uuid4().hex[:8]}", name="Test CPSE")
    db.add(cpse)
    db.commit()

    mat = Material(
        cpse_id=cpse.id,
        source_material_code="MAT-MAP-001",
        source_description="Test",
        source_uom="EA"
    )
    db.add(mat)
    db.commit()

    nm = NationalMaterial(
        national_code=f"NM-MAP-{uuid.uuid4().hex[:8]}",
        category="VALVE",
        canonical_description="Test Valve",
        valve_type="BALL",
        size="DN50",
        body_material="CS",
        pressure_class="300",
        connection_type="RF",
        trim="SS",
        normalized_uom="EA",
        identity_key=f"TESTKEY-{uuid.uuid4().hex[:8]}",
        status="ACTIVE"
    )
    db.add(nm)
    db.commit()

    mapping = MaterialNationalMapping(
        material_id=mat.id,
        national_material_id=nm.id,
        basis="AUTO_SAME",
        status="ACTIVE"
    )
    db.add(mapping)
    db.commit()

    response = client.get(f"/api/v1/materials/{mat.id}/mapping-history")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["basis"] == "AUTO_SAME"

def test_mapping_history_not_found(client):
    import uuid
    random_id = str(uuid.uuid4())
    response = client.get(f"/api/v1/materials/{random_id}/mapping-history")
    # Actually, the user asked for missing material to return 404
    # Wait, did the subagent implement 404 for missing material? I need to check endpoints/materials.py
    # If the subagent didn't implement it, I will fix it. Let's write the test first.
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()

def test_mapping_history_malformed_uuid(client):
    response = client.get("/api/v1/materials/not-a-uuid/mapping-history")
    assert response.status_code == 422
