import io
import uuid
import pytest
import pandas as pd
from fastapi.testclient import TestClient

from app.models import CPSE, Material, AuditLog

@pytest.fixture
def sample_cpse(db):
    cpse = CPSE(code=f"CPSE-TEST-{uuid.uuid4()}", name="Test CPSE")
    db.add(cpse)
    db.commit()
    db.refresh(cpse)
    return cpse

def test_csv_upload_succeeds(client: TestClient, db, sample_cpse):
    csv_content = (
        "source_material_code,source_description,source_uom,source_specifications,category\n"
        "V-001,BALL VALVE DN50,EA,Carbon Steel,VALVE\n"
        "V-002,GATE VALVE DN100,EA,Stainless Steel,VALVE\n"
    )

    response = client.post(
        "/api/v1/materials/import",
        data={"cpse_id": str(sample_cpse.id)},
        files={"file": ("test.csv", csv_content.encode("utf-8"), "text/csv")}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total_rows"] == 2
    assert data["imported_rows"] == 2
    assert data["rejected_rows"] == 0

    # Verify in DB
    mats = db.query(Material).filter(Material.cpse_id == sample_cpse.id).all()
    assert len(mats) == 2
    assert mats[0].source_material_code == "V-001"
    assert mats[0].source_description == "BALL VALVE DN50"

    # Verify raw_source_data preserved the row
    assert mats[0].raw_source_data["source_material_code"] == "V-001"

    # Verify audit log
    logs = db.query(AuditLog).filter(AuditLog.entity_id == str(mats[0].id)).all()
    assert len(logs) == 1
    assert logs[0].action == "IMPORT"

def test_xlsx_upload_succeeds(client: TestClient, db, sample_cpse):
    df = pd.DataFrame({
        "source_material_code": ["X-001"],
        "source_description": ["TEST XLSX VALVE"],
        "source_uom": ["NOS"],
        "source_specifications": ["Spec 1"],
        "category": ["VALVE"]
    })

    excel_file = io.BytesIO()
    df.to_excel(excel_file, index=False)
    excel_file.seek(0)

    response = client.post(
        "/api/v1/materials/import",
        data={"cpse_id": str(sample_cpse.id)},
        files={"file": ("test.xlsx", excel_file.read(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    )

    assert response.status_code == 200
    assert response.json()["imported_rows"] == 1

def test_unsupported_file_type_rejected(client: TestClient, sample_cpse):
    response = client.post(
        "/api/v1/materials/import",
        data={"cpse_id": str(sample_cpse.id)},
        files={"file": ("test.txt", b"some content", "text/plain")}
    )
    assert response.status_code == 400
    assert "Unsupported file format" in response.json()["detail"]

def test_oversized_file_rejected(client: TestClient, sample_cpse):
    large_content = b"x" * (6 * 1024 * 1024)  # 6 MB
    response = client.post(
        "/api/v1/materials/import",
        data={"cpse_id": str(sample_cpse.id)},
        files={"file": ("large.csv", large_content, "text/csv")}
    )
    assert response.status_code == 413
    assert "File too large" in response.json()["detail"]

def test_required_columns_validated(client: TestClient, sample_cpse):
    csv_content = "source_material_code,source_description\nV-001,VALVE\n" # Missing source_uom
    response = client.post(
        "/api/v1/materials/import",
        data={"cpse_id": str(sample_cpse.id)},
        files={"file": ("test.csv", csv_content.encode("utf-8"), "text/csv")}
    )
    assert response.status_code == 400
    assert "Missing required columns" in response.json()["detail"]
    assert "source_uom" in response.json()["detail"]

def test_missing_values_remain_null_and_mandatory_fields_reported(client: TestClient, db, sample_cpse):
    csv_content = (
        "source_material_code,source_description,source_uom,source_specifications,category\n"
        ",VALVE NO CODE,EA,Spec,\n" # Missing code
        "V-003,,EA,Spec,\n" # Missing desc
        "V-004,VALVE,EA,,\n" # Valid, specs/category are empty
    )
    response = client.post(
        "/api/v1/materials/import",
        data={"cpse_id": str(sample_cpse.id)},
        files={"file": ("test.csv", csv_content.encode("utf-8"), "text/csv")}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["imported_rows"] == 1
    assert data["rejected_rows"] == 2

    # Error should mention missing mandatory fields
    assert any("Missing mandatory fields" in err["error"] for err in data["errors"])

    mat = db.query(Material).filter(
        Material.source_material_code == "V-004",
        Material.cpse_id == sample_cpse.id
    ).first()
    assert mat is not None
    assert mat.source_specifications is None # NOT "UNKNOWN"
    assert mat.category is None

def test_duplicate_codes_handled(client: TestClient, db, sample_cpse):
    # First import
    csv_1 = "source_material_code,source_description,source_uom\nV-DUP,A,EA\n"
    client.post(
        "/api/v1/materials/import",
        data={"cpse_id": str(sample_cpse.id)},
        files={"file": ("1.csv", csv_1.encode("utf-8"), "text/csv")}
    )

    # Second import with same code + new code
    csv_2 = "source_material_code,source_description,source_uom\nV-DUP,B,EA\nV-NEW,C,EA\n"
    response = client.post(
        "/api/v1/materials/import",
        data={"cpse_id": str(sample_cpse.id)},
        files={"file": ("2.csv", csv_2.encode("utf-8"), "text/csv")}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["imported_rows"] == 1
    assert data["rejected_rows"] == 1
    assert data["duplicate_rows"] == 1
    assert any("Duplicate source_material_code" in e["error"] for e in data["errors"])

    # Verify DB original is untouched
    mat = db.query(Material).filter(Material.source_material_code == "V-DUP").first()
    assert mat.source_description == "A"  # Not overwritten by "B"

def test_invalid_category_rejected(client: TestClient, sample_cpse):
    csv_content = (
        "source_material_code,source_description,source_uom,category\n"
        "V-005,BALL VALVE,EA,PUMP\n"
    )
    response = client.post(
        "/api/v1/materials/import",
        data={"cpse_id": str(sample_cpse.id)},
        files={"file": ("test.csv", csv_content.encode("utf-8"), "text/csv")}
    )
    assert response.status_code == 200
    assert response.json()["rejected_rows"] == 1
    assert "Category must be 'VALVE'" in response.json()["errors"][0]["error"]


def test_header_aliases_case_insensitive(client: TestClient, sample_cpse):
    csv_content = "Material Code,Description,UOM\nCODE1,Desc 1,EA"
    files = {"file": ("test.csv", csv_content.encode(), "text/csv")}
    data = {"cpse_id": str(sample_cpse.id)}

    resp = client.post("/api/v1/materials/import", data=data, files=files)
    assert resp.status_code == 200
    res = resp.json()
    assert res["imported_rows"] == 1

def test_header_aliases_cpse_style(client: TestClient, sample_cpse):
    csv_content = "Material Number,Long Description,Base UOM\nCODE2,Desc 2,NOS"
    files = {"file": ("test.csv", csv_content.encode(), "text/csv")}
    data = {"cpse_id": str(sample_cpse.id)}

    resp = client.post("/api/v1/materials/import", data=data, files=files)
    assert resp.status_code == 200
    res = resp.json()
    assert res["imported_rows"] == 1

def test_header_aliases_whitespace(client: TestClient, sample_cpse):
    csv_content = "\" Material Code \",\" Description \",\" UOM \"\nCODE3,Desc 3,PCS"
    files = {"file": ("test.csv", csv_content.encode(), "text/csv")}
    data = {"cpse_id": str(sample_cpse.id)}

    resp = client.post("/api/v1/materials/import", data=data, files=files)
    assert resp.status_code == 200
    res = resp.json()
    assert res["imported_rows"] == 1

def test_header_aliases_duplicate_rejected(client: TestClient, sample_cpse):
    csv_content = "Material Code,Item Code,Description,UOM\nC1,C2,D,U"
    files = {"file": ("test.csv", csv_content.encode(), "text/csv")}
    data = {"cpse_id": str(sample_cpse.id)}

    resp = client.post("/api/v1/materials/import", data=data, files=files)
    assert resp.status_code == 400
    assert "Ambiguous headers: Multiple columns resolve to source_material_code" in resp.json()["detail"]

def test_header_aliases_missing_required(client: TestClient, sample_cpse):
    csv_content = "Material Code,UOM\nC1,U"
    files = {"file": ("test.csv", csv_content.encode(), "text/csv")}
    data = {"cpse_id": str(sample_cpse.id)}

    resp = client.post("/api/v1/materials/import", data=data, files=files)
    assert resp.status_code == 400
    assert "Missing required columns" in resp.json()["detail"]
    assert "source_description" in resp.json()["detail"]


def test_raw_source_preserves_original_headers(client: TestClient, db, sample_cpse):
    csv_content = "Material Code,Description,UOM\nCODE1_RAW,Desc 1,EA\n"
    files = {"file": ("test.csv", csv_content.encode(), "text/csv")}
    data = {"cpse_id": str(sample_cpse.id)}

    resp = client.post("/api/v1/materials/import", data=data, files=files)
    assert resp.status_code == 200
    res = resp.json()
    assert res["imported_rows"] == 1

    # Verify in DB
    from app.models import Material
    mat = db.query(Material).filter(Material.source_material_code == "CODE1_RAW").first()
    assert mat is not None
    assert mat.source_description == "Desc 1"

    # Verify raw_source_data preserved the original header
    raw = mat.raw_source_data
    assert "Material Code" in raw
    assert raw["Material Code"] == "CODE1_RAW"
    assert "Description" in raw
    assert raw["Description"] == "Desc 1"
    assert "UOM" in raw
    assert raw["UOM"] == "EA"

    # Ensure it did NOT get renamed to canonical inside raw_source_data
    assert "source_material_code" not in raw
    assert "source_description" not in raw
