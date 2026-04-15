from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import BaseModel


class SignalOut(BaseModel):
    id: UUID
    company_id: UUID
    signal_type: str
    current_value: Optional[Decimal] = None
    previous_value: Optional[Decimal] = None
    threshold: Optional[Decimal] = None
    condition_met: bool
    raw_data: Optional[Dict[str, Any]] = None
    source: Optional[str] = None
    last_updated: datetime

    model_config = {"from_attributes": True}
