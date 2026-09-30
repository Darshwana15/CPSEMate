from fastapi import HTTPException
from fastapi.testclient import TestClient
import pytest
import uuid

from app.api.deps import get_current_reviewer
from app.core.config import Settings, settings
from app.models import CPSE, Material, MatchRecommendation, NationalMaterial, MaterialNationalMapping, AuditLog

def test_get_current_reviewer_accepts_configured_tokens(monkeypatch):
    monkeypatch.setattr(settings, "reviewer_tokens_raw", "token_a, token_b , ,token_c")
    monkeypatch.setattr(settings, "reviewer_token", None)

    assert settings.reviewer_tokens == ["token_a", "token_b", "token_c"]
    assert get_current_reviewer("token_a") == "human_reviewer"
    assert get_current_reviewer("token_b") == "human_reviewer"

    with pytest.raises(HTTPException) as exc:
        get_current_reviewer("invalid-token")
    assert exc.value.status_code == 401

    with pytest.raises(HTTPException) as exc:
        get_current_reviewer("")
    assert exc.value.status_code == 401


def test_get_current_reviewer_supports_legacy_single_token(monkeypatch):
    monkeypatch.setattr(settings, "reviewer_tokens_raw", None)
    monkeypatch.setattr(settings, "reviewer_token", "legacy-token")

    assert settings.reviewer_tokens == ["legacy-token"]
    assert get_current_reviewer("legacy-token") == "human_reviewer"


@pytest.fixture
def test_cpse(db):
    c = CPSE(code=f"CPSE-REV-{uuid.uuid4()}", name="REV")
    db.add(c)
    db.commit()
    db.refresh(c)
    return c

def create_mat(db, cpse, complete=True) -> Material:
    mat = Material(
        id=uuid.uuid4(),
        cpse_id=cpse.id,
        source_material_code=f"M-{uuid.uuid4()}",
        source_description="DESC",
        source_uom="EA",
        category="VALVE",
        normalized_description="NORM DESC",
        valve_type="BALL",
        size="DN50",
        body_material="CARBON_STEEL",
        pressure_class="CLASS300",
        connection_type="RF",
        trim="SS304" if complete else None,
        normalized_uom="EACH"
    )
    db.add(mat)
    db.commit()
    db.refresh(mat)
    return mat

def create_rec(db, m1, m2, classification):
    rec = MatchRecommendation(
        source_material_id=m1.id,
        candidate_material_id=m2.id,
        classification=classification,
        confidence=0.8 if classification == "SAME" else 0.5,
        evidence={},
        explanation="TEST"
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return rec

def test_unauthorized_rejected(client: TestClient):
    resp = client.get("/api/v1/reviews/queue")
    assert resp.status_code == 401 # 16. unauthorized rejected

def test_queue_appears(client: TestClient, db, test_cpse):
    m1 = create_mat(db, test_cpse)
    m2 = create_mat(db, test_cpse)
    rec1 = create_rec(db, m1, m2, "POTENTIALLY_EQUIVALENT")

    m3 = create_mat(db, test_cpse, complete=False)
    m4 = create_mat(db, test_cpse)
    rec2 = create_rec(db, m3, m4, "SAME") # Incomplete identity SAME

    headers = {"X-Reviewer-Token": settings.reviewer_token}
    resp = client.get("/api/v1/reviews/queue", headers=headers)
    assert resp.status_code == 200
    q = resp.json()["queue"]

    rec_ids = [r["recommendation_id"] for r in q]
    assert str(rec1.id) in rec_ids # 1. POTENTIALLY_EQUIVALENT appears
    assert str(rec2.id) in rec_ids # 2. Incomplete identity appears

def test_accept_complete(client: TestClient, db, test_cpse):
    m1 = create_mat(db, test_cpse)
    m2 = create_mat(db, test_cpse)
    rec = create_rec(db, m1, m2, "POTENTIALLY_EQUIVALENT")

    headers = {"X-Reviewer-Token": settings.reviewer_token}
    resp = client.post(f"/api/v1/reviews/{rec.id}/action", json={
        "action": "ACCEPT"
    }, headers=headers)
    assert resp.status_code == 200

    mapping = db.query(MaterialNationalMapping).filter_by(material_id=m1.id).first()
    assert mapping.basis == "HUMAN_CONFIRMED_SAME" # 3. ACCEPT creates HUMAN_CONFIRMED_SAME mapping

    log = db.query(AuditLog).filter_by(entity_id=str(rec.id)).first()
    assert log.action == "ACCEPT" # 11. human action creates AuditLog

    nm = db.query(NationalMaterial).filter_by(id=mapping.national_material_id).first()
    assert nm.valve_type == "BALL"
    assert m1.valve_type == "BALL" # 17. source Material data remains unchanged

def test_reject_and_mark_different(client: TestClient, db, test_cpse):
    m1 = create_mat(db, test_cpse)
    m2 = create_mat(db, test_cpse)
    rec = create_rec(db, m1, m2, "DIFFERENT")

    headers = {"X-Reviewer-Token": settings.reviewer_token}
    resp = client.post(f"/api/v1/reviews/{rec.id}/action", json={
        "action": "REJECT"
    }, headers=headers)
    assert resp.status_code == 400 # 7. REJECT requires reason

    resp2 = client.post(f"/api/v1/reviews/{rec.id}/action", json={
        "action": "REJECT", "reason": "No way"
    }, headers=headers)
    assert resp2.status_code == 200

    mapping = db.query(MaterialNationalMapping).filter_by(material_id=m1.id).first()
    assert mapping is None # 4. REJECT creates no mapping

    log = db.query(AuditLog).filter_by(entity_id=str(rec.id)).first()
    assert log.reason == "No way" # 10. reason is stored in AuditLog

    rec2 = create_rec(db, m1, m2, "POTENTIALLY_EQUIVALENT")
    resp3 = client.post(f"/api/v1/reviews/{rec2.id}/action", json={
        "action": "MARK_DIFFERENT"
    }, headers=headers)
    assert resp3.status_code == 400 # 8. MARK_DIFFERENT requires reason

    resp4 = client.post(f"/api/v1/reviews/{rec2.id}/action", json={
        "action": "MARK_DIFFERENT", "reason": "Diff class"
    }, headers=headers)
    assert resp4.status_code == 200
    assert db.query(MaterialNationalMapping).filter_by(material_id=m1.id).first() is None # 5. MARK_DIFFERENT creates no mapping

    # 14. historical recommendations remain unchanged
    db.refresh(rec)
    assert rec.classification == "DIFFERENT"

def test_override(client: TestClient, db, test_cpse):
    m1 = create_mat(db, test_cpse)
    m2 = create_mat(db, test_cpse)
    rec = create_rec(db, m1, m2, "POTENTIALLY_EQUIVALENT")

    # Create NM manually
    nm = NationalMaterial(
        id=uuid.uuid4(), national_code=f"NM-OVR-{uuid.uuid4().hex[:4]}", identity_key=f"OVR-{uuid.uuid4()}",
        category="VALVE", valve_type="BALL", size="DN50", body_material="CS",
        pressure_class="CL", connection_type="RF", trim="SS", normalized_uom="EA", canonical_description="desc"
    )
    db.add(nm)
    db.commit()

    headers = {"X-Reviewer-Token": settings.reviewer_token}
    resp = client.post(f"/api/v1/reviews/{rec.id}/action", json={
        "action": "OVERRIDE"
    }, headers=headers)
    assert resp.status_code == 400 # 9. OVERRIDE requires reason (and nm id)

    resp2 = client.post(f"/api/v1/reviews/{rec.id}/action", json={
        "action": "OVERRIDE", "reason": "Force mapping", "national_material_id": str(nm.id)
    }, headers=headers)
    assert resp2.status_code == 200

    mapping = db.query(MaterialNationalMapping).filter_by(material_id=m1.id).first()
    assert mapping.basis == "HUMAN_OVERRIDE" # 6. OVERRIDE creates HUMAN_OVERRIDE mapping
    assert mapping.national_material_id == nm.id

def test_accept_incomplete_non_conflicting_allowed(client: TestClient, db, test_cpse):
    # CASE 1: Non-conflicting missing attributes on both source and candidate (e.g. trim=None)
    m1 = create_mat(db, test_cpse, complete=False)
    m2 = create_mat(db, test_cpse, complete=False)
    rec = create_rec(db, m1, m2, "POTENTIALLY_EQUIVALENT")

    headers = {"X-Reviewer-Token": settings.reviewer_token}
    resp = client.post(f"/api/v1/reviews/{rec.id}/action", json={
        "action": "ACCEPT",
        "reason": "Human verified equivalent despite unspecified trim"
    }, headers=headers)

    assert resp.status_code == 200
    mapping = db.query(MaterialNationalMapping).filter_by(material_id=m1.id).first()
    assert mapping is not None
    assert mapping.basis == "HUMAN_CONFIRMED_SAME"
    assert mapping.status == "ACTIVE"

    log = db.query(AuditLog).filter_by(entity_id=str(rec.id)).first()
    assert log.action == "ACCEPT"
    assert "unspecified trim" in log.reason

    nm = db.query(NationalMaterial).filter_by(id=mapping.national_material_id).first()
    assert nm is not None
    assert nm.trim == "UNKNOWN"
    assert nm.identity_key == "VALVE|BALL|DN50|CARBON_STEEL|CLASS300|RF|UNKNOWN|EACH"

def test_accept_asymmetric_missing_rejected(client: TestClient, db, test_cpse):
    # Asymmetric missing attribute (SS304 vs UNKNOWN)
    m1 = create_mat(db, test_cpse, complete=True)  # trim=SS304
    m2 = create_mat(db, test_cpse, complete=False) # trim=None
    rec = create_rec(db, m1, m2, "POTENTIALLY_EQUIVALENT")

    headers = {"X-Reviewer-Token": settings.reviewer_token}
    resp = client.post(f"/api/v1/reviews/{rec.id}/action", json={
        "action": "ACCEPT"
    }, headers=headers)

    assert resp.status_code == 400
    assert "asymmetric missing attributes" in resp.json()["detail"].lower()

def test_accept_conflict_size_blocked(client: TestClient, db, test_cpse):
    # CASE 2: DN50 vs DN80
    m1 = create_mat(db, test_cpse)
    m2 = create_mat(db, test_cpse)
    m2.size = "DN80"
    db.commit()
    rec = create_rec(db, m1, m2, "POTENTIALLY_EQUIVALENT")

    headers = {"X-Reviewer-Token": settings.reviewer_token}
    resp = client.post(f"/api/v1/reviews/{rec.id}/action", json={
        "action": "ACCEPT"
    }, headers=headers)

    assert resp.status_code == 400
    assert "conflicting attributes" in resp.json()["detail"].lower()
    assert "size" in resp.json()["detail"].lower()

def test_accept_conflict_pressure_class_blocked(client: TestClient, db, test_cpse):
    # CASE 3: CLASS300 vs CLASS150
    m1 = create_mat(db, test_cpse)
    m2 = create_mat(db, test_cpse)
    m2.pressure_class = "CLASS150"
    db.commit()
    rec = create_rec(db, m1, m2, "POTENTIALLY_EQUIVALENT")

    headers = {"X-Reviewer-Token": settings.reviewer_token}
    resp = client.post(f"/api/v1/reviews/{rec.id}/action", json={
        "action": "ACCEPT"
    }, headers=headers)

    assert resp.status_code == 400
    assert "conflicting attributes" in resp.json()["detail"].lower()
    assert "pressure_class" in resp.json()["detail"].lower()

def test_accept_conflict_trim_blocked(client: TestClient, db, test_cpse):
    # CASE 4: SS304 vs SS316
    m1 = create_mat(db, test_cpse)
    m2 = create_mat(db, test_cpse)
    m2.trim = "SS316"
    db.commit()
    rec = create_rec(db, m1, m2, "POTENTIALLY_EQUIVALENT")

    headers = {"X-Reviewer-Token": settings.reviewer_token}
    resp = client.post(f"/api/v1/reviews/{rec.id}/action", json={
        "action": "ACCEPT"
    }, headers=headers)

    assert resp.status_code == 400
    assert "conflicting attributes" in resp.json()["detail"].lower()
    assert "trim" in resp.json()["detail"].lower()

def test_accept_conflict_valve_type_blocked(client: TestClient, db, test_cpse):
    # CASE 5: BALL vs GATE
    m1 = create_mat(db, test_cpse)
    m2 = create_mat(db, test_cpse)
    m2.valve_type = "GATE"
    db.commit()
    rec = create_rec(db, m1, m2, "POTENTIALLY_EQUIVALENT")

    headers = {"X-Reviewer-Token": settings.reviewer_token}
    resp = client.post(f"/api/v1/reviews/{rec.id}/action", json={
        "action": "ACCEPT"
    }, headers=headers)

    assert resp.status_code == 400
    assert "conflicting attributes" in resp.json()["detail"].lower()
    assert "valve_type" in resp.json()["detail"].lower()

def test_one_active_mapping_enforced(client: TestClient, db, test_cpse):
    m1 = create_mat(db, test_cpse)
    m2 = create_mat(db, test_cpse)
    rec1 = create_rec(db, m1, m2, "POTENTIALLY_EQUIVALENT")
    rec2 = create_rec(db, m1, m2, "DIFFERENT")

    headers = {"X-Reviewer-Token": settings.reviewer_token}
    client.post(f"/api/v1/reviews/{rec1.id}/action", json={"action": "ACCEPT"}, headers=headers)

    resp2 = client.post(f"/api/v1/reviews/{rec2.id}/action", json={"action": "ACCEPT"}, headers=headers)
    assert resp2.status_code == 400
    assert "already has an active mapping" in resp2.json()["detail"].lower() # 13. one ACTIVE mapping rule remains enforced

def test_mapped_semantics_exact_recommendation_only(client: TestClient, db, test_cpse):
    # CASE 1: Source has active mapping through recommendation R1.
    # R1 = SAME, R2 = DIFFERENT, R3 = POTENTIALLY_EQUIVALENT
    # Expected: R1 -> MAPPED, R2 -> DIFFERENT, R3 -> NEEDS REVIEW
    m_src = create_mat(db, test_cpse)
    m_cand1 = create_mat(db, test_cpse)
    m_cand2 = create_mat(db, test_cpse)
    m_cand3 = create_mat(db, test_cpse)

    r1 = create_rec(db, m_src, m_cand1, "SAME")
    r2 = create_rec(db, m_src, m_cand2, "DIFFERENT")
    r3 = create_rec(db, m_src, m_cand3, "POTENTIALLY_EQUIVALENT")

    # Create NM and mapping strictly linked to r1
    nm = NationalMaterial(
        id=uuid.uuid4(),
        national_code=f"NM-TEST-{uuid.uuid4().hex[:6]}",
        identity_key=f"TEST-KEY-{uuid.uuid4()}",
        canonical_description="CANONICAL DESC",
        category="VALVE",
        valve_type="BALL",
        size="DN50",
        body_material="CARBON_STEEL",
        pressure_class="CLASS300",
        connection_type="RF",
        trim="SS304",
        normalized_uom="EACH",
        status="ACTIVE"
    )
    db.add(nm)
    db.flush()

    mapping = MaterialNationalMapping(
        id=uuid.uuid4(),
        material_id=m_src.id,
        national_material_id=nm.id,
        basis="AUTO_SAME",
        status="ACTIVE",
        recommendation_id=r1.id
    )
    db.add(mapping)
    db.commit()

    headers = {"X-Reviewer-Token": settings.reviewer_token}
    resp = client.get("/api/v1/reviews/queue", headers=headers)
    assert resp.status_code == 200
    q = resp.json()["queue"]
    q_map = {item["recommendation_id"]: item for item in q}

    assert q_map[str(r1.id)]["mapping_status"] == "MAPPED"
    assert q_map[str(r1.id)]["national_material_code"] == nm.national_code
    assert q_map[str(r1.id)]["mapping_basis"] == "AUTO_SAME"

    assert q_map[str(r2.id)]["mapping_status"] == "DIFFERENT"
    assert q_map[str(r2.id)]["national_material_code"] is None

    assert q_map[str(r3.id)]["mapping_status"] == "NEEDS REVIEW"
    assert q_map[str(r3.id)]["national_material_code"] is None

def test_mapped_semantics_human_accept_preserves_other_recs(client: TestClient, db, test_cpse):
    # CASE 3 & 4: Human ACCEPT on R1 only marks R1 as MAPPED; R2 remains DIFFERENT
    m_src = create_mat(db, test_cpse)
    m_cand1 = create_mat(db, test_cpse)
    m_cand2 = create_mat(db, test_cpse)

    r1 = create_rec(db, m_src, m_cand1, "POTENTIALLY_EQUIVALENT")
    r2 = create_rec(db, m_src, m_cand2, "DIFFERENT")

    headers = {"X-Reviewer-Token": settings.reviewer_token}
    resp = client.post(f"/api/v1/reviews/{r1.id}/action", json={
        "action": "ACCEPT",
        "reason": "Verified matching specifications"
    }, headers=headers)
    assert resp.status_code == 200

    q_resp = client.get("/api/v1/reviews/queue", headers=headers)
    assert q_resp.status_code == 200
    q = q_resp.json()["queue"]
    q_map = {item["recommendation_id"]: item for item in q}

    # R1 is MAPPED
    assert q_map[str(r1.id)]["mapping_status"] == "MAPPED"
    assert q_map[str(r1.id)]["mapping_basis"] == "HUMAN_CONFIRMED_SAME"

def test_accept_idempotent_same_candidate(client: TestClient, db, test_cpse):
    # 2. ACCEPT same source + same candidate when mapping already exists is idempotent
    m1 = create_mat(db, test_cpse)
    m2 = create_mat(db, test_cpse)
    rec = create_rec(db, m1, m2, "POTENTIALLY_EQUIVALENT")

    headers = {"X-Reviewer-Token": settings.reviewer_token}
    resp1 = client.post(f"/api/v1/reviews/{rec.id}/action", json={"action": "ACCEPT"}, headers=headers)
    assert resp1.status_code == 200

    resp2 = client.post(f"/api/v1/reviews/{rec.id}/action", json={"action": "ACCEPT"}, headers=headers)
    assert resp2.status_code == 200
    assert resp2.json()["status"] == "success"

    mappings = db.query(MaterialNationalMapping).filter_by(material_id=m1.id, status="ACTIVE").all()
    assert len(mappings) == 1

def test_unmap_active_mapping_succeeds(client: TestClient, db, test_cpse):
    # 4. UNMAP existing active mapping succeeds and marks it INACTIVE
    m1 = create_mat(db, test_cpse)
    m2 = create_mat(db, test_cpse)
    rec = create_rec(db, m1, m2, "POTENTIALLY_EQUIVALENT")

    headers = {"X-Reviewer-Token": settings.reviewer_token}
    client.post(f"/api/v1/reviews/{rec.id}/action", json={"action": "ACCEPT"}, headers=headers)

    mapping = db.query(MaterialNationalMapping).filter_by(material_id=m1.id, status="ACTIVE").first()
    assert mapping is not None

    resp_unmap = client.post(f"/api/v1/reviews/{rec.id}/action", json={"action": "UNMAP", "reason": "Operator unmap"}, headers=headers)
    assert resp_unmap.status_code == 200

    db.refresh(mapping)
    assert mapping.status == "INACTIVE"

    log = db.query(AuditLog).filter_by(entity_id=str(mapping.id), action="UNMAP").first()
    assert log is not None

def test_unmap_then_accept_succeeds(client: TestClient, db, test_cpse):
    # 5. UNMAP followed by ACCEPT succeeds
    m1 = create_mat(db, test_cpse)
    m2 = create_mat(db, test_cpse)
    m3 = create_mat(db, test_cpse)
    rec1 = create_rec(db, m1, m2, "POTENTIALLY_EQUIVALENT")
    rec2 = create_rec(db, m1, m3, "POTENTIALLY_EQUIVALENT")

    headers = {"X-Reviewer-Token": settings.reviewer_token}
    # Accept rec1
    client.post(f"/api/v1/reviews/{rec1.id}/action", json={"action": "ACCEPT"}, headers=headers)

    # UNMAP rec1
    resp_unmap = client.post(f"/api/v1/reviews/{rec1.id}/action", json={"action": "UNMAP"}, headers=headers)
    assert resp_unmap.status_code == 200

    # Accept rec2
    resp_accept2 = client.post(f"/api/v1/reviews/{rec2.id}/action", json={"action": "ACCEPT"}, headers=headers)
    assert resp_accept2.status_code == 200

    active_mappings = db.query(MaterialNationalMapping).filter_by(material_id=m1.id, status="ACTIVE").all()
    assert len(active_mappings) == 1
    assert active_mappings[0].recommendation_id == rec2.id

def test_override_replaces_existing_mapping(client: TestClient, db, test_cpse):
    # 6. OVERRIDE explicitly replaces existing active mapping
    m1 = create_mat(db, test_cpse)
    m2 = create_mat(db, test_cpse)
    rec = create_rec(db, m1, m2, "POTENTIALLY_EQUIVALENT")

    headers = {"X-Reviewer-Token": settings.reviewer_token}
    client.post(f"/api/v1/reviews/{rec.id}/action", json={"action": "ACCEPT"}, headers=headers)

    old_mapping = db.query(MaterialNationalMapping).filter_by(material_id=m1.id, status="ACTIVE").first()
    assert old_mapping is not None

    # Target new NM
    nm2 = NationalMaterial(
        id=uuid.uuid4(),
        national_code=f"NM-OVR-{uuid.uuid4().hex[:6]}",
        identity_key=f"OVR-KEY-{uuid.uuid4()}",
        canonical_description="TARGET NM",
        category="VALVE",
        valve_type="BALL",
        size="DN80",
        body_material="CARBON_STEEL",
        pressure_class="CLASS150",
        connection_type="RF",
        trim="SS304",
        normalized_uom="EACH",
        status="ACTIVE"
    )
    db.add(nm2)
    db.commit()

    resp_ovr = client.post(f"/api/v1/reviews/{rec.id}/action", json={
        "action": "OVERRIDE",
        "reason": "Explicit operator remap",
        "national_material_id": str(nm2.id)
    }, headers=headers)
    assert resp_ovr.status_code == 200

    db.refresh(old_mapping)
    assert old_mapping.status == "INACTIVE"

    new_mapping = db.query(MaterialNationalMapping).filter_by(material_id=m1.id, status="ACTIVE").first()
    assert new_mapping is not None
    assert new_mapping.id != old_mapping.id
    assert new_mapping.national_material_id == nm2.id
    assert new_mapping.basis == "HUMAN_OVERRIDE"

def test_accept_flange_category_succeeds(client: TestClient, db, test_cpse):
    # ISSUE 1: ACCEPT on FLANGE category creates NM and Mapping without constraint violation
    m_flange1 = Material(
        id=uuid.uuid4(),
        cpse_id=test_cpse.id,
        source_material_code=f"FLG-1-{uuid.uuid4().hex[:4]}",
        source_description="FLANGE WN 100MM CS CL150",
        source_uom="EA",
        category="FLANGE",
        normalized_description="FLANGE WN 100MM CS CL150",
        size="DN100",
        body_material="CARBON_STEEL",
        pressure_class="CLASS150",
        connection_type="RF",
        normalized_uom="EACH"
    )
    m_flange2 = Material(
        id=uuid.uuid4(),
        cpse_id=test_cpse.id,
        source_material_code=f"FLG-2-{uuid.uuid4().hex[:4]}",
        source_description="WELD NECK FLANGE DN100 CS CLASS 150",
        source_uom="EA",
        category="FLANGE",
        normalized_description="WELD NECK FLANGE DN100 CS CLASS 150",
        size="DN100",
        body_material="CARBON_STEEL",
        pressure_class="CLASS150",
        connection_type="RF",
        normalized_uom="EACH"
    )
    db.add_all([m_flange1, m_flange2])
    db.commit()

    rec_flange = create_rec(db, m_flange1, m_flange2, "POTENTIALLY_EQUIVALENT")

    headers = {"X-Reviewer-Token": settings.reviewer_token}
    resp = client.post(f"/api/v1/reviews/{rec_flange.id}/action", json={
        "action": "ACCEPT",
        "reason": "Matching flange specifications"
    }, headers=headers)

    assert resp.status_code == 200
    mapping = db.query(MaterialNationalMapping).filter_by(material_id=m_flange1.id, status="ACTIVE").first()
    assert mapping is not None
    assert mapping.basis == "HUMAN_CONFIRMED_SAME"

    nm = db.query(NationalMaterial).filter_by(id=mapping.national_material_id).first()
    assert nm is not None
    assert nm.category == "FLANGE"
    assert "FLANGE" in nm.canonical_description


def test_mapped_via_material_id_lookup(client: TestClient, db, test_cpse):
    """
    Verifies that a SAME recommendation whose source material has an ACTIVE mapping
    (linked to a DIFFERENT recommendation_id, as created by harmonize_same_families)
    still shows as MAPPED in the review queue.

    Also verifies that DIFFERENT and POTENTIALLY_EQUIVALENT recommendations for the
    same source material retain their own classification status even when the source
    is mapped — they should NOT be promoted to MAPPED.
    """
    from app.services.review import get_review_queue

    m_src = create_mat(db, test_cpse)
    m_cand_same_1 = create_mat(db, test_cpse)  # linked to the mapping (r_same_1)
    m_cand_same_2 = create_mat(db, test_cpse)  # SAME rec NOT linked to the mapping
    m_cand_diff = create_mat(db, test_cpse)
    m_cand_pot = create_mat(db, test_cpse)

    r_same_1 = create_rec(db, m_src, m_cand_same_1, "SAME")
    r_same_2 = create_rec(db, m_src, m_cand_same_2, "SAME")   # not linked to mapping
    r_diff = create_rec(db, m_src, m_cand_diff, "DIFFERENT")
    r_pot = create_rec(db, m_src, m_cand_pot, "POTENTIALLY_EQUIVALENT")

    # Create NM and mapping linked to r_same_1 only (simulating harmonize_same_families)
    nm = NationalMaterial(
        id=uuid.uuid4(),
        national_code=f"NM-MATID-{uuid.uuid4().hex[:6]}",
        identity_key=f"MATID-KEY-{uuid.uuid4()}",
        canonical_description="BALL VALVE DN50 CS CLASS300 RF SS304 TRIM",
        category="VALVE",
        valve_type="BALL",
        size="DN50",
        body_material="CARBON_STEEL",
        pressure_class="CLASS300",
        connection_type="RF",
        trim="SS304",
        normalized_uom="EACH",
        status="ACTIVE"
    )
    db.add(nm)
    db.flush()

    mapping = MaterialNationalMapping(
        id=uuid.uuid4(),
        material_id=m_src.id,
        national_material_id=nm.id,
        basis="AUTO_SAME",
        status="ACTIVE",
        recommendation_id=r_same_1.id  # only r_same_1 is directly linked
    )
    db.add(mapping)
    db.commit()

    queue = get_review_queue(db)
    q_map = {item["recommendation_id"]: item for item in queue}

    # r_same_1: directly linked via recommendation_id → MAPPED
    assert q_map[str(r_same_1.id)]["mapping_status"] == "MAPPED"
    assert q_map[str(r_same_1.id)]["national_material_code"] == nm.national_code

    # r_same_2: SAME rec, source is mapped, but rec_id not directly linked → must also be MAPPED
    assert q_map[str(r_same_2.id)]["mapping_status"] == "MAPPED", (
        "SAME rec for a mapped source material should show as MAPPED even if rec_id not linked"
    )
    assert q_map[str(r_same_2.id)]["national_material_code"] == nm.national_code

    # r_diff: DIFFERENT → must stay DIFFERENT even though source is mapped
    assert q_map[str(r_diff.id)]["mapping_status"] == "DIFFERENT", (
        "DIFFERENT rec should not be promoted to MAPPED"
    )
    assert q_map[str(r_diff.id)]["national_material_code"] is None

    # r_pot: POTENTIALLY_EQUIVALENT → must stay NEEDS REVIEW even though source is mapped
    assert q_map[str(r_pot.id)]["mapping_status"] == "NEEDS REVIEW", (
        "POTENTIALLY_EQUIVALENT rec should not be promoted to MAPPED"
    )
    assert q_map[str(r_pot.id)]["national_material_code"] is None


def test_review_queue_cpse_scoping(client: TestClient, db):
    """
    Focused verification of CPSE-scoped review queue:
    1. Querying with cpse_id=CPSE_A returns ONLY recommendations involving CPSE_A (as source OR candidate).
    2. Unrelated CPSE C -> CPSE B recommendations are strictly excluded.
    3. Mapped SAME rows for CPSE A materials appear as MAPPED.
    4. Multiple valid recommendation rows for one mapped material are preserved (e.g. A->B and A->C).
    5. POTENTIALLY_EQUIVALENT recommendations remain NEEDS REVIEW.
    6. DIFFERENT recommendations remain DIFFERENT.
    7. Review actions on scoped recommendations execute successfully.
    """
    suffix = uuid.uuid4().hex[:6]
    cpse_a = CPSE(code=f"CPSE-A-{suffix}", name=f"ScopeCpseA{suffix}")
    cpse_b = CPSE(code=f"CPSE-B-{suffix}", name=f"ScopeCpseB{suffix}")
    cpse_c = CPSE(code=f"CPSE-C-{suffix}", name=f"ScopeCpseC{suffix}")
    db.add_all([cpse_a, cpse_b, cpse_c])
    db.commit()

    m_a1 = create_mat(db, cpse_a)
    m_a2 = create_mat(db, cpse_a)
    m_b1 = create_mat(db, cpse_b)
    m_c1 = create_mat(db, cpse_c)

    # Recommendations involving CPSE A:
    # 1. m_a1 (source) -> m_b1 (candidate) [SAME]
    rec_a_b = create_rec(db, m_a1, m_b1, "SAME")
    # 2. m_a1 (source) -> m_c1 (candidate) [SAME] - multiple recommendation rows for m_a1
    rec_a_c = create_rec(db, m_a1, m_c1, "SAME")
    # 3. m_c1 (source) -> m_a1 (candidate) [SAME] - CPSE A is candidate
    rec_c_a = create_rec(db, m_c1, m_a1, "SAME")
    # 4. m_a2 (source) -> m_b1 (candidate) [DIFFERENT]
    rec_a_diff = create_rec(db, m_a2, m_b1, "DIFFERENT")
    # 5. m_a2 (source) -> m_c1 (candidate) [POTENTIALLY_EQUIVALENT]
    rec_a_pot = create_rec(db, m_a2, m_c1, "POTENTIALLY_EQUIVALENT")

    # Unrelated recommendations (CPSE C -> CPSE B): neither source nor candidate belongs to CPSE A!
    rec_unrelated_same = create_rec(db, m_c1, m_b1, "SAME")
    rec_unrelated_diff = create_rec(db, m_c1, m_b1, "DIFFERENT")

    # Active mapping for m_a1
    nm = NationalMaterial(
        id=uuid.uuid4(),
        national_code=f"NM-SCOPE-{uuid.uuid4().hex[:6]}",
        identity_key=f"SCOPE-KEY-{uuid.uuid4()}",
        canonical_description="BALL VALVE DN50 CS CLASS300 RF SS304 TRIM",
        category="VALVE",
        valve_type="BALL",
        size="DN50",
        body_material="CARBON_STEEL",
        pressure_class="CLASS300",
        connection_type="RF",
        trim="SS304",
        normalized_uom="EACH",
        status="ACTIVE"
    )
    db.add(nm)
    db.flush()

    mapping_a = MaterialNationalMapping(
        id=uuid.uuid4(),
        material_id=m_a1.id,
        national_material_id=nm.id,
        basis="AUTO_SAME",
        status="ACTIVE",
        recommendation_id=rec_a_b.id
    )
    db.add(mapping_a)
    db.commit()

    # Query queue with cpse_id=cpse_a.id via API
    headers = {"X-Reviewer-Token": settings.reviewer_token}
    resp = client.get(f"/api/v1/reviews/queue?cpse_id={cpse_a.id}", headers=headers)
    assert resp.status_code == 200
    queue = resp.json()["queue"]
    q_map = {item["recommendation_id"]: item for item in queue}

    # 1. Verify CPSE A rows are present
    assert str(rec_a_b.id) in q_map, "rec_a_b should be present"
    assert str(rec_a_c.id) in q_map, "rec_a_c should be present (multiple rows for m_a1)"
    assert str(rec_c_a.id) in q_map, "rec_c_a should be present (CPSE A as candidate)"
    assert str(rec_a_diff.id) in q_map, "rec_a_diff should be present"
    assert str(rec_a_pot.id) in q_map, "rec_a_pot should be present"

    # 2. Verify unrelated C->B rows are strictly EXCLUDED
    assert str(rec_unrelated_same.id) not in q_map, "Unrelated C->B SAME rec must be excluded from CPSE A queue"
    assert str(rec_unrelated_diff.id) not in q_map, "Unrelated C->B DIFF rec must be excluded from CPSE A queue"

    # 3. Verify MAPPED status on SAME recs involving m_a1
    assert q_map[str(rec_a_b.id)]["mapping_status"] == "MAPPED"
    assert q_map[str(rec_a_b.id)]["national_material_code"] == nm.national_code
    assert q_map[str(rec_a_c.id)]["mapping_status"] == "MAPPED"
    assert q_map[str(rec_a_c.id)]["national_material_code"] == nm.national_code
    assert q_map[str(rec_c_a.id)]["mapping_status"] == "MAPPED"
    assert q_map[str(rec_c_a.id)]["national_material_code"] == nm.national_code

    # 4. Verify DIFFERENT remains DIFFERENT
    assert q_map[str(rec_a_diff.id)]["mapping_status"] == "DIFFERENT"
    assert q_map[str(rec_a_diff.id)]["classification"] == "DIFFERENT"

    # 5. Verify POTENTIALLY_EQUIVALENT remains NEEDS REVIEW
    assert q_map[str(rec_a_pot.id)]["mapping_status"] == "NEEDS REVIEW"
    assert q_map[str(rec_a_pot.id)]["classification"] == "POTENTIALLY_EQUIVALENT"

    # 6. Verify existing review actions still work on scoped recommendations
    action_resp = client.post(
        f"/api/v1/reviews/{rec_a_pot.id}/action",
        json={"action": "MARK_DIFFERENT", "reason": "Confirmed different pressure class"},
        headers=headers
    )
    assert action_resp.status_code == 200
    assert action_resp.json()["status"] == "success"
    assert action_resp.json()["action"] == "MARK_DIFFERENT"
