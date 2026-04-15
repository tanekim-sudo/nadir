from datetime import datetime, timezone
from decimal import Decimal
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.company import Company
from app.models.enums import PositionStatus
from app.models.position import Position
from app.schemas.position import ManualExitRequest, PositionOut
from app.services.trade_executor import TradeExecutor

router = APIRouter(prefix="/api/positions", tags=["positions"])


@router.get("", response_model=List[PositionOut])
def list_positions(status: str = None, db: Session = Depends(get_db)):
    q = db.query(Position)
    if status:
        q = q.filter(Position.status == status)
    else:
        q = q.filter(Position.status == PositionStatus.OPEN.value)
    return q.order_by(Position.entry_date.desc()).all()


@router.get("/history", response_model=List[PositionOut])
def position_history(db: Session = Depends(get_db)):
    return (
        db.query(Position)
        .filter(Position.status != PositionStatus.OPEN.value)
        .order_by(Position.exit_date.desc())
        .all()
    )


@router.get("/{ticker}", response_model=PositionOut)
def get_position(ticker: str, db: Session = Depends(get_db)):
    position = (
        db.query(Position)
        .filter(Position.ticker == ticker.upper())
        .filter(Position.status == PositionStatus.OPEN.value)
        .first()
    )
    if not position:
        raise HTTPException(status_code=404, detail="No open position for this ticker")
    return position


@router.post("/{ticker}/approve", response_model=PositionOut)
def approve_trade(ticker: str, db: Session = Depends(get_db)):
    position = (
        db.query(Position)
        .filter(Position.ticker == ticker.upper())
        .filter(Position.pending_approval == True)
        .first()
    )
    if not position:
        raise HTTPException(status_code=404, detail="No pending position for this ticker")

    executor = TradeExecutor()
    order, err = executor.execute_entry(position.ticker, float(position.dollar_amount))
    if err:
        raise HTTPException(status_code=500, detail=f"Execution failed: {err}")

    position.pending_approval = False
    if order:
        position.alpaca_order_id = getattr(order, "id", None)

    db.commit()
    db.refresh(position)
    return position


@router.post("/{ticker}/exit", response_model=PositionOut)
def manual_exit(ticker: str, body: ManualExitRequest, db: Session = Depends(get_db)):
    position = (
        db.query(Position)
        .filter(Position.ticker == ticker.upper())
        .filter(Position.status == PositionStatus.OPEN.value)
        .first()
    )
    if not position:
        raise HTTPException(status_code=404, detail="No open position for this ticker")

    executor = TradeExecutor()
    current_price = executor.get_current_price(position.ticker)
    order, err = executor.execute_exit(position.ticker, position.shares, body.reason)

    entry_price = float(position.entry_price)
    exit_price = current_price or entry_price
    return_pct = (exit_price - entry_price) / entry_price if entry_price else 0

    position.status = (
        PositionStatus.CLOSED_PROFIT.value if return_pct > 0
        else PositionStatus.CLOSED_LOSS.value
    )
    position.exit_date = datetime.now(timezone.utc)
    position.exit_price = Decimal(str(exit_price))
    position.return_pct = Decimal(str(return_pct))
    position.exit_reason = body.reason
    if order:
        position.alpaca_order_id = getattr(order, "id", None)

    db.commit()
    db.refresh(position)
    return position
