import pytest
from app.models import AuditLog

def test_list_audit_logs(client, db):
    log = AuditLog(
        actor="TEST_USER",
        action="TEST_ACTION",
        entity_type="TEST_ENTITY",
        entity_id="test-id"
    )
    db.add(log)
    db.commit()

    response = client.get("/api/v1/audit")
    assert response.status_code == 200
    data = response.json()
    assert any(x["action"] == "TEST_ACTION" for x in data)

    response = client.get("/api/v1/audit?entity_type=TEST_ENTITY")
    assert response.status_code == 200
    data = response.json()
    assert any(x["action"] == "TEST_ACTION" for x in data)

def test_list_audit_logs_empty(client):
    response = client.get("/api/v1/audit?entity_type=NONEXISTENT_TYPE_123")
    assert response.status_code == 200
    assert response.json() == []

def test_list_audit_logs_with_reason(client, db):
    from app.models import AuditLog
    log = AuditLog(
        actor="TEST_USER",
        action="TEST_ACTION_WITH_REASON",
        entity_type="TEST_ENTITY",
        entity_id="test-id-2",
        reason="Because I said so"
    )
    db.add(log)
    db.commit()

    response = client.get("/api/v1/audit?entity_type=TEST_ENTITY&entity_id=test-id-2")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert any(x["reason"] == "Because I said so" for x in data)
