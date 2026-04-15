from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.services.analytics import (
    get_kelly_calibration,
    get_performance_dashboard,
    get_signal_accuracy_breakdown,
)

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("/performance")
def performance(db: Session = Depends(get_db)):
    return get_performance_dashboard(db)


@router.get("/signals")
def signal_accuracy(db: Session = Depends(get_db)):
    return get_signal_accuracy_breakdown(db)


@router.get("/kelly")
def kelly_calibration(db: Session = Depends(get_db)):
    return get_kelly_calibration(db)
