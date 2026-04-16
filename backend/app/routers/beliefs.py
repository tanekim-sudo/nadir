from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.belief_stack import BeliefStackNode, DCFDecomposition
from app.models.company import Company
from app.schemas.belief import BeliefNodeOut, BeliefStackSummary, DCFOut
from app.services.belief_stack_engine import run_belief_stack_engine

router = APIRouter(prefix="/api/beliefs", tags=["beliefs"])


@router.get("/{ticker}", response_model=BeliefStackSummary)
def get_belief_stack(ticker: str, db: Session = Depends(get_db)):
    company = db.query(Company).filter(Company.ticker == ticker.upper()).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    nodes = (
        db.query(BeliefStackNode)
        .filter(BeliefStackNode.company_id == company.id)
        .order_by(BeliefStackNode.node_id)
        .all()
    )

    dcf = (
        db.query(DCFDecomposition)
        .filter(DCFDecomposition.company_id == company.id)
        .order_by(DCFDecomposition.scan_date.desc())
        .first()
    )

    primary_node = max(nodes, key=lambda n: float(n.conviction_score or 0), default=None)

    return BeliefStackSummary(
        nodes=[BeliefNodeOut.model_validate(n) for n in nodes],
        dcf=DCFOut.model_validate(dcf) if dcf else None,
        primary_mispricing_node=primary_node.node_id if primary_node and primary_node.conviction_score else None,
        primary_conviction=float(primary_node.conviction_score) if primary_node and primary_node.conviction_score else None,
    )


@router.post("/{ticker}/refresh", response_model=BeliefStackSummary)
def refresh_belief_stack(ticker: str, db: Session = Depends(get_db)):
    company = db.query(Company).filter(Company.ticker == ticker.upper()).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    result = run_belief_stack_engine(db, company)
    if not result:
        raise HTTPException(status_code=500, detail="Belief stack engine failed")

    return get_belief_stack(ticker, db)
