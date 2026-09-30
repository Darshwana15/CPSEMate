import uuid
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.api.deps import get_current_reviewer
from app.schemas.review import ReviewActionRequest
from app.models import MatchRecommendation, Material
from app.services.review import get_review_queue, process_review_action
from app.services.ai.explainability import MaterialExplanationService

router = APIRouter()


@router.get("/queue")
def read_review_queue(
    cpse_id: uuid.UUID | None = Query(None),
    classification: str | None = Query(None),
    limit: int = Query(500, ge=1, le=1000),
    db: Session = Depends(get_db),
    reviewer_id: str = Depends(get_current_reviewer)
):
    """
    Returns recommendations requiring human action.
    """
    try:
        return {"queue": get_review_queue(db, limit=limit, classification=classification, cpse_id=cpse_id)}
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to fetch review queue")


@router.get("/{recommendation_id}/explanation")
def get_recommendation_explanation(
    recommendation_id: uuid.UUID,
    db: Session = Depends(get_db),
    reviewer_id: str = Depends(get_current_reviewer)
):
    """
    Phase 4: Returns structured AI explainability, attribute comparisons,
    and authoritative engineering conflict evidence for a recommendation in the review queue.
    """
    rec = db.get(MatchRecommendation, recommendation_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Recommendation not found")

    source = db.get(Material, rec.source_material_id)
    candidate = db.get(Material, rec.candidate_material_id)
    if not source or not candidate:
        raise HTTPException(status_code=404, detail="Source or candidate material not found")

    try:
        service = MaterialExplanationService()
        explanation = service.generate_explanation(
            source=source,
            candidate=candidate,
            retrieval_source="REVIEW_RECOMMENDATION",
        )
        return {
            "status": "success",
            "recommendation_id": str(rec.id),
            **explanation.to_dict(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate review explanation: {str(e)}")


@router.post("/{recommendation_id}/action")
def perform_review_action(
    recommendation_id: uuid.UUID,
    req: ReviewActionRequest,
    db: Session = Depends(get_db),
    reviewer_id: str = Depends(get_current_reviewer)
):
    """
    Performs a human review action (ACCEPT, REJECT, MARK_DIFFERENT, OVERRIDE).
    """
    try:
        result = process_review_action(
            db=db,
            recommendation_id=recommendation_id,
            action=req.action,
            reason=req.reason or "",
            national_material_id=req.national_material_id,
            actor=reviewer_id
        )
        return result
    except ValueError as ve:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Review action failed")
