from pydantic import BaseModel, ConfigDict
from uuid import UUID
from datetime import datetime

class CPSECreate(BaseModel):
    code: str
    name: str

class CPSEResponse(BaseModel):
    id: UUID
    code: str
    name: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CPSEDeleteResponse(BaseModel):
    status: str = "success"
    deleted_id: str
    deleted_type: str = "CPSE"
