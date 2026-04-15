"""
Performance Analytics — calculates portfolio metrics, signal accuracy, and Kelly calibration.
"""
import logging
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List

from sqlalchemy.orm import Session

from app.models.enums import PositionStatus, SignalType
from app.models.position import Position
from app.models.signal_accuracy import SignalAccuracy

logger = logging.getLogger(__name__)


def get_performance_dashboard(db: Session) -> Dict[str, Any]:
    """Full performance dashboard data."""
    all_positions = db.query(Position).all()
    open_pos = [p for p in all_positions if p.status == PositionStatus.OPEN.value]
    closed_pos = [p for p in all_positions if p.status != PositionStatus.OPEN.value]

    wins = [p for p in closed_pos if p.return_pct and float(p.return_pct) > 0]
    losses = [p for p in closed_pos if p.return_pct and float(p.return_pct) <= 0]

    total_return = sum(float(p.return_pct) for p in closed_pos if p.return_pct) if closed_pos else 0
    avg_return = total_return / len(closed_pos) if closed_pos else 0

    avg_win = (sum(float(p.return_pct) for p in wins) / len(wins)) if wins else 0
    avg_loss = (sum(float(p.return_pct) for p in losses) / len(losses)) if losses else 0

    holding_days = []
    for p in closed_pos:
        if p.entry_date and p.exit_date:
            holding_days.append((p.exit_date - p.entry_date).days)

    # P&L attribution by exit reason
    exit_reasons: Dict[str, Dict] = defaultdict(lambda: {"count": 0, "total_return": 0})
    for p in closed_pos:
        reason = p.exit_reason or "UNKNOWN"
        exit_reasons[reason]["count"] += 1
        exit_reasons[reason]["total_return"] += float(p.return_pct) if p.return_pct else 0

    # Equity curve data points
    equity_curve = []
    cumulative = 0
    for p in sorted(closed_pos, key=lambda x: x.exit_date or datetime.min.replace(tzinfo=timezone.utc)):
        if p.return_pct and p.exit_date:
            cumulative += float(p.return_pct) * float(p.position_pct)
            equity_curve.append({
                "date": p.exit_date.isoformat(),
                "cumulative_return": round(cumulative, 4),
                "ticker": p.ticker,
            })

    false_positive_rate = (
        sum(1 for p in closed_pos if p.exit_reason == "STOP_LOSS") / len(closed_pos)
        if closed_pos else 0
    )

    return {
        "total_positions": len(all_positions),
        "open_positions": len(open_pos),
        "closed_positions": len(closed_pos),
        "win_rate": round(len(wins) / len(closed_pos) * 100, 1) if closed_pos else 0,
        "avg_return_pct": round(avg_return * 100, 2),
        "avg_win_pct": round(avg_win * 100, 2),
        "avg_loss_pct": round(avg_loss * 100, 2),
        "avg_holding_days": round(sum(holding_days) / len(holding_days), 0) if holding_days else 0,
        "false_positive_rate": round(false_positive_rate * 100, 1),
        "equity_curve": equity_curve,
        "exit_reasons": dict(exit_reasons),
        "return_distribution": [
            {"return_pct": round(float(p.return_pct) * 100, 2), "ticker": p.ticker}
            for p in closed_pos if p.return_pct
        ],
        "holding_period_distribution": holding_days,
    }


def get_signal_accuracy_breakdown(db: Session) -> List[Dict[str, Any]]:
    """Signal accuracy for each of the 5 NADIR signals."""
    accuracies = db.query(SignalAccuracy).all()
    return [
        {
            "signal_type": a.signal_type,
            "true_positives": a.true_positives,
            "false_positives": a.false_positives,
            "true_negatives": a.true_negatives,
            "false_negatives": a.false_negatives,
            "precision": float(a.precision) if a.precision else None,
            "recall": float(a.recall) if a.recall else None,
            "f1_score": float(a.f1_score) if a.f1_score else None,
        }
        for a in accuracies
    ]


def get_kelly_calibration(db: Session) -> Dict[str, Any]:
    """Compare predicted win probability vs actual win rate by bucket."""
    closed = (
        db.query(Position)
        .filter(Position.status != PositionStatus.OPEN.value)
        .filter(Position.p_win.isnot(None))
        .all()
    )

    buckets: Dict[str, Dict] = {}
    for start in range(30, 80, 5):
        end = start + 5
        label = f"{start}-{end}%"
        in_bucket = [p for p in closed if start <= float(p.p_win or 0) * 100 < end]
        if in_bucket:
            actual_wins = sum(1 for p in in_bucket if p.return_pct and float(p.return_pct) > 0)
            buckets[label] = {
                "predicted_avg": round(sum(float(p.p_win) for p in in_bucket) / len(in_bucket) * 100, 1),
                "actual_win_rate": round(actual_wins / len(in_bucket) * 100, 1),
                "count": len(in_bucket),
            }

    return {
        "buckets": buckets,
        "total_positions": len(closed),
        "is_well_calibrated": all(
            abs(b["predicted_avg"] - b["actual_win_rate"]) < 10
            for b in buckets.values()
        ) if buckets else False,
    }
