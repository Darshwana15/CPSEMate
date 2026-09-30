import uuid
import pytest
from fastapi.testclient import TestClient
from app.models import CPSE, Material

def test_get_material_detail_success(client: TestClient, db):
    # Setup test data
    c = CPSE(code=f"CPSE-TEST-{uuid.uuid4()}", name="Test CPSE")
    db.add(c)
    db.commit()
    db.refresh(c)

    mat = Material(
        cpse_id=c.id,
        source_material_code=f"M-TEST-{uuid.uuid4()}",
        source_description="Test Desc",
        source_uom="EA",
        source_specifications="Spec",
        raw_source_data={"key": "value"},
        category="VALVE",
        valve_type="BALL",
        size="DN50",
        body_material="CS",
        pressure_class="300",
        connection_type="RF",
        trim="SS",
        normalized_uom="EACH",
        normalized_description="Norm Desc",
        normalized_attributes={"n_key": "n_val"}
    )
    db.add(mat)
    db.commit()
    db.refresh(mat)

    # Run test
    resp = client.get(f"/api/v1/materials/{mat.id}")
    assert resp.status_code == 200

    data = resp.json()
    assert data["id"] == str(mat.id)
    assert data["cpse_id"] == str(c.id)
    assert data["source_material_code"] == mat.source_material_code
    assert data["source_description"] == "Test Desc"
    assert data["source_uom"] == "EA"
    assert data["source_specifications"] == "Spec"
    assert data["raw_source_data"] == {"key": "value"}
    assert data["category"] == "VALVE"
    assert data["valve_type"] == "BALL"
    assert data["size"] == "DN50"
    assert data["body_material"] == "CS"
    assert data["pressure_class"] == "300"
    assert data["connection_type"] == "RF"
    assert data["trim"] == "SS"
    assert data["normalized_uom"] == "EACH"
    assert data["normalized_description"] == "Norm Desc"
    assert data["normalized_attributes"] == {"n_key": "n_val"}
    assert "created_at" in data
    assert "updated_at" in data

    # Verify no relationships leaked
    assert "cpse" not in data
    assert "mappings" not in data
    assert "recommendations" not in data
    assert "audit_logs" not in data

def test_get_material_not_found(client: TestClient):
    random_id = str(uuid.uuid4())
    resp = client.get(f"/api/v1/materials/{random_id}")
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()

def test_get_material_malformed_uuid(client: TestClient):
    resp = client.get("/api/v1/materials/not-a-uuid")
    assert resp.status_code == 422
