from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.company import Company
from app.models.nadir_signal import NadirSignal
from app.schemas.signal import SignalOut
from app.services.signal_collectors import run_daily_collectors

router = APIRouter(prefix="/api/signals", tags=["signals"])


@router.get("/{ticker}", response_model=List[SignalOut])
def get_signals(ticker: str, db: Session = Depends(get_db)):
    company = db.query(Company).filter(Company.ticker == ticker.upper()).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    from sqlalchemy import func
    subq = (
        db.query(
            NadirSignal.signal_type,
            func.max(NadirSignal.last_updated).label("max_updated"),
        )
        .filter(NadirSignal.company_id == company.id)
        .group_by(NadirSignal.signal_type)
        .subquery()
    )

    signals = (
        db.query(NadirSignal)
        .join(subq, (NadirSignal.signal_type == subq.c.signal_type) & (NadirSignal.last_updated == subq.c.max_updated))
        .filter(NadirSignal.company_id == company.id)
        .all()
    )
    return signals


@router.get("/{ticker}/history", response_model=List[SignalOut])
def get_signal_history(
    ticker: str,
    signal_type: str = None,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    company = db.query(Company).filter(Company.ticker == ticker.upper()).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    q = db.query(NadirSignal).filter(NadirSignal.company_id == company.id)
    if signal_type:
        q = q.filter(NadirSignal.signal_type == signal_type)
    return q.order_by(NadirSignal.last_updated.desc()).limit(limit).all()


@router.post("/refresh/{ticker}")
def refresh_signals(ticker: str, db: Session = Depends(get_db)):
    company = db.query(Company).filter(Company.ticker == ticker.upper()).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    run_daily_collectors(db, [company])
    return {"status": "refreshed", "ticker": ticker.upper()}
