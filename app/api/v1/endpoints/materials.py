import uuid
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.material import ImportSummary, MaterialDetailResponse
from app.services.ingestion import process_material_import
from app.services.normalization import normalize_material_record
from app.models import Material, MaterialNationalMapping, MatchRecommendation, NationalMaterial
from app.services.matching import create_match_recommendations
from app.services.harmonization import harmonize_material
from app.services.ai.retrieval import compare_candidate_retrieval
from app.services.ai.shadow import run_shadow_matching_analysis
from app.services.ai.extraction import PatternMaterialExtractor, compare_material_profiles
from app.services.ai.reranking import rerank_candidates_shadow
from app.services.ai.explainability import MaterialExplanationService
router = APIRouter()

MAX_UPLOAD_SIZE = 5 * 1024 * 1024  # 5 MB

@router.post("/import", response_model=ImportSummary)
async def import_materials(
    cpse_id: uuid.UUID = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Ingest a CSV or XLSX file of materials for a specific CPSE.
    """
    # 1. File Type Validation
    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No filename provided.")

    filename_lower = file.filename.lower()
    if not (filename_lower.endswith('.csv') or filename_lower.endswith('.xlsx')):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported file format. Please upload .csv or .xlsx"
        )

    # 2. File Size Validation
    file_contents = await file.read()
    if len(file_contents) > MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"File too large. Maximum size is {MAX_UPLOAD_SIZE // (1024 * 1024)} MB."
        )

    if len(file_contents) == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File is empty.")

    # 3. Process Import
    try:
        summary = process_material_import(
            db=db,
            cpse_id=cpse_id,
            file_contents=file_contents,
            filename=file.filename
        )
        return summary
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        # Avoid exposing raw DB/internal exceptions
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"An unexpected error occurred during import: {str(e)}")

@router.post("/{material_id}/normalize")
def normalize_material(
    material_id: uuid.UUID,
    db: Session = Depends(get_db)
):
    """
    Apply deterministic normalization rules to a single material.
    """
    material = db.query(Material).filter(Material.id == material_id).first()
    if not material:
        raise HTTPException(status_code=404, detail="Material not found")

    try:
        audit_log = normalize_material_record(db, material)
        db.commit()
        return {
            "status": "success",
            "material_id": str(material.id),
            "normalized": audit_log is not None
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Normalization failed: {str(e)}")



@router.post("/{material_id}/match")
def match_material(
    material_id: uuid.UUID,
    db: Session = Depends(get_db)
):
    """
    Generate and persist match recommendations for a single material.
    """
    material = db.query(Material).filter(Material.id == material_id).first()
    if not material:
        raise HTTPException(status_code=404, detail="Material not found")

    try:
        recommendations = create_match_recommendations(db, material)
        db.commit()

        return {
            "status": "success",
            "material_id": str(material.id),
            "candidate_count": len(recommendations),
            "recommendations_created": len(recommendations),
            "recommendations": [
                {
                    "candidate_id": str(r.candidate_material_id),
                    "classification": r.classification,
                    "confidence": float(r.confidence) if r.confidence is not None else 0.0,
                    "explanation": r.explanation
                }
                for r in recommendations
            ]
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Matching failed: {str(e)}")


@router.get("/{material_id}/candidate-comparison")
def compare_candidates_endpoint(
    material_id: uuid.UUID,
    top_k: int | None = None,
    min_similarity: float | None = None,
    db: Session = Depends(get_db)
):
    """
    Phase 2A Diagnostic: Compare baseline deterministic candidate retrieval
    against parallel AI semantic candidate retrieval.
    Does NOT mutate mappings or create recommendations.
    """
    material = db.query(Material).filter(Material.id == material_id).first()
    if not material:
        raise HTTPException(status_code=404, detail="Material not found")

    try:
        result = compare_candidate_retrieval(
            db=db,
            source=material,
            top_k=top_k,
            min_similarity=min_similarity,
        )
        return {
            "status": "success",
            **result.to_dict(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Candidate comparison failed: {str(e)}")


@router.get("/{material_id}/shadow-match")
def shadow_match_endpoint(
    material_id: uuid.UUID,
    top_k: int | None = None,
    min_similarity: float | None = None,
    category_filter: bool = True,
    db: Session = Depends(get_db)
):
    """
    Phase 2C Diagnostic: Shadow analysis comparing baseline match recommendations
    against hypothetical hybrid union (Baseline UNION AI) recommendations.
    Executes in memory: does NOT persist recommendations or mutate mappings.
    """
    material = db.query(Material).filter(Material.id == material_id).first()
    if not material:
        raise HTTPException(status_code=404, detail="Material not found")

    try:
        report = run_shadow_matching_analysis(
            db=db,
            source=material,
            top_k=top_k,
            min_similarity=min_similarity,
            category_filter=category_filter,
        )
        return {
            "status": "success",
            **report.to_dict(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Shadow matching analysis failed: {str(e)}")


@router.get("/{material_id}/ai-profile")
def get_material_ai_profile_endpoint(
    material_id: uuid.UUID,
    db: Session = Depends(get_db)
):
    """
    Phase 3A Diagnostic: Shadow-mode AI material profile extraction and comparison.
    Extracts structured attributes from source description and compares against
    existing deterministic normalization. Does NOT mutate database state.
    """
    material = db.query(Material).filter(Material.id == material_id).first()
    if not material:
        raise HTTPException(status_code=404, detail="Material not found")

    try:
        extractor = PatternMaterialExtractor()
        source_text = material.source_description or material.normalized_description or ""
        ai_profile = extractor.extract(
            text=source_text,
            source_uom=material.source_uom,
            category_hint=material.category,
        )
        report = compare_material_profiles(material, ai_profile)
        return {
            "status": "success",
            **report.to_dict(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI profile extraction failed: {str(e)}")


@router.get("/{material_id}/semantic-reranking")
def get_material_semantic_reranking_endpoint(
    material_id: uuid.UUID,
    top_k: int = 15,
    db: Session = Depends(get_db)
):
    """
    Phase 3B Diagnostic: Shadow-mode semantic reranking and candidate comparison.
    Reranks retrieved candidates using dense semantic similarity and evaluates
    authoritative engineering constraints. Does NOT mutate database state or recommendations.
    """
    material = db.query(Material).filter(Material.id == material_id).first()
    if not material:
        raise HTTPException(status_code=404, detail="Material not found")

    try:
        report = rerank_candidates_shadow(
            db=db,
            source=material,
            top_k=top_k,
        )
        return {
            "status": "success",
            **report.to_dict(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Semantic reranking analysis failed: {str(e)}")


@router.get("/{material_id}/candidate-explanation/{candidate_id}")
def get_candidate_explanation_endpoint(
    material_id: uuid.UUID,
    candidate_id: uuid.UUID,
    db: Session = Depends(get_db)
):
    """
    Phase 4: Structured AI Explainability & Reviewer Intelligence endpoint.
    Returns attribute-level comparisons, physical engineering conflicts, semantic evidence,
    and audit trail for a material pair. Does NOT mutate database state.
    """
    source = db.query(Material).filter(Material.id == material_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="Source material not found")

    candidate = db.query(Material).filter(Material.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate material not found")

    try:
        service = MaterialExplanationService()
        explanation = service.generate_explanation(source=source, candidate=candidate)
        return {
            "status": "success",
            **explanation.to_dict(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate explanation: {str(e)}")


@router.post("/{material_id}/harmonize")
def harmonize_material_endpoint(
    material_id: uuid.UUID,
    db: Session = Depends(get_db)
):
    """
    Attempt to safely auto-harmonize the material.
    """
    material = db.query(Material).filter(Material.id == material_id).first()
    if not material:
        raise HTTPException(status_code=404, detail="Material not found")

    try:
        result = harmonize_material(db, material)
        db.commit()
        return result
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Harmonization failed: {str(e)}")



@router.get("/{material_id}", response_model=MaterialDetailResponse, status_code=status.HTTP_200_OK)
def get_material(
    material_id: uuid.UUID,
    db: Session = Depends(get_db)
):
    """
    Get full details for a single material with authoritative harmonization status.
    """
    material = db.query(Material).filter(Material.id == material_id).first()
    if not material:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Material not found")

    # Check active mapping
    mapping = db.query(
        MaterialNationalMapping.material_id,
        NationalMaterial.id.label("nm_id"),
        NationalMaterial.national_code
    ).join(
        NationalMaterial, MaterialNationalMapping.national_material_id == NationalMaterial.id
    ).filter(
        MaterialNationalMapping.material_id == material_id,
        MaterialNationalMapping.status == "ACTIVE"
    ).first()

    if mapping:
        m_status = "MAPPED"
        nm_code = mapping.national_code
        nm_id = mapping.nm_id
    else:
        nm_code, nm_id = None, None
        recs = db.query(
            MatchRecommendation.classification
        ).filter(
            (MatchRecommendation.source_material_id == material_id) |
            (MatchRecommendation.candidate_material_id == material_id)
        ).all()
        classifications = [r.classification for r in recs]
        if "POTENTIALLY_EQUIVALENT" in classifications:
            m_status = "NEEDS REVIEW"
        elif "DIFFERENT" in classifications:
            m_status = "DIFFERENT"
        elif material.normalized_description and material.normalized_description.strip():
            m_status = "UNMATCHED"
        else:
            m_status = "NOT PROCESSED"

    res = MaterialDetailResponse.model_validate(material)
    res.mapping_status = m_status
    res.national_material_code = nm_code
    res.national_material_id = nm_id
    return res


from app.schemas.material import MaterialMappingHistory, MaterialDeleteResponse
from typing import List
from app.models import MaterialNationalMapping, MatchRecommendation
from app.api.deps import get_current_reviewer

@router.get("/{material_id}/mapping-history", response_model=List[MaterialMappingHistory])
def get_material_mapping_history(
    material_id: uuid.UUID,
    db: Session = Depends(get_db)
):
    """
    Get the mapping history for a single material.
    """
    material = db.query(Material).filter(Material.id == material_id).first()
    if not material:
        raise HTTPException(status_code=404, detail="Material not found")

    history = db.query(MaterialNationalMapping).filter(
        MaterialNationalMapping.material_id == material_id
    ).order_by(MaterialNationalMapping.created_at.desc()).all()
    return history


@router.delete("/{material_id}", response_model=MaterialDeleteResponse, status_code=status.HTTP_200_OK)
def delete_material(
    material_id: uuid.UUID,
    db: Session = Depends(get_db),
    reviewer: str = Depends(get_current_reviewer)
):
    """
    Delete a single Material and its dependent operational data.
    Atomically removes:
    1. Dependent MaterialNationalMapping rows for this material
    2. Dependent MatchRecommendation rows where this material is source or candidate
    3. The Material record
    National Materials and AuditLog rows are preserved.
    """
    material = db.query(Material).filter(Material.id == material_id).first()
    if not material:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Material not found")

    try:
        # 1. Delete dependent MaterialNationalMapping rows
        db.query(MaterialNationalMapping).filter(
            MaterialNationalMapping.material_id == material_id
        ).delete(synchronize_session=False)

        # 2. Delete dependent MatchRecommendation rows
        db.query(MatchRecommendation).filter(
            (MatchRecommendation.source_material_id == material_id) |
            (MatchRecommendation.candidate_material_id == material_id)
        ).delete(synchronize_session=False)

        # 3. Delete the Material
        db.delete(material)
        db.commit()

        return MaterialDeleteResponse(
            status="success",
            deleted_id=str(material_id),
            deleted_type="MATERIAL"
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete material: {str(e)}"
        )

@router.post("/{material_id}/unmap")
def unmap_material(
    material_id: uuid.UUID,
    db: Session = Depends(get_db),
    reviewer: str = Depends(get_current_reviewer)
):
    """
    Deactivates any active mapping for this material and records an audit log.
    """
    material = db.query(Material).filter(Material.id == material_id).first()
    if not material:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Material not found")

    mapping = db.query(MaterialNationalMapping).filter_by(
        material_id=material_id, status="ACTIVE"
    ).first()
    if not mapping:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Material does not have an active mapping.")

    mapping.status = "INACTIVE"
    db.add(AuditLog(
        id=uuid.uuid4(),
        actor=reviewer,
        action="UNMAP",
        entity_type="MATERIAL_NATIONAL_MAPPING",
        entity_id=str(mapping.id),
        before_state={"status": "ACTIVE", "national_material_id": str(mapping.national_material_id)},
        after_state={"status": "INACTIVE"},
        reason="Human unmapped material"
    ))
    db.commit()
    return {"status": "success", "action": "UNMAP", "mapping_id": str(mapping.id)}
