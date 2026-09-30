from pydantic import BaseModel, ConfigDict, model_validator
from typing import List, Optional, Any
from datetime import datetime
import uuid

class ImportRowError(BaseModel):
    row: int
    error: str

class ImportSummary(BaseModel):
    total_rows: int
    imported_rows: int
    rejected_rows: int
    duplicate_rows: int
    errors: List[ImportRowError]

class MaterialListResponse(BaseModel):
    id: uuid.UUID
    cpse_id: uuid.UUID
    source_material_code: str
    source_description: str
    category: Optional[str] = None
    normalized_description: Optional[str] = None
    mapping_status: Optional[str] = None
    national_material_code: Optional[str] = None
    national_material_id: Optional[uuid.UUID] = None

    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="after")
    def populate_category_if_none(self) -> "MaterialListResponse":
        # In SQL schema, material.category can be None for categories outside DB_ALLOWED_CATEGORIES
        # If available on the ORM object, fetch it
        return self



class MaterialDetailResponse(BaseModel):
    id: uuid.UUID
    cpse_id: uuid.UUID
    source_material_code: str
    source_description: str
    source_uom: str
    source_specifications: Optional[str] = None
    raw_source_data: Optional[Any] = None

    category: Optional[str] = None

    valve_type: Optional[str] = None
    size: Optional[str] = None
    body_material: Optional[str] = None
    pressure_class: Optional[str] = None
    connection_type: Optional[str] = None
    trim: Optional[str] = None

    normalized_uom: Optional[str] = None
    normalized_description: Optional[str] = None
    normalized_attributes: Optional[Any] = None

    mapping_status: Optional[str] = None
    national_material_code: Optional[str] = None
    national_material_id: Optional[uuid.UUID] = None

    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="after")
    def populate_fields_from_normalized_attributes(self) -> "MaterialDetailResponse":
        if self.normalized_attributes and isinstance(self.normalized_attributes, dict):
            raw_attrs = self.normalized_attributes
            if not self.category and raw_attrs.get("category"):
                self.category = raw_attrs.get("category")
            if not self.valve_type and (raw_attrs.get("type") or raw_attrs.get("material_type")):
                self.valve_type = raw_attrs.get("type") or raw_attrs.get("material_type")
            if not self.size and raw_attrs.get("size"):
                self.size = raw_attrs.get("size")
            if not self.pressure_class and (raw_attrs.get("pressure_rating") or raw_attrs.get("pressure_class")):
                self.pressure_class = raw_attrs.get("pressure_rating") or raw_attrs.get("pressure_class")
            if not self.body_material and (raw_attrs.get("material_grade") or raw_attrs.get("casing_material")):
                self.body_material = raw_attrs.get("material_grade") or raw_attrs.get("casing_material")
            if not self.connection_type and (raw_attrs.get("facing_connection") or raw_attrs.get("connection_type")):
                self.connection_type = raw_attrs.get("facing_connection") or raw_attrs.get("connection_type")
            if not self.trim and raw_attrs.get("trim"):
                self.trim = raw_attrs.get("trim")
        return self


class MaterialMappingHistory(BaseModel):
    id: uuid.UUID
    material_id: uuid.UUID
    national_material_id: uuid.UUID
    basis: str
    status: str
    recommendation_id: Optional[uuid.UUID] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MaterialDeleteResponse(BaseModel):
    status: str = "success"
    deleted_id: str
    deleted_type: str = "MATERIAL"
