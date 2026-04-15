from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class AlertOut(BaseModel):
    id: UUID
    company_id: UUID
    alert_type: str
    alert_text: str
    priority: str
    reviewed: bool
    action_taken: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class AlertReview(BaseModel):
    action_taken: str = ""
