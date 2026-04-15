from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.prediction import Prediction
from app.schemas.prediction import PredictionCreate, PredictionOut, PredictionResolve
from app.services.prediction_registry import (
    create_prediction,
    get_accuracy_stats,
    get_active_predictions,
    resolve_prediction,
)

router = APIRouter(prefix="/api/predictions", tags=["predictions"])


@router.get("", response_model=List[PredictionOut])
def list_predictions(active_only: bool = False, db: Session = Depends(get_db)):
    if active_only:
        return get_active_predictions(db)
    return db.query(Prediction).order_by(Prediction.resolution_date.asc()).all()


@router.post("", response_model=PredictionOut)
def create(body: PredictionCreate, db: Session = Depends(get_db)):
    return create_prediction(
        db,
        company_id=body.company_id,
        claim_text=body.claim_text,
        observable_outcome=body.observable_outcome,
        resolution_date=body.resolution_date,
        confidence_pct=body.confidence_pct,
        belief_stack_id=body.belief_stack_id,
    )


@router.put("/{prediction_id}/resolve", response_model=PredictionOut)
def resolve(prediction_id: str, body: PredictionResolve, db: Session = Depends(get_db)):
    try:
        return resolve_prediction(
            db,
            prediction_id=prediction_id,
            actual_outcome=body.actual_outcome,
            outcome_direction=body.outcome_direction,
            notes=body.notes,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/accuracy")
def accuracy_stats(db: Session = Depends(get_db)):
    return get_accuracy_stats(db)
