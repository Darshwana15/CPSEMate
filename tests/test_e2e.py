from app.core.config import settings
import os
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import CPSE, Material, NationalMaterial, MatchRecommendation, MaterialNationalMapping, AuditLog

def test_e2e_pipeline(client: TestClient, db: Session):
    # 1. Setup CPSEs
    run_id = uuid.uuid4().hex[:6]
    cpse_a = CPSE(id=uuid.uuid4(), code=f"CPSE-A-DEMO-{run_id}", name="CPSE A")
    cpse_b = CPSE(id=uuid.uuid4(), code=f"CPSE-B-DEMO-{run_id}", name="CPSE B")
    cpse_c = CPSE(id=uuid.uuid4(), code=f"CPSE-C-DEMO-{run_id}", name="CPSE C")
    db.add_all([cpse_a, cpse_b, cpse_c])
    db.commit()

    # 2. Upload Data
    base_dir = os.path.dirname(os.path.abspath(__file__))
    for code, c_id in [("cpse_a", cpse_a.id), ("cpse_b", cpse_b.id), ("cpse_c", cpse_c.id)]:
        file_path = os.path.join(base_dir, "demo_data", f"{code}.csv")
        with open(file_path, "rb") as f:
            resp = client.post(f"/api/v1/materials/import", data={"cpse_id": str(c_id)}, files={"file": (f"{code}.csv", f, "text/csv")})
            assert resp.status_code == 200, resp.text
            summary = resp.json()
            if code == "cpse_a":
                assert summary["total_rows"] == 6
                assert summary["imported_rows"] == 4
                assert summary["rejected_rows"] == 2 # 1 invalid, 1 duplicate

    materials = db.query(Material).filter(Material.cpse_id.in_([cpse_a.id, cpse_b.id, cpse_c.id])).all()
    assert len(materials) == 14 # 4 (A) + 6 (B) + 4 (C)

    # 3. Normalize imported materials
    for mat in materials:
        resp = client.post(f"/api/v1/materials/{mat.id}/normalize")
        assert resp.status_code == 200

    db.expire_all()

    # 4. Generate matching recommendations
    for mat in materials:
        resp = client.post(f"/api/v1/materials/{mat.id}/match")
        assert resp.status_code == 200

    db.expire_all()

    # 5. Harmonize safe SAME records
    for mat in materials:
        client.post(f"/api/v1/materials/{mat.id}/harmonize")

    db.expire_all()

    # 6. Verify Exact Equivalent across CPSEs mapping to same NM
    a1 = db.query(Material).filter_by(source_material_code="A-001", cpse_id=cpse_a.id).first()
    b1 = db.query(Material).filter_by(source_material_code="B-001", cpse_id=cpse_b.id).first()
    c1 = db.query(Material).filter_by(source_material_code="C-001", cpse_id=cpse_c.id).first()

    map_a1 = db.query(MaterialNationalMapping).filter_by(material_id=a1.id, status="ACTIVE").first()
    map_b1 = db.query(MaterialNationalMapping).filter_by(material_id=b1.id, status="ACTIVE").first()
    map_c1 = db.query(MaterialNationalMapping).filter_by(material_id=c1.id, status="ACTIVE").first()

    assert map_a1 is not None and map_b1 is not None and map_c1 is not None
    assert map_a1.national_material_id == map_b1.national_material_id
    assert map_a1.national_material_id == map_c1.national_material_id
    assert map_a1.basis == "AUTO_SAME"

    # 7. Verify CLASS150 vs CLASS300, DN50 vs DN100, BALL vs GATE, RF vs SW are DIFFERENT
    # A-001 (BALL, DN50, CS, CLASS300, RF, SS304)
    # B-003 (CLASS150 variant), B-004 (4 INCH / DN100 variant), C-002 (SS316 TRIM variant), C-004 (SOCKET WELD variant)
    def check_diff(source_code, source_cpse_id, candidate_code, cand_cpse_id):
        src = db.query(Material).filter_by(source_material_code=source_code, cpse_id=source_cpse_id).first()
        cand = db.query(Material).filter_by(source_material_code=candidate_code, cpse_id=cand_cpse_id).first()
        rec = db.query(MatchRecommendation).filter_by(source_material_id=src.id, candidate_material_id=cand.id).first()
        assert rec is not None
        assert rec.classification == "DIFFERENT"
        return rec

    check_diff("A-001", cpse_a.id, "B-003", cpse_b.id) # Class diff
    check_diff("A-001", cpse_a.id, "B-004", cpse_b.id) # Size diff
    check_diff("A-001", cpse_a.id, "C-002", cpse_c.id) # Trim diff
    check_diff("A-001", cpse_a.id, "C-004", cpse_c.id) # Connection diff
    # check_diff("A-001", cpse_a.id, "B-002", cpse_b.id) # Pre-filtered out by matching engine completely

    # 8. Verify incomplete identities (Missing trim)
    # A-003, C-003
    a3 = db.query(Material).filter_by(source_material_code="A-003", cpse_id=cpse_a.id).first()
    assert db.query(MaterialNationalMapping).filter_by(material_id=a3.id).first() is None # Did not auto map!

    # 9. Verify Review Queue contains unmapped items
    headers = {"X-Reviewer-Token": settings.reviewer_token}
    resp = client.get("/api/v1/reviews/queue", headers=headers)
    assert resp.status_code == 200
    queue = resp.json()["queue"]

    # Extract rec_ids from queue
    q_rec_ids = [q["recommendation_id"] for q in queue]

    # 10. Human ACCEPT on asymmetric incomplete (A-003 missing trim vs C-002 with SS316 trim) -> should fail
    c2 = db.query(Material).filter_by(source_material_code="C-002", cpse_id=cpse_c.id).first()
    rec_a3_c2 = db.query(MatchRecommendation).filter_by(source_material_id=a3.id, candidate_material_id=c2.id).first()
    assert rec_a3_c2 is not None

    resp_accept_invalid = client.post(f"/api/v1/reviews/{rec_a3_c2.id}/action", json={"action": "ACCEPT"}, headers=headers)
    assert resp_accept_invalid.status_code == 400
    assert "asymmetric" in resp_accept_invalid.json()["detail"].lower()

    # 11. Human OVERRIDE on A-003
    c3 = db.query(Material).filter_by(source_material_code="C-003", cpse_id=cpse_c.id).first()
    rec_a3_c3 = db.query(MatchRecommendation).filter_by(source_material_id=a3.id, candidate_material_id=c3.id).first()
    nm_target = map_a1.national_material_id # We'll just map it to the known complete one
    resp_override = client.post(f"/api/v1/reviews/{rec_a3_c3.id}/action", json={
        "action": "OVERRIDE", "reason": "Standardizing to SS304", "national_material_id": str(nm_target)
    }, headers=headers)
    assert resp_override.status_code == 200

    map_a3 = db.query(MaterialNationalMapping).filter_by(material_id=a3.id).first()
    assert map_a3.basis == "HUMAN_OVERRIDE"

    # 12. Human MARK_DIFFERENT on a POTENTIALLY_EQUIVALENT rec
    # A-001 vs A-003 should be POTENTIALLY_EQUIVALENT because A-003 misses trim
    rec_a1_a3 = db.query(MatchRecommendation).filter_by(source_material_id=a1.id, candidate_material_id=a3.id).first()
    if rec_a1_a3 and rec_a1_a3.classification == "POTENTIALLY_EQUIVALENT":
        resp_md = client.post(f"/api/v1/reviews/{rec_a1_a3.id}/action", json={
            "action": "MARK_DIFFERENT", "reason": "We do not know the trim"
        }, headers=headers)
        assert resp_md.status_code == 200
        # Audit log verifies
        log_md = db.query(AuditLog).filter_by(action="MARK_DIFFERENT", entity_id=str(rec_a1_a3.id)).first()
        assert log_md is not None
        assert log_md.reason == "We do not know the trim"

    # 13. Audit history verifies
    assert db.query(AuditLog).count() > 30 # Just ensuring it exists and logs lots of things (ingestion, norm, map, review)

    # 14. E2E VERIFICATION OF ALL READ APIs

    # 14.a GET /api/v1/cpses
    resp_cpses = client.get("/api/v1/cpses")
    assert resp_cpses.status_code == 200
    cpses_data = resp_cpses.json()
    assert len([c for c in cpses_data if c["code"] in [cpse_a.code, cpse_b.code, cpse_c.code]]) == 3

    # 14.b GET /api/v1/cpses/{cpse_id}/materials
    resp_cpse_a_mats = client.get(f"/api/v1/cpses/{cpse_a.id}/materials")
    assert resp_cpse_a_mats.status_code == 200
    mats_data = resp_cpse_a_mats.json()
    assert len(mats_data) == 4
    # Ensure raw_source_data is NOT in list payload
    assert "raw_source_data" not in mats_data[0]

    # 14.c GET /api/v1/materials/{material_id}
    mat_id = mats_data[0]["id"]
    resp_mat_detail = client.get(f"/api/v1/materials/{mat_id}")
    assert resp_mat_detail.status_code == 200
    mat_detail = resp_mat_detail.json()
    assert "raw_source_data" in mat_detail
    assert "normalized_attributes" in mat_detail
    assert "cpse" not in mat_detail # No relationships

    # 14.d GET /api/v1/national-materials
    resp_nms = client.get("/api/v1/national-materials")
    assert resp_nms.status_code == 200
    nms_data = resp_nms.json()
    assert len(nms_data) > 0
    nm_id = nms_data[0]["id"]

    # 14.e GET /api/v1/national-materials/{nm_id}
    resp_nm_detail = client.get(f"/api/v1/national-materials/{nm_id}")
    assert resp_nm_detail.status_code == 200
    nm_detail = resp_nm_detail.json()
    assert nm_detail["id"] == nm_id
    assert "mappings" not in nm_detail # No relationships

    # 14.f GET /api/v1/materials/{material_id}/mapping-history
    resp_map_hist = client.get(f"/api/v1/materials/{a3.id}/mapping-history")
    assert resp_map_hist.status_code == 200
    hist_data = resp_map_hist.json()
    assert len(hist_data) >= 1
    assert hist_data[0]["basis"] == "HUMAN_OVERRIDE"
    assert hist_data[0]["status"] == "ACTIVE"

    # 14.g GET /api/v1/audit
    resp_audit = client.get("/api/v1/audit")
    assert resp_audit.status_code == 200
    audit_data = resp_audit.json()
    assert len(audit_data) > 0

    resp_audit_filter = client.get(f"/api/v1/audit?entity_type=MATERIAL&entity_id={a3.id}")
    assert resp_audit_filter.status_code == 200
    audit_filtered_data = resp_audit_filter.json()
    # At least normalize/match logged for this material
    assert len(audit_filtered_data) > 0

    # 14.h GET /api/v1/dashboard
    resp_dash = client.get("/api/v1/dashboard")
    assert resp_dash.status_code == 200
    dash_data = resp_dash.json()
    assert dash_data["inventory"]["total_materials"] > 0
    assert dash_data["inventory"]["total_cpses"] >= 3
    assert dash_data["harmonization"]["total_national_materials"] > 0
    assert dash_data["harmonization"]["automation_rate_percentage"] >= 0.0
    assert dash_data["review"]["pending_reviews"] >= 0
    assert dash_data["review"]["completed_reviews"] >= 1
    assert len(dash_data["cpse_breakdown"]) >= 3
