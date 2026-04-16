from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class CompanyBase(BaseModel):
    ticker: str
    name: str = ""
    sector: str = "Technology"


class CompanyCreate(CompanyBase):
    pass


class CompanyOut(CompanyBase):
    id: UUID
    market_cap: Optional[int] = None
    current_price: Optional[Decimal] = None
    current_ev: Optional[int] = None
    market_implied_nrr: Optional[Decimal] = None
    market_implied_growth: Optional[Decimal] = None
    system_state: str
    conditions_met: int
    last_scanned: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CompanyDetail(CompanyOut):
    signals: list = []
    belief_nodes: list = []
    positions: list = []
    alerts: list = []
