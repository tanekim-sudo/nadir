"""
Exit Monitor — runs daily at 9:00am ET.
Checks all open positions against exit conditions.
GRR is the primary post-entry falsification signal.
"""
import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import List

from sqlalchemy.orm import Session

from app.models.alert import Alert
from app.models.company import Company
from app.models.enums import AlertPriority, AlertType, PositionStatus, SignalType
from app.models.nadir_signal import NadirSignal
from app.models.position import Position
from app.services.signal_collectors import collect_grr_for_monitoring
from app.services.trade_executor import TradeExecutor

logger = logging.getLogger(__name__)


def run_exit_monitor(db: Session) -> List[dict]:
    """Check all open positions against exit conditions."""
    executor = TradeExecutor()
    open_positions = (
        db.query(Position)
        .filter(Position.status == PositionStatus.OPEN.value)
        .all()
    )

    actions = []
    for pos in open_positions:
        company = db.query(Company).filter(Company.id == pos.company_id).first()
        if not company:
            continue

        current_price = executor.get_current_price(pos.ticker)
        if current_price is None and pos.entry_price:
            current_price = float(pos.entry_price)

        entry_price = float(pos.entry_price)
        current_return = (current_price - entry_price) / entry_price if entry_price else 0

        days_held = (datetime.now(timezone.utc) - pos.entry_date).days if pos.entry_date else 0

        # CHECK 1 — GRR Falsification (auto-exit)
        # GRR is the most important ongoing monitoring signal after entry
        if pos.falsification_conditions:
            grr_floor = pos.falsification_conditions.get("grr_floor", 0.85)
            latest_grr = (
                db.query(NadirSignal)
                .filter(NadirSignal.company_id == pos.company_id)
                .filter(NadirSignal.signal_type == SignalType.GRR_MONITORING.value)
                .order_by(NadirSignal.last_updated.desc())
                .first()
            )

            # If no GRR data yet, try to collect it
            if not latest_grr:
                latest_grr = collect_grr_for_monitoring(db, company)

            if latest_grr and latest_grr.current_value and float(latest_grr.current_value) < grr_floor:
                order, err = executor.execute_exit(pos.ticker, pos.shares, "GRR_FALSIFICATION")
                pos.status = PositionStatus.CLOSED_FALSIFIED.value
                pos.exit_date = datetime.now(timezone.utc)
                pos.exit_price = Decimal(str(current_price))
                pos.return_pct = Decimal(str(current_return))
                pos.exit_reason = "GRR_FALSIFICATION"
                if order:
                    pos.alpaca_order_id = getattr(order, "id", None)

                alert = Alert(
                    company_id=pos.company_id,
                    alert_type=AlertType.FALSIFICATION_DETECTED.value,
                    alert_text=(
                        f"GRR fell to {float(latest_grr.current_value)*100:.1f}% "
                        f"below floor of {grr_floor*100:.0f}%. Position auto-closed."
                    ),
                    priority=AlertPriority.CRITICAL.value,
                )
                db.add(alert)
                actions.append({"ticker": pos.ticker, "action": "FALSIFICATION_EXIT", "return": current_return})
                continue

        # CHECK 2 — Time limit (flag for review)
        if days_held > pos.time_horizon_days:
            alert = Alert(
                company_id=pos.company_id,
                alert_type=AlertType.TIME_LIMIT_REACHED.value,
                alert_text=f"{pos.ticker} held for {days_held} days (horizon: {pos.time_horizon_days}). Review required.",
                priority=AlertPriority.HIGH.value,
            )
            db.add(alert)
            actions.append({"ticker": pos.ticker, "action": "TIME_LIMIT_FLAG"})

        # CHECK 3 — Rehabilitation signal (flag for review)
        latest_short = (
            db.query(NadirSignal)
            .filter(NadirSignal.company_id == pos.company_id)
            .filter(NadirSignal.signal_type == SignalType.SHORT_INTEREST.value)
            .order_by(NadirSignal.last_updated.desc())
            .first()
        )
        if latest_short and latest_short.current_value and float(latest_short.current_value) < 0.10:
            alert = Alert(
                company_id=pos.company_id,
                alert_type=AlertType.REHABILITATION_SIGNAL.value,
                alert_text=(
                    f"{pos.ticker} short interest dropped to "
                    f"{float(latest_short.current_value)*100:.1f}%. Consider trimming 30-50%."
                ),
                priority=AlertPriority.MEDIUM.value,
            )
            db.add(alert)
            actions.append({"ticker": pos.ticker, "action": "REHABILITATION_FLAG"})

        # CHECK 4 — Stop loss (auto-exit)
        if current_return < -0.35:
            order, err = executor.execute_exit(pos.ticker, pos.shares, "STOP_LOSS")
            pos.status = PositionStatus.CLOSED_LOSS.value
            pos.exit_date = datetime.now(timezone.utc)
            pos.exit_price = Decimal(str(current_price))
            pos.return_pct = Decimal(str(current_return))
            pos.exit_reason = "STOP_LOSS"
            if order:
                pos.alpaca_order_id = getattr(order, "id", None)

            alert = Alert(
                company_id=pos.company_id,
                alert_type=AlertType.STOP_LOSS_TRIGGERED.value,
                alert_text=f"{pos.ticker} down {current_return*100:.1f}% — stop loss triggered.",
                priority=AlertPriority.CRITICAL.value,
            )
            db.add(alert)
            actions.append({"ticker": pos.ticker, "action": "STOP_LOSS_EXIT", "return": current_return})
            continue

        # CHECK 5 — Insider buying stopped (flag for review)
        latest_insider = (
            db.query(NadirSignal)
            .filter(NadirSignal.company_id == pos.company_id)
            .filter(NadirSignal.signal_type == SignalType.INSIDER_BUYING.value)
            .order_by(NadirSignal.last_updated.desc())
            .first()
        )
        if latest_insider and latest_insider.raw_data:
            purchases = latest_insider.raw_data.get("purchases", [])
            if purchases:
                from dateutil.parser import parse as dateparse
                try:
                    latest_purchase_date = max(dateparse(p["date"]) for p in purchases if p.get("date"))
                    days_since = (datetime.now(timezone.utc) - latest_purchase_date.replace(tzinfo=timezone.utc)).days
                    if days_since > 60:
                        alert = Alert(
                            company_id=pos.company_id,
                            alert_type=AlertType.INSIDER_BUYING_STOPPED.value,
                            alert_text=f"{pos.ticker}: no insider purchases in {days_since} days.",
                            priority=AlertPriority.MEDIUM.value,
                        )
                        db.add(alert)
                        actions.append({"ticker": pos.ticker, "action": "INSIDER_STOPPED_FLAG"})
                except Exception:
                    pass

    db.commit()
    return actions
