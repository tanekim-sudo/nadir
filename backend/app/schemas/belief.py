from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class BeliefStackOut(BaseModel):
    id: UUID
    company_id: UUID
    layer: str
    assumption_text: str
    market_implied_value: str
    variant_value: str
    confidence_pct: Optional[Decimal] = None
    confirming_signals: int
    contradicting_signals: int
    net_direction: str
    last_updated: datetime

    model_config = {"from_attributes": True}
