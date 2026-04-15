from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.belief_stack import BeliefStack
from app.models.company import Company
from app.schemas.belief import BeliefStackOut
from app.services.belief_stack_builder import build_belief_stack

router = APIRouter(prefix="/api/beliefs", tags=["beliefs"])


@router.get("/{ticker}", response_model=List[BeliefStackOut])
def get_belief_stack(ticker: str, db: Session = Depends(get_db)):
    company = db.query(Company).filter(Company.ticker == ticker.upper()).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    beliefs = (
        db.query(BeliefStack)
        .filter(BeliefStack.company_id == company.id)
        .order_by(BeliefStack.layer)
        .all()
    )
    return beliefs


@router.post("/{ticker}/refresh", response_model=List[BeliefStackOut])
def refresh_belief_stack(ticker: str, db: Session = Depends(get_db)):
    company = db.query(Company).filter(Company.ticker == ticker.upper()).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    result = build_belief_stack(db, company)
    if not result:
        raise HTTPException(status_code=500, detail="Belief stack generation failed")

    beliefs = (
        db.query(BeliefStack)
        .filter(BeliefStack.company_id == company.id)
        .order_by(BeliefStack.layer)
        .all()
    )
    return beliefs
