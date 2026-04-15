from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import BaseModel


class PositionOut(BaseModel):
    id: UUID
    company_id: UUID
    ticker: str
    entry_date: datetime
    entry_price: Decimal
    shares: int
    dollar_amount: Decimal
    position_pct: Decimal
    p_win: Optional[Decimal] = None
    kelly_fraction: Optional[Decimal] = None
    thesis: Optional[Dict[str, Any]] = None
    validation_result: Optional[Dict[str, Any]] = None
    falsification_conditions: Optional[Dict[str, Any]] = None
    time_horizon_days: int
    status: str
    exit_date: Optional[datetime] = None
    exit_price: Optional[Decimal] = None
    return_pct: Optional[Decimal] = None
    exit_reason: Optional[str] = None
    alpaca_order_id: Optional[str] = None
    pending_approval: bool = False
    created_at: datetime

    model_config = {"from_attributes": True}


class ManualExitRequest(BaseModel):
    reason: str = "MANUAL"
