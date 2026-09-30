import uuid
import pytest
from app.models import NationalMaterial

def test_list_national_materials(client, db):
    nm = NationalMaterial(
        national_code=f"NM-TEST-{uuid.uuid4().hex[:8]}",
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

    found = False
    for skip in range(0, 5000, 100):
        response = client.get(f"/api/v1/national-materials?skip={skip}")
        assert response.status_code == 200
        data = response.json()
        if not data:
            break
        if any(x["national_code"] == nm.national_code for x in data):
            found = True
            break

    assert found, f"National material {nm.national_code} not found in paginated results"

def test_get_national_material(client, db):
    nm = NationalMaterial(
        national_code=f"NM-TEST-{uuid.uuid4().hex[:8]}",
        category="VALVE",
        canonical_description="Test Valve 2",
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

    response = client.get(f"/api/v1/national-materials/{nm.id}")
    assert response.status_code == 200
    assert response.json()["national_code"] == nm.national_code


def test_get_national_material_not_found(client):
    import uuid
    random_id = str(uuid.uuid4())
    response = client.get(f"/api/v1/national-materials/{random_id}")
    assert response.status_code == 404

def test_get_national_material_malformed_uuid(client):
    response = client.get("/api/v1/national-materials/not-a-uuid")
    assert response.status_code == 422

def test_list_national_materials_empty(client):
    from app.main import app
    from app.db.session import get_db

    class MockQuery:
        def order_by(self, *args): return self
        def offset(self, *args): return self
        def limit(self, *args): return self
        def all(self): return []

    class MockSession:
        def query(self, *args): return MockQuery()

    previous_override = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = lambda: MockSession()
    try:
        response = client.get("/api/v1/national-materials")
        assert response.status_code == 200
        assert response.json() == []
    finally:
        if previous_override is not None:
            app.dependency_overrides[get_db] = previous_override
        else:
            app.dependency_overrides.pop(get_db, None)
