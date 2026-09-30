from pydantic import BaseModel, ConfigDict
from typing import List
from uuid import UUID

class InventoryMetrics(BaseModel):
    total_materials: int
    total_cpses: int

class HarmonizationMetrics(BaseModel):
    total_national_materials: int
    total_mapped_materials: int
    automation_rate_percentage: float

class ReviewMetrics(BaseModel):
    pending_reviews: int
    completed_reviews: int

class CPSEBreakdown(BaseModel):
    cpse_id: UUID
    cpse_name: str
    total_materials: int
    mapped_materials: int

class DashboardResponse(BaseModel):
    inventory: InventoryMetrics
    harmonization: HarmonizationMetrics
    review: ReviewMetrics
    cpse_breakdown: List[CPSEBreakdown]

    model_config = ConfigDict(from_attributes=True)
