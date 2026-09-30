from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import NationalMaterial, MaterialNationalMapping, Material, CPSE
from app.schemas.national_material import (
    NationalMaterialListResponse,
    NationalMaterialDetailResponse,
    MappedSourceMaterialSummary
)

router = APIRouter()

@router.get("", response_model=List[NationalMaterialListResponse])
def get_national_materials(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """
    Get a list of national materials.
    """
    materials = db.query(NationalMaterial).offset(skip).limit(limit).all()
    return materials

@router.get("/{national_material_id}", response_model=NationalMaterialDetailResponse)
def get_national_material(
    national_material_id: UUID,
    db: Session = Depends(get_db)
):
    """
    Get a single national material by ID, including its actively mapped source materials.
    """
    material = db.query(NationalMaterial).filter(NationalMaterial.id == national_material_id).first()
    if not material:
        raise HTTPException(status_code=404, detail="National material not found")

    mappings = db.query(
        MaterialNationalMapping.id.label("mapping_id"),
        MaterialNationalMapping.material_id,
        MaterialNationalMapping.status.label("mapping_status"),
        MaterialNationalMapping.basis.label("mapping_basis"),
        Material.cpse_id,
        Material.source_material_code,
        Material.source_description,
        CPSE.code.label("cpse_code"),
        CPSE.name.label("cpse_name")
    ).join(
        Material, MaterialNationalMapping.material_id == Material.id
    ).join(
        CPSE, Material.cpse_id == CPSE.id
    ).filter(
        MaterialNationalMapping.national_material_id == national_material_id,
        MaterialNationalMapping.status == "ACTIVE"
    ).order_by(
        CPSE.name, Material.source_material_code
    ).all()

    mapped_list = [
        MappedSourceMaterialSummary(
            mapping_id=m.mapping_id,
            material_id=m.material_id,
            cpse_id=m.cpse_id,
            cpse_code=m.cpse_code,
            cpse_name=m.cpse_name,
            source_material_code=m.source_material_code,
            source_description=m.source_description,
            mapping_status=m.mapping_status,
            mapping_basis=m.mapping_basis
        )
        for m in mappings
    ]

    res = NationalMaterialDetailResponse.model_validate(material)
    res.mapped_materials = mapped_list
    return res

