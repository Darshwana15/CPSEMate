import uuid
import pytest
from fastapi.testclient import TestClient

from app.models import CPSE

def test_create_cpse_success(client: TestClient, db):
    code = f"TEST-CPSE-{uuid.uuid4()}"
    data = {
        "code": code,
        "name": "Test CPSE Name"
    }
    resp = client.post("/api/v1/cpses", json=data)
    assert resp.status_code == 201
    res = resp.json()
    assert res["code"] == code
    assert res["name"] == "Test CPSE Name"
    assert "id" in res
    assert "created_at" in res

    # Verify in DB
    cpse_db = db.query(CPSE).filter(CPSE.code == code).first()
    assert cpse_db is not None
    assert str(cpse_db.id) == res["id"]

def test_create_cpse_duplicate_rejected(client: TestClient, db):
    code = f"TEST-DUP-{uuid.uuid4()}"
    data = {
        "code": code,
        "name": "Duplicate CPSE"
    }
    # First create
    resp1 = client.post("/api/v1/cpses", json=data)
    assert resp1.status_code == 201

    # Second create should fail
    resp2 = client.post("/api/v1/cpses", json=data)
    assert resp2.status_code == 400
    assert "already exists" in resp2.json()["detail"].lower()

def test_create_cpse_missing_fields(client: TestClient):
    # Missing name
    data = {
        "code": f"TEST-{uuid.uuid4()}"
    }
    resp = client.post("/api/v1/cpses", json=data)
    assert resp.status_code == 422  # Pydantic validation error

    # Missing code
    data = {
        "name": "Missing Code CPSE"
    }
    resp2 = client.post("/api/v1/cpses", json=data)
    assert resp2.status_code == 422


def test_list_cpses_empty(client: TestClient):
    from app.main import app
    from app.db.session import get_db

    class MockQuery:
        def order_by(self, *args): return self
        def all(self): return []

    class MockSession:
        def query(self, *args): return MockQuery()

    previous_override = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = lambda: MockSession()
    try:
        resp = client.get("/api/v1/cpses")
        assert resp.status_code == 200
        assert resp.json() == []
    finally:
        if previous_override is not None:
            app.dependency_overrides[get_db] = previous_override
        else:
            app.dependency_overrides.pop(get_db, None)

def test_list_cpses_multiple_and_ordering(client: TestClient):
    import uuid
    # Create two CPSEs with specific names to test ordering
    c1_code = f"Z-CODE-{uuid.uuid4()}"
    c2_code = f"A-CODE-{uuid.uuid4()}"
    client.post("/api/v1/cpses", json={"code": c1_code, "name": "Zeta CPSE"})
    client.post("/api/v1/cpses", json={"code": c2_code, "name": "Alpha CPSE"})

    resp = client.get("/api/v1/cpses")
    assert resp.status_code == 200
    data = resp.json()

    # Verify both exist in the response
    codes = [item["code"] for item in data]
    assert c1_code in codes
    assert c2_code in codes

    # Verify deterministic ordering by name
    names = [item["name"] for item in data]
    assert names == sorted(names)

def test_list_cpses_response_fields(client: TestClient):
    import uuid
    code = f"TEST-FIELDS-{uuid.uuid4()}"
    client.post("/api/v1/cpses", json={"code": code, "name": "Field Test CPSE"})

    resp = client.get("/api/v1/cpses")
    assert resp.status_code == 200
    data = resp.json()

    # Find our specific item
    item = next(i for i in data if i["code"] == code)

    # Verify structure
    assert "id" in item
    assert "code" in item
    assert "name" in item
    assert "created_at" in item
    assert "updated_at" in item
    assert item["name"] == "Field Test CPSE"

def test_list_cpse_materials_empty(client: TestClient, db):
    # Create a CPSE
    cpse_code = f"T1-{uuid.uuid4()}"
    resp_cpse = client.post("/api/v1/cpses", json={"code": cpse_code, "name": "Mat Test CPSE"})
    assert resp_cpse.status_code == 201
    cpse_id = resp_cpse.json()["id"]

    # Verify empty material list
    resp = client.get(f"/api/v1/cpses/{cpse_id}/materials")
    assert resp.status_code == 200
    assert resp.json() == []

def test_list_cpse_materials_not_found(client: TestClient):
    random_id = str(uuid.uuid4())
    resp = client.get(f"/api/v1/cpses/{random_id}/materials")
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()

def test_list_cpse_materials_populated(client: TestClient, db):
    from app.models import Material
    # Create CPSE
    cpse_code = f"T2-{uuid.uuid4()}"
    resp_cpse = client.post("/api/v1/cpses", json={"code": cpse_code, "name": "Mat Test CPSE 2"})
    cpse_id = resp_cpse.json()["id"]

    # Insert materials manually via DB for test
    mat1 = Material(
        cpse_id=cpse_id,
        source_material_code="B-CODE",
        source_description="B Desc",
        source_uom="EA",
        category="VALVE"
    )
    mat2 = Material(
        cpse_id=cpse_id,
        source_material_code="A-CODE",
        source_description="A Desc",
        source_uom="EA",
        category="VALVE"
    )
    db.add(mat1)
    db.add(mat2)
    db.commit()

    # Fetch and verify
    resp = client.get(f"/api/v1/cpses/{cpse_id}/materials")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2

    # Verify ordering by source_material_code
    assert data[0]["source_material_code"] == "A-CODE"
    assert data[1]["source_material_code"] == "B-CODE"

    # Verify exact response fields
    first = data[0]
    assert "id" in first
    assert first["cpse_id"] == cpse_id
    assert first["source_description"] == "A Desc"
    assert first["category"] == "VALVE"
    assert "normalized_description" in first
    assert "raw_source_data" not in first
    assert "valve_type" not in first
