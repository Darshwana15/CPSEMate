import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.models import (
    CPSE, Material, NationalMaterial, MatchRecommendation,
    MaterialNationalMapping, AuditLog
)

def test_dashboard_empty_database(client: TestClient):
    response = client.get("/api/v1/dashboard")
    assert response.status_code == 200
    data = response.json()
    assert data["inventory"]["total_materials"] >= 0
    # On an empty DB (or mostly empty from isolation), stats should be zeroed
    # But since tests share DB, it might not be strictly empty. Let's use a mock for empty.


def test_dashboard_empty_mock(client: TestClient):
    from app.main import app
    from app.db.session import get_db
    from sqlalchemy import select
    from app.models import MaterialNationalMapping

    class MockQuery:
        def scalar(self): return 0
        def all(self): return []
        def filter(self, *args, **kwargs): return self
        def order_by(self, *args, **kwargs): return self
        def join(self, *args, **kwargs): return self
        def __clause_element__(self):
            return select(MaterialNationalMapping.material_id).where(False)

    class MockSession:
        def query(self, *args): return MockQuery()

    previous_override = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = lambda: MockSession()
    try:
        response = client.get("/api/v1/dashboard")
        assert response.status_code == 200
        data = response.json()
        assert data["inventory"]["total_materials"] == 0
        assert data["inventory"]["total_cpses"] == 0
        assert data["harmonization"]["total_national_materials"] == 0
        assert data["harmonization"]["total_mapped_materials"] == 0
        assert data["harmonization"]["automation_rate_percentage"] == 0.0
        assert data["review"]["pending_reviews"] == 0
        assert data["review"]["completed_reviews"] == 0
        assert data["cpse_breakdown"] == []
    finally:
        if previous_override is not None:
            app.dependency_overrides[get_db] = previous_override
        else:
            app.dependency_overrides.pop(get_db, None)

def test_dashboard_known_data(client: TestClient, db: Session):
    # Create isolated CPSE and materials
    cpse1 = CPSE(id=uuid.uuid4(), code=f"DASH-CPSE1-{uuid.uuid4().hex[:4]}", name="Dashboard CPSE 1")
    cpse2 = CPSE(id=uuid.uuid4(), code=f"DASH-CPSE2-{uuid.uuid4().hex[:4]}", name="Dashboard CPSE 2")
    # Pre-dashboard response
    resp1 = client.get("/api/v1/dashboard").json()

    db.add_all([cpse1, cpse2])
    db.commit()

    mat1 = Material(
        id=uuid.uuid4(), cpse_id=cpse1.id,
        source_material_code="M1", source_description="Desc1", source_uom="EA",
        category="VALVE"
    )
    mat2 = Material(
        id=uuid.uuid4(), cpse_id=cpse2.id,
        source_material_code="M2", source_description="Desc2", source_uom="EA",
        category="VALVE"
    )
    db.add_all([mat1, mat2])
    db.commit()
    start_mats = resp1["inventory"]["total_materials"]
    start_cpses = resp1["inventory"]["total_cpses"]
    start_nms = resp1["harmonization"]["total_national_materials"]

    nm = NationalMaterial(
        id=uuid.uuid4(), national_code=f"NM-DASH-{uuid.uuid4().hex[:4]}", category="VALVE",
        canonical_description="Valve", valve_type="BALL", size="DN50", body_material="CS",
        pressure_class="300", connection_type="RF", trim="SS", normalized_uom="EA",
        identity_key=f"ID-DASH-{uuid.uuid4().hex[:4]}", status="ACTIVE"
    )
    db.add(nm)
    db.commit()

    mapping = MaterialNationalMapping(
        id=uuid.uuid4(), material_id=mat1.id, national_material_id=nm.id,
        basis="AUTO_SAME", status="ACTIVE"
    )
    db.add(mapping)
    db.commit()

    # 1 recommendation
    rec = MatchRecommendation(
        id=uuid.uuid4(), source_material_id=mat2.id, candidate_material_id=mat1.id,
        classification="POTENTIALLY_EQUIVALENT"
    )
    db.add(rec)
    db.commit()

    # 1 completed review
    audit = AuditLog(
        id=uuid.uuid4(), actor="user1", action="ACCEPT", entity_type="MATCH_RECOMMENDATION",
        entity_id=str(rec.id)
    )
    db.add(audit)
    db.commit()

    resp2 = client.get("/api/v1/dashboard").json()

    assert resp2["inventory"]["total_materials"] == start_mats + 2
    assert resp2["inventory"]["total_cpses"] == start_cpses + 2
    assert resp2["harmonization"]["total_national_materials"] == start_nms + 1

    # Test read-only
    resp3 = client.get("/api/v1/dashboard").json()
    assert resp2 == resp3

    # CPSE breakdown verify
    b1 = next(b for b in resp2["cpse_breakdown"] if b["cpse_id"] == str(cpse1.id))
    b2 = next(b for b in resp2["cpse_breakdown"] if b["cpse_id"] == str(cpse2.id))

    assert b1["total_materials"] == 1
    assert b1["mapped_materials"] == 1 # mat1 is mapped

    assert b2["total_materials"] == 1
    assert b2["mapped_materials"] == 0 # mat2 is not mapped
