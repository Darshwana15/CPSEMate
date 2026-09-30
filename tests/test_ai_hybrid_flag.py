import uuid
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.models import CPSE, Material, MatchRecommendation, MaterialNationalMapping
from app.services.matching import create_match_recommendations


@pytest.fixture
def cpse_source(db):
    c = CPSE(code=f"CPSE-SRC-FLAG-{uuid.uuid4().hex[:6]}", name="Source CPSE")
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


@pytest.fixture
def cpse_target(db):
    c = CPSE(code=f"CPSE-TGT-FLAG-{uuid.uuid4().hex[:6]}", name="Target CPSE")
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


def create_material(db, cpse, desc: str, cat: str = "VALVE", **kwargs) -> Material:
    mat = Material(
        id=uuid.uuid4(),
        cpse_id=cpse.id,
        source_material_code=f"MAT-FLAG-{uuid.uuid4().hex[:6]}",
        source_description=desc,
        source_uom="EA",
        category=cat,
        normalized_description=desc,
        normalized_uom="EA",
        valve_type=kwargs.get("valve_type"),
        size=kwargs.get("size"),
        body_material=kwargs.get("body_material"),
        pressure_class=kwargs.get("pressure_class"),
        connection_type=kwargs.get("connection_type"),
        trim=kwargs.get("trim"),
    )
    db.add(mat)
    db.commit()
    db.refresh(mat)
    return mat


def test_feature_flag_default_is_disabled():
    """Default configuration MUST be false."""
    assert settings.ai_hybrid_retrieval_enabled is False
    assert settings.AI_HYBRID_RETRIEVAL_ENABLED is False


def test_production_matching_uses_baseline_when_flag_disabled(db, cpse_source, cpse_target):
    """When flag is False, production matching only evaluates baseline SQL candidates."""
    tag = uuid.uuid4().hex[:6]
    src = create_material(
        db, cpse_source,
        desc=f"GATE VALVE {tag} DN50 CS CLASS150 RF",
        valve_type="GATE", size="DN50"
    )

    # Candidate 1: Category VALVE with valve_type GATE (baseline SQL matches)
    cand_base = create_material(
        db, cpse_target,
        desc=f"GATE VALVE {tag} DN50 CS CLASS150 RF",
        valve_type="GATE", size="DN50"
    )

    # Candidate 2: Incompatible valve_type GLOBE in baseline SQL filter,
    # but high textual similarity
    cand_other = create_material(
        db, cpse_target,
        desc=f"GLOBE VALVE {tag} DN50 CS CLASS150 RF",
        valve_type="GLOBE", size="DN50"
    )

    with patch.object(settings, "ai_hybrid_retrieval_enabled", False):
        recs = create_match_recommendations(db, src)
        db.commit()

        rec_cand_ids = [r.candidate_material_id for r in recs]
        assert cand_base.id in rec_cand_ids
        # Baseline SQL filter excludes GLOBE when source valve_type is GATE
        assert cand_other.id not in rec_cand_ids


def test_production_matching_uses_hybrid_when_flag_enabled(db, cpse_source, cpse_target):
    """When flag is True, AI semantic candidates are pulled into production recommendations."""
    tag = uuid.uuid4().hex[:6]
    src = create_material(
        db, cpse_source,
        desc=f"HEX HEAD BOLT M16 X 50MM SS316 {tag}",
        cat="FASTENER",
    )

    # Candidate 1: Baseline candidate (exact category match)
    cand_base = create_material(
        db, cpse_target,
        desc=f"HEX HEAD BOLT M16 X 50MM SS316 {tag}",
        cat="FASTENER",
    )

    # Candidate 2: Distinct phrasing, discovered by semantic retrieval
    cand_ai = create_material(
        db, cpse_target,
        desc=f"FASTENER HEXAGONAL BOLT M16X50MM SS316 {tag}",
        cat="FASTENER",
    )

    with patch.object(settings, "ai_hybrid_retrieval_enabled", True):
        recs = create_match_recommendations(db, src)
        db.commit()

        rec_cand_ids = [r.candidate_material_id for r in recs]
        # Baseline candidate present
        assert cand_base.id in rec_cand_ids
        # AI candidate discovered and classified
        assert cand_ai.id in rec_cand_ids


def test_hard_engineering_conflict_remains_different_when_discovered_by_ai(db, cpse_source, cpse_target):
    """An AI candidate with a hard engineering conflict must be classified as DIFFERENT with 0 confidence."""
    src = create_material(
        db, cpse_source,
        desc="BALL VALVE DN50 CS CLASS150 RF",
        valve_type="BALL", size="DN50", body_material="CARBON_STEEL", pressure_class="CLASS150"
    )

    # Candidate with hard size conflict (DN100 / 4 IN vs DN50 / 2 IN)
    cand_size_conflict = create_material(
        db, cpse_target,
        desc="BALL VALVE DN100 CS CLASS150 RF",
        valve_type="BALL", size="DN100", body_material="CARBON_STEEL", pressure_class="CLASS150"
    )

    with patch.object(settings, "ai_hybrid_retrieval_enabled", True):
        recs = create_match_recommendations(db, src)
        db.commit()

        target_rec = next((r for r in recs if r.candidate_material_id == cand_size_conflict.id), None)
        assert target_rec is not None
        assert target_rec.classification == "DIFFERENT"
        assert target_rec.confidence == 0.0
        assert "size conflict" in target_rec.explanation.lower()


def test_ai_failure_falls_back_safely_to_baseline(db, cpse_source, cpse_target):
    """If AI semantic retrieval throws an exception, system logs warning and safely falls back to baseline."""
    src = create_material(
        db, cpse_source,
        desc="CHECK VALVE DN50 CS CLASS150",
        valve_type="CHECK", size="DN50"
    )
    cand_base = create_material(
        db, cpse_target,
        desc="CHECK VALVE DN50 CS CLASS150",
        valve_type="CHECK", size="DN50"
    )

    with patch.object(settings, "ai_hybrid_retrieval_enabled", True):
        with patch("app.services.ai.retrieval.generate_semantic_candidates", side_effect=RuntimeError("GPU OOM")):
            # Must NOT crash or raise RuntimeError
            recs = create_match_recommendations(db, src)
            db.commit()

            rec_cand_ids = [r.candidate_material_id for r in recs]
            assert cand_base.id in rec_cand_ids


def test_post_match_api_endpoint_respects_flag(db, cpse_source, cpse_target):
    """API endpoint POST /api/v1/materials/{id}/match operates seamlessly under both flag states."""
    client = TestClient(app)
    src = create_material(db, cpse_source, "NEEDLE VALVE 1/2 IN SS316 6000# NPT", valve_type="NEEDLE")
    cand = create_material(db, cpse_target, "NEEDLE VALVE 1/2 IN SS316 6000# NPT", valve_type="NEEDLE")

    # 1. With flag = False
    with patch.object(settings, "ai_hybrid_retrieval_enabled", False):
        resp = client.post(f"/api/v1/materials/{src.id}/match")
        assert resp.status_code == 200
        data = resp.json()
        assert "recommendations" in data

    # 2. With flag = True
    src2 = create_material(db, cpse_source, "NEEDLE VALVE 1/4 IN SS316 6000# NPT", valve_type="NEEDLE")
    with patch.object(settings, "ai_hybrid_retrieval_enabled", True):
        resp = client.post(f"/api/v1/materials/{src2.id}/match")
        assert resp.status_code == 200
        data = resp.json()
        assert "recommendations" in data


def test_mapping_and_harmonization_pipeline_intact_with_hybrid_flag(db, cpse_source, cpse_target):
    """Recommendations produced when hybrid is enabled seamlessly flow into the existing harmonization pipeline."""
    from app.services.harmonization import harmonize_material
    from app.models import AuditLog

    tag = uuid.uuid4().hex[:6]
    # Exact equivalent materials
    src = create_material(
        db, cpse_source,
        desc=f"BALL VALVE {tag} DN50 CS CLASS150 RF SS316",
        valve_type="BALL", size="DN50", body_material="CARBON_STEEL",
        pressure_class="CLASS150", connection_type="RF", trim="SS316"
    )
    cand = create_material(
        db, cpse_target,
        desc=f"BALL VALVE {tag} DN50 CS CLASS150 RF SS316",
        valve_type="BALL", size="DN50", body_material="CARBON_STEEL",
        pressure_class="CLASS150", connection_type="RF", trim="SS316"
    )

    with patch.object(settings, "ai_hybrid_retrieval_enabled", True):
        recs = create_match_recommendations(db, src)
        db.commit()

        # Find the SAME recommendation
        same_rec = next((r for r in recs if r.candidate_material_id == cand.id and r.classification == "SAME"), None)
        assert same_rec is not None

        # Harmonize material
        result = harmonize_material(db, src)
        db.commit()

        assert result["status"] == "success"
        mapping = db.query(MaterialNationalMapping).filter_by(material_id=src.id, status="ACTIVE").first()
        assert mapping is not None
        assert mapping.status == "ACTIVE"

        # Check audit log
        audit = db.query(AuditLog).filter(AuditLog.entity_id == str(mapping.id)).first()
        assert audit is not None
        assert audit.action == "CREATE_MAPPING"
