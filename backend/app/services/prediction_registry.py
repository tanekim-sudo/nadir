"""
Prediction Registry — tracks predictions, resolves them, and feeds signal accuracy.
"""
import logging
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from app.models.enums import OutcomeDirection
from app.models.prediction import Prediction
from app.models.signal_accuracy import SignalAccuracy

logger = logging.getLogger(__name__)


def create_prediction(
    db: Session,
    company_id: UUID,
    claim_text: str,
    observable_outcome: str,
    resolution_date: date,
    confidence_pct: float,
    belief_stack_id: Optional[UUID] = None,
) -> Prediction:
    prediction = Prediction(
        company_id=company_id,
        belief_stack_id=belief_stack_id,
        claim_text=claim_text,
        observable_outcome=observable_outcome,
        resolution_date=resolution_date,
        confidence_pct=Decimal(str(confidence_pct)),
    )
    db.add(prediction)
    db.commit()
    db.refresh(prediction)
    return prediction


def resolve_prediction(
    db: Session,
    prediction_id: UUID,
    actual_outcome: str,
    outcome_direction: str,
    notes: str = "",
) -> Prediction:
    prediction = db.query(Prediction).filter(Prediction.id == prediction_id).first()
    if not prediction:
        raise ValueError(f"Prediction {prediction_id} not found")

    prediction.actual_outcome = actual_outcome
    prediction.outcome_direction = outcome_direction
    prediction.signal_accuracy_notes = notes
    prediction.resolved_at = datetime.now(timezone.utc)
    db.commit()

    _update_signal_accuracy(db)
    return prediction


def get_active_predictions(db: Session) -> List[Prediction]:
    return (
        db.query(Prediction)
        .filter(Prediction.resolved_at.is_(None))
        .order_by(Prediction.resolution_date.asc())
        .all()
    )


def get_approaching_predictions(db: Session, within_days: int = 7) -> List[Prediction]:
    target_date = date.today()
    from datetime import timedelta
    end_date = target_date + timedelta(days=within_days)
    return (
        db.query(Prediction)
        .filter(
            and_(
                Prediction.resolved_at.is_(None),
                Prediction.resolution_date <= end_date,
                Prediction.resolution_date >= target_date,
            )
        )
        .order_by(Prediction.resolution_date.asc())
        .all()
    )


def get_accuracy_stats(db: Session) -> Dict[str, Any]:
    """Calculate prediction accuracy statistics."""
    resolved = (
        db.query(Prediction)
        .filter(Prediction.resolved_at.isnot(None))
        .all()
    )

    if not resolved:
        return {
            "total_resolved": 0,
            "confirmed": 0,
            "denied": 0,
            "ambiguous": 0,
            "accuracy_pct": 0,
            "by_confidence_bucket": {},
        }

    confirmed = sum(1 for p in resolved if p.outcome_direction == OutcomeDirection.CONFIRMED.value)
    denied = sum(1 for p in resolved if p.outcome_direction == OutcomeDirection.DENIED.value)
    ambiguous = sum(1 for p in resolved if p.outcome_direction == OutcomeDirection.AMBIGUOUS.value)

    # Calibration: predicted confidence vs actual win rate
    buckets: Dict[str, Dict] = {}
    for bucket_start in range(0, 100, 10):
        bucket_end = bucket_start + 10
        label = f"{bucket_start}-{bucket_end}%"
        in_bucket = [p for p in resolved if bucket_start <= float(p.confidence_pct) < bucket_end]
        if in_bucket:
            wins = sum(1 for p in in_bucket if p.outcome_direction == OutcomeDirection.CONFIRMED.value)
            buckets[label] = {
                "count": len(in_bucket),
                "wins": wins,
                "actual_rate": wins / len(in_bucket),
                "predicted_avg": sum(float(p.confidence_pct) for p in in_bucket) / len(in_bucket),
            }

    return {
        "total_resolved": len(resolved),
        "confirmed": confirmed,
        "denied": denied,
        "ambiguous": ambiguous,
        "accuracy_pct": round(confirmed / len(resolved) * 100, 1) if resolved else 0,
        "by_confidence_bucket": buckets,
    }


def _update_signal_accuracy(db: Session):
    """Recalculate signal accuracy table from resolved predictions."""
    from app.models.enums import SignalType

    for signal_type in SignalType:
        accuracy = db.query(SignalAccuracy).filter(
            SignalAccuracy.signal_type == signal_type.value
        ).first()
        if not accuracy:
            accuracy = SignalAccuracy(signal_type=signal_type.value)
            db.add(accuracy)

        tp = accuracy.true_positives or 0
        fp = accuracy.false_positives or 0
        tn = accuracy.true_negatives or 0
        fn = accuracy.false_negatives or 0

        total_pos = tp + fp
        total_actual = tp + fn

        accuracy.precision = Decimal(str(tp / total_pos)) if total_pos > 0 else None
        accuracy.recall = Decimal(str(tp / total_actual)) if total_actual > 0 else None

        if accuracy.precision and accuracy.recall:
            p = float(accuracy.precision)
            r = float(accuracy.recall)
            accuracy.f1_score = Decimal(str(2 * p * r / (p + r))) if (p + r) > 0 else None

        accuracy.last_calculated = datetime.now(timezone.utc)

    db.commit()
