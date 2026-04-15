from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class PredictionCreate(BaseModel):
    company_id: UUID
    claim_text: str
    observable_outcome: str
    resolution_date: date
    confidence_pct: float
    belief_stack_id: Optional[UUID] = None


class PredictionResolve(BaseModel):
    actual_outcome: str
    outcome_direction: str  # CONFIRMED, DENIED, AMBIGUOUS
    notes: str = ""


class PredictionOut(BaseModel):
    id: UUID
    company_id: UUID
    belief_stack_id: Optional[UUID] = None
    claim_text: str
    observable_outcome: str
    resolution_date: date
    confidence_pct: Decimal
    actual_outcome: Optional[str] = None
    outcome_direction: Optional[str] = None
    signal_accuracy_notes: Optional[str] = None
    created_at: datetime
    resolved_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
