from typing import Any
from uuid import UUID
from pydantic import BaseModel, ConfigDict

class NationalMaterialListResponse(BaseModel):
    id: UUID
    national_code: str
    category: str | None = None
    canonical_description: str
    status: str | None = None

    model_config = ConfigDict(from_attributes=True)

class MappedSourceMaterialSummary(BaseModel):
    mapping_id: UUID
    material_id: UUID
    cpse_id: UUID
    cpse_code: str
    cpse_name: str
    source_material_code: str
    source_description: str
    mapping_status: str
    mapping_basis: str

    model_config = ConfigDict(from_attributes=True)


class NationalMaterialDetailResponse(BaseModel):
    id: UUID
    national_code: str
    category: str
    canonical_description: str
    normalized_attributes: dict[str, Any] | None = None
    valve_type: str | None = None
    size: str | None = None
    body_material: str | None = None
    pressure_class: str | None = None
    connection_type: str | None = None
    trim: str | None = None
    normalized_uom: str | None = None
    identity_key: str
    status: str | None = None
    mapped_materials: list[MappedSourceMaterialSummary] = []

    model_config = ConfigDict(from_attributes=True)
