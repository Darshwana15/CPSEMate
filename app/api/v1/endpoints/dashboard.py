from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List

from app.db.session import get_db
from app.models import (
    Material,
    CPSE,
    NationalMaterial,
    MaterialNationalMapping,
    MatchRecommendation,
    AuditLog
)
from app.schemas.dashboard import (
    DashboardResponse,
    InventoryMetrics,
    HarmonizationMetrics,
    ReviewMetrics,
    CPSEBreakdown
)

router = APIRouter()

@router.get("", response_model=DashboardResponse)
def get_dashboard(db: Session = Depends(get_db)):
    # 1. Inventory
    total_materials = db.query(func.count(Material.id)).scalar() or 0
    total_cpses = db.query(func.count(CPSE.id)).scalar() or 0

    # 2. Harmonization
    total_national_materials = db.query(func.count(NationalMaterial.id)).scalar() or 0

    # Mapped materials: distinct Material IDs having an ACTIVE mapping
    active_mappings_query = db.query(MaterialNationalMapping.material_id).filter(
        MaterialNationalMapping.status == "ACTIVE"
    )
    total_mapped_materials = db.query(func.count(func.distinct(MaterialNationalMapping.material_id))).filter(
        MaterialNationalMapping.status == "ACTIVE"
    ).scalar() or 0

    # Automation Rate: AUTO_SAME active / total active * 100
    total_active_mappings = db.query(func.count(MaterialNationalMapping.id)).filter(
        MaterialNationalMapping.status == "ACTIVE"
    ).scalar() or 0

    auto_same_mappings = db.query(func.count(MaterialNationalMapping.id)).filter(
        MaterialNationalMapping.status == "ACTIVE",
        MaterialNationalMapping.basis == "AUTO_SAME"
    ).scalar() or 0

    automation_rate = 0.0
    if total_active_mappings > 0:
        automation_rate = round((auto_same_mappings / total_active_mappings) * 100.0, 1)

    # 3. Review
    # Pending reviews: unresolved POTENTIALLY_EQUIVALENT recommendations where source is unmapped
    pending_reviews = db.query(func.count(MatchRecommendation.id)).filter(
        MatchRecommendation.classification == "POTENTIALLY_EQUIVALENT",
        MatchRecommendation.source_material_id.notin_(active_mappings_query)
    ).scalar() or 0


    # Completed reviews: distinct recommendations that have an explicit human action in AuditLog
    completed_reviews = db.query(func.count(func.distinct(AuditLog.entity_id))).filter(
        AuditLog.entity_type == "MATCH_RECOMMENDATION",
        AuditLog.action.in_(["ACCEPT", "OVERRIDE", "REJECT", "MARK_DIFFERENT"])
    ).scalar() or 0

    # 4. CPSE Breakdown
    cpses = db.query(CPSE).order_by(CPSE.name).all()
    breakdown = []

    for cpse in cpses:
        cpse_materials = db.query(func.count(Material.id)).filter(Material.cpse_id == cpse.id).scalar() or 0
        cpse_mapped = db.query(func.count(func.distinct(MaterialNationalMapping.material_id))).join(
            Material, MaterialNationalMapping.material_id == Material.id
        ).filter(
            MaterialNationalMapping.status == "ACTIVE",
            Material.cpse_id == cpse.id
        ).scalar() or 0

        breakdown.append(CPSEBreakdown(
            cpse_id=cpse.id,
            cpse_name=cpse.name,
            total_materials=cpse_materials,
            mapped_materials=cpse_mapped
        ))

    return DashboardResponse(
        inventory=InventoryMetrics(
            total_materials=total_materials,
            total_cpses=total_cpses
        ),
        harmonization=HarmonizationMetrics(
            total_national_materials=total_national_materials,
            total_mapped_materials=total_mapped_materials,
            automation_rate_percentage=automation_rate
        ),
        review=ReviewMetrics(
            pending_reviews=pending_reviews,
            completed_reviews=completed_reviews
        ),
        cpse_breakdown=breakdown
    )
