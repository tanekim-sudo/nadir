"""
Orchestrating Agent — main pipeline coordinator using Celery tasks.
"""
import logging
import time
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.core.celery_app import celery_app
from app.db.session import SessionLocal
from app.models.alert import Alert
from app.models.company import Company
from app.models.enums import AlertPriority, AlertType, PositionStatus, SystemState
from app.models.position import Position
from app.models.scan_history import ScanHistory
from app.services.belief_stack_builder import build_belief_stack
from app.services.exit_monitor import run_exit_monitor
from app.services.nadir_validator import validate_nadir
from app.services.position_sizer import calculate_position_size
from app.services.prediction_registry import get_approaching_predictions
from app.services.signal_collectors import run_all_collectors
from app.services.thesis_generator import generate_thesis
from app.services.trade_executor import TradeExecutor
from app.services.universe_manager import sync_universe

logger = logging.getLogger(__name__)


def _update_company_states(db: Session):
    """Recalculate conditions_met and system_state for all companies."""
    from app.models.nadir_signal import NadirSignal
    from sqlalchemy import func

    companies = db.query(Company).all()
    for company in companies:
        # Get latest signal of each type
        latest_signals = (
            db.query(
                NadirSignal.signal_type,
                func.bool_or(NadirSignal.condition_met).label("met"),
            )
            .filter(NadirSignal.company_id == company.id)
            .group_by(NadirSignal.signal_type)
            .all()
        )

        met_count = sum(1 for _, met in latest_signals if met)
        prev_state = company.system_state

        company.conditions_met = met_count
        if met_count >= 5:
            company.system_state = SystemState.NADIR_COMPLETE.value
        elif met_count >= 3:
            company.system_state = SystemState.WATCH.value
        elif met_count == 0 and prev_state in (SystemState.NADIR_COMPLETE.value, SystemState.WATCH.value):
            company.system_state = SystemState.CONSTRAINT_DISSOLVING.value
        else:
            company.system_state = SystemState.NORMAL.value

        company.last_scanned = datetime.now(timezone.utc)

        # Alert on state transitions
        if prev_state != company.system_state:
            if company.system_state == SystemState.WATCH.value:
                alert = Alert(
                    company_id=company.id,
                    alert_type=AlertType.WATCH_TRIGGERED.value,
                    alert_text=f"{company.ticker} entered WATCH state with {met_count} conditions met.",
                    priority=AlertPriority.MEDIUM.value,
                )
                db.add(alert)
            elif company.system_state == SystemState.NADIR_COMPLETE.value:
                alert = Alert(
                    company_id=company.id,
                    alert_type=AlertType.NADIR_COMPLETE.value,
                    alert_text=f"{company.ticker} hit NADIR_COMPLETE — all 5 conditions met!",
                    priority=AlertPriority.CRITICAL.value,
                )
                db.add(alert)

    db.commit()


def _process_nadir_complete(db: Session, company: Company):
    """Full pipeline for a newly NADIR_COMPLETE company."""
    logger.info("Processing NADIR_COMPLETE for %s", company.ticker)

    # Build belief stack
    build_belief_stack(db, company)

    # Validate
    validation = validate_nadir(db, company)
    if not validation:
        logger.warning("Validation returned None for %s", company.ticker)
        return

    if validation.get("validation_status") == "FALSE_POSITIVE":
        logger.info("%s flagged as FALSE_POSITIVE", company.ticker)
        return

    # Generate thesis
    thesis = generate_thesis(db, company, validation)

    # Size position
    executor = TradeExecutor()
    portfolio_value = executor.get_portfolio_value()
    open_positions_db = (
        db.query(Position)
        .filter(Position.status == PositionStatus.OPEN.value)
        .all()
    )
    open_positions_list = [
        {"position_pct": float(p.position_pct)} for p in open_positions_db
    ]

    sizing = calculate_position_size(validation, portfolio_value, open_positions_list)
    if not sizing or sizing.get("skip"):
        logger.info("Position sizing says skip for %s", company.ticker)
        return

    # Determine whether auto-execute or require approval
    needs_approval = (
        not executor.is_paper
        or sizing["position_pct"] >= 0.15
    )

    current_price = executor.get_current_price(company.ticker) or float(company.current_price or 0)
    shares = int(sizing["dollar_amount"] / current_price) if current_price else 0

    position = Position(
        company_id=company.id,
        ticker=company.ticker,
        entry_date=datetime.now(timezone.utc),
        entry_price=Decimal(str(current_price)),
        shares=shares,
        dollar_amount=Decimal(str(sizing["dollar_amount"])),
        position_pct=Decimal(str(sizing["position_pct"])),
        p_win=Decimal(str(sizing["p_win"])),
        kelly_fraction=Decimal(str(sizing["kelly_fraction"])),
        thesis=thesis,
        validation_result=validation,
        falsification_conditions={
            "grr_floor": 0.85,
            "condition": validation.get("falsification_condition", ""),
        },
        time_horizon_days=180,
        status=PositionStatus.OPEN.value,
        pending_approval=needs_approval,
    )

    if needs_approval:
        position.status = PositionStatus.OPEN.value
        position.pending_approval = True
        alert = Alert(
            company_id=company.id,
            alert_type=AlertType.APPROVAL_REQUIRED.value,
            alert_text=(
                f"Trade approval required for {company.ticker}: "
                f"${sizing['dollar_amount']:,.0f} ({sizing['position_pct']*100:.1f}% of portfolio). "
                f"Kelly: {sizing['kelly_fraction']*100:.1f}%, p(win): {sizing['p_win']*100:.0f}%"
            ),
            priority=AlertPriority.CRITICAL.value,
        )
        db.add(alert)
    else:
        # Auto-execute in paper mode
        order, err = executor.execute_entry(company.ticker, sizing["dollar_amount"])
        if order:
            position.alpaca_order_id = getattr(order, "id", None)
        elif err:
            logger.error("Auto-execution failed for %s: %s", company.ticker, err)

    db.add(position)
    db.commit()
    logger.info(
        "Position created for %s: $%.0f (%.1f%%), approval_needed=%s",
        company.ticker, sizing["dollar_amount"], sizing["position_pct"] * 100, needs_approval,
    )


@celery_app.task(name="app.services.nadir_agent.run_daily_pipeline")
def run_daily_pipeline():
    """Main daily pipeline — 6:30am ET."""
    db = SessionLocal()
    start_time = time.time()
    errors: List[Dict] = []
    new_alerts = 0

    try:
        logger.info("Starting daily NADIR pipeline")
        companies = db.query(Company).all()

        # 1. Run all signal collectors
        try:
            run_all_collectors(db, companies)
        except Exception as e:
            logger.error("Signal collection failed: %s", e)
            errors.append({"stage": "signal_collection", "error": str(e)})

        # 2-3. Update states
        try:
            _update_company_states(db)
        except Exception as e:
            logger.error("State update failed: %s", e)
            errors.append({"stage": "state_update", "error": str(e)})

        # 4. Process new NADIR_COMPLETE companies
        nadir_companies = (
            db.query(Company)
            .filter(Company.system_state == SystemState.NADIR_COMPLETE.value)
            .all()
        )
        existing_positions = {
            p.company_id
            for p in db.query(Position.company_id).filter(
                Position.status == PositionStatus.OPEN.value
            ).all()
        }

        for company in nadir_companies:
            if company.id not in existing_positions:
                try:
                    _process_nadir_complete(db, company)
                except Exception as e:
                    logger.error("NADIR processing failed for %s: %s", company.ticker, e)
                    errors.append({"stage": "nadir_processing", "ticker": company.ticker, "error": str(e)})

        # 5. Exit monitor
        try:
            actions = run_exit_monitor(db)
            new_alerts += len(actions)
        except Exception as e:
            logger.error("Exit monitor failed: %s", e)
            errors.append({"stage": "exit_monitor", "error": str(e)})

        # 6. Flag approaching predictions
        try:
            approaching = get_approaching_predictions(db)
            for pred in approaching:
                alert = Alert(
                    company_id=pred.company_id,
                    alert_type=AlertType.PREDICTION_RESOLVING.value,
                    alert_text=f"Prediction approaching resolution: {pred.claim_text[:100]}",
                    priority=AlertPriority.MEDIUM.value,
                )
                db.add(alert)
                new_alerts += 1
            db.commit()
        except Exception as e:
            logger.error("Prediction check failed: %s", e)

        # 7. Record scan history
        duration = time.time() - start_time
        scan = ScanHistory(
            companies_scanned=len(companies),
            nadir_complete_count=len(nadir_companies),
            watch_count=db.query(Company).filter(Company.system_state == SystemState.WATCH.value).count(),
            new_alerts=new_alerts,
            scan_duration_seconds=Decimal(str(round(duration, 2))),
            errors=errors if errors else None,
        )
        db.add(scan)
        db.commit()

        logger.info(
            "Daily pipeline complete: %d companies, %d NADIR, %d alerts, %.1fs",
            len(companies), len(nadir_companies), new_alerts, duration,
        )

    except Exception as e:
        logger.error("Daily pipeline fatal error: %s", e)
        db.rollback()
    finally:
        db.close()


@celery_app.task(name="app.services.nadir_agent.run_signal_collector")
def run_signal_collector(signal_type: str):
    """Run a single signal collector for full universe."""
    db = SessionLocal()
    try:
        companies = db.query(Company).all()
        run_all_collectors(db, companies, signal_type=signal_type)
        logger.info("Signal collector %s complete for %d companies", signal_type, len(companies))
    except Exception as e:
        logger.error("Signal collector %s failed: %s", signal_type, e)
    finally:
        db.close()


@celery_app.task(name="app.services.nadir_agent.run_exit_monitor")
def run_exit_monitor_task():
    db = SessionLocal()
    try:
        actions = run_exit_monitor(db)
        logger.info("Exit monitor complete: %d actions", len(actions))
    except Exception as e:
        logger.error("Exit monitor task failed: %s", e)
    finally:
        db.close()


@celery_app.task(name="app.services.nadir_agent.refresh_universe")
def refresh_universe():
    db = SessionLocal()
    try:
        new_count = sync_universe(db)
        logger.info("Universe refresh complete: %d new companies", new_count)
    except Exception as e:
        logger.error("Universe refresh failed: %s", e)
    finally:
        db.close()
