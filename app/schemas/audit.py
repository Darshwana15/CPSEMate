from uuid import UUID
from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, ConfigDict

class AuditLogResponse(BaseModel):
    id: UUID
    actor: str
    action: str
    entity_type: str
    entity_id: str
    before_state: Optional[Any] = None
    after_state: Optional[Any] = None
    reason: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
