from pydantic import BaseModel
from typing import Optional
import uuid

class ReviewActionRequest(BaseModel):
    action: str
    reason: Optional[str] = None
    national_material_id: Optional[uuid.UUID] = None
