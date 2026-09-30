from typing import List
import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.db.session import get_db
from app.api.deps import get_current_reviewer
from app.models import CPSE, Material, MatchRecommendation, MaterialNationalMapping, NationalMaterial
from app.schemas.cpse import CPSECreate, CPSEResponse, CPSEDeleteResponse
from app.schemas.material import MaterialListResponse

router = APIRouter()

@router.post("", response_model=CPSEResponse, status_code=status.HTTP_201_CREATED)
def create_cpse(
    cpse_in: CPSECreate,
    db: Session = Depends(get_db)
):
    """
    Create a new CPSE.
    """
    # Check for duplicate code
    existing = db.query(CPSE).filter(CPSE.code == cpse_in.code).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"CPSE with code '{cpse_in.code}' already exists."
        )

    new_cpse = CPSE(
        id=uuid.uuid4(),
        code=cpse_in.code,
        name=cpse_in.name
    )
    db.add(new_cpse)
    try:
        db.commit()
        db.refresh(new_cpse)
        return new_cpse
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"CPSE with code '{cpse_in.code}' already exists."
        )


@router.get("", response_model=List[CPSEResponse], status_code=status.HTTP_200_OK)
def list_cpses(
    db: Session = Depends(get_db)
):
    """
    List all available CPSEs ordered by name.
    """
    return db.query(CPSE).order_by(CPSE.name).all()


@router.get("/{cpse_id}/materials", response_model=List[MaterialListResponse], status_code=status.HTTP_200_OK)
def list_cpse_materials(
    cpse_id: uuid.UUID,
    db: Session = Depends(get_db)
):
    """
    List materials for a specific CPSE with authoritative harmonization and review status.
    """
    cpse = db.query(CPSE).filter(CPSE.id == cpse_id).first()
    if not cpse:
        raise HTTPException(status_code=404, detail="CPSE not found")

    materials = db.query(Material).filter(Material.cpse_id == cpse_id).order_by(Material.source_material_code).all()
    if not materials:
        return []

    mat_ids = [m.id for m in materials]

    # Active National Mappings
    mappings = db.query(
        MaterialNationalMapping.material_id,
        NationalMaterial.id.label("nm_id"),
        NationalMaterial.national_code
    ).join(
        NationalMaterial, MaterialNationalMapping.national_material_id == NationalMaterial.id
    ).filter(
        MaterialNationalMapping.material_id.in_(mat_ids),
        MaterialNationalMapping.status == "ACTIVE"
    ).all()
    mapping_dict = {row.material_id: (row.national_code, row.nm_id) for row in mappings}

    # Match recommendations for materials without active mappings
    unmapped_ids = [mid for mid in mat_ids if mid not in mapping_dict]
    rec_status_dict = {}
    if unmapped_ids:
        recs = db.query(
            MatchRecommendation.source_material_id,
            MatchRecommendation.candidate_material_id,
            MatchRecommendation.classification
        ).filter(
            (MatchRecommendation.source_material_id.in_(unmapped_ids)) |
            (MatchRecommendation.candidate_material_id.in_(unmapped_ids))
        ).all()
        for src_id, cand_id, classification in recs:
            for mid in (src_id, cand_id):
                if mid in unmapped_ids:
                    curr = rec_status_dict.get(mid)
                    if classification == "POTENTIALLY_EQUIVALENT":
                        rec_status_dict[mid] = "NEEDS REVIEW"
                    elif classification == "DIFFERENT" and curr != "NEEDS REVIEW":
                        rec_status_dict[mid] = "DIFFERENT"

    results = []
    for m in materials:
        if m.id in mapping_dict:
            nm_code, nm_id = mapping_dict[m.id]
            m_status = "MAPPED"
        elif m.id in rec_status_dict:
            nm_code, nm_id = None, None
            m_status = rec_status_dict[m.id]
        elif m.normalized_description and m.normalized_description.strip():
            nm_code, nm_id = None, None
            m_status = "UNMATCHED"
        else:
            nm_code, nm_id = None, None
            m_status = "NOT PROCESSED"

        cat = m.category
        if not cat and m.normalized_attributes and isinstance(m.normalized_attributes, dict):
            cat = m.normalized_attributes.get("category")

        results.append(MaterialListResponse(
            id=m.id,
            cpse_id=m.cpse_id,
            source_material_code=m.source_material_code,
            source_description=m.source_description,
            category=cat,
            normalized_description=m.normalized_description,
            mapping_status=m_status,
            national_material_code=nm_code,
            national_material_id=nm_id
        ))

    return results




@router.delete("/{cpse_id}", response_model=CPSEDeleteResponse, status_code=status.HTTP_200_OK)
def delete_cpse(
    cpse_id: uuid.UUID,
    db: Session = Depends(get_db),
    reviewer: str = Depends(get_current_reviewer)
):
    """
    Delete a CPSE and its source-material operational data.
    Atomically removes:
    1. Dependent MaterialNationalMapping rows for CPSE materials
    2. Dependent MatchRecommendation rows for CPSE materials
    3. Source Material rows for the CPSE
    4. The CPSE record
    National Materials and AuditLog rows are preserved.
    """
    cpse = db.query(CPSE).filter(CPSE.id == cpse_id).first()
    if not cpse:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="CPSE not found")

    try:
        # Collect material IDs belonging to this CPSE
        material_ids = [m[0] for m in db.query(Material.id).filter(Material.cpse_id == cpse_id).all()]

        if material_ids:
            # 1. Delete dependent MaterialNationalMapping rows
            db.query(MaterialNationalMapping).filter(
                MaterialNationalMapping.material_id.in_(material_ids)
            ).delete(synchronize_session=False)

            # 2. Delete dependent MatchRecommendation rows (either source or candidate)
            db.query(MatchRecommendation).filter(
                (MatchRecommendation.source_material_id.in_(material_ids)) |
                (MatchRecommendation.candidate_material_id.in_(material_ids))
            ).delete(synchronize_session=False)

            # 3. Delete CPSE materials
            db.query(Material).filter(Material.cpse_id == cpse_id).delete(synchronize_session=False)

        # 4. Delete the CPSE
        db.delete(cpse)
        db.commit()

        return CPSEDeleteResponse(
            status="success",
            deleted_id=str(cpse_id),
            deleted_type="CPSE"
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete CPSE: {str(e)}"
        )
