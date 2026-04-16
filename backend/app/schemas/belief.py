from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel


class BeliefNodeOut(BaseModel):
    id: UUID
    company_id: UUID
    node_id: str
    node_name: str
    parent_node: Optional[str] = None
    market_implied_value: str
    market_implied_label: str
    evidence_value: str
    evidence_label: str
    evidence_direction: str
    evidence_confidence: str
    gap_magnitude: Optional[Decimal] = None
    conviction_score: Optional[Decimal] = None
    evidence_sources: Optional[Dict[str, Any]] = None
    last_updated: datetime

    model_config = {"from_attributes": True}


class DCFOut(BaseModel):
    id: UUID
    company_id: UUID
    scan_date: datetime
    current_ev: Optional[int] = None
    current_price: Optional[Decimal] = None
    shares: Optional[int] = None
    debt: Optional[int] = None
    cash: Optional[int] = None
    ttm_revenue: Optional[int] = None
    ttm_gross_profit: Optional[int] = None
    ttm_ebit: Optional[int] = None
    implied_year1_growth: Optional[Decimal] = None
    implied_terminal_margin: Optional[Decimal] = None
    implied_wacc: Optional[Decimal] = None
    ev_revenue_multiple: Optional[Decimal] = None
    solver_converged: bool
    solver_error: Optional[Decimal] = None

    model_config = {"from_attributes": True}


class BeliefStackSummary(BaseModel):
    nodes: List[BeliefNodeOut]
    dcf: Optional[DCFOut] = None
    primary_mispricing_node: Optional[str] = None
    primary_conviction: Optional[float] = None
