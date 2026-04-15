from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.company import Company
from app.models.nadir_signal import NadirSignal
from app.schemas.company import CompanyCreate, CompanyDetail, CompanyOut
from app.schemas.signal import SignalOut
from app.services.universe_manager import add_ticker, remove_ticker

router = APIRouter(prefix="/api/universe", tags=["universe"])


@router.get("", response_model=List[CompanyOut])
def list_companies(
    state: Optional[str] = None,
    sector: Optional[str] = None,
    min_conditions: int = Query(0, ge=0, le=5),
    db: Session = Depends(get_db),
):
    q = db.query(Company)
    if state:
        q = q.filter(Company.system_state == state)
    if sector:
        q = q.filter(Company.sector == sector)
    if min_conditions > 0:
        q = q.filter(Company.conditions_met >= min_conditions)
    return q.order_by(Company.conditions_met.desc(), Company.ticker).all()


@router.get("/{ticker}", response_model=CompanyDetail)
def get_company(ticker: str, db: Session = Depends(get_db)):
    company = db.query(Company).filter(Company.ticker == ticker.upper()).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    signals = (
        db.query(NadirSignal)
        .filter(NadirSignal.company_id == company.id)
        .order_by(NadirSignal.last_updated.desc())
        .all()
    )

    result = CompanyDetail.model_validate(company)
    result.signals = [SignalOut.model_validate(s) for s in signals]
    return result


@router.post("/add", response_model=CompanyOut)
def add_company(body: CompanyCreate, db: Session = Depends(get_db)):
    company = add_ticker(db, body.ticker, body.name, body.sector)
    return company


@router.delete("/{ticker}")
def delete_company(ticker: str, db: Session = Depends(get_db)):
    success = remove_ticker(db, ticker)
    if not success:
        raise HTTPException(status_code=404, detail="Company not found")
    return {"status": "removed", "ticker": ticker.upper()}
