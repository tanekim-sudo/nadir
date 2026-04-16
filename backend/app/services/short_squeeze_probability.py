"""
Short Squeeze Probability — measures mechanical conditions for a violent
upward price move driven by short covering.

Detection condition: squeeze_score > 0.65
"""
import logging
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

import httpx
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.belief_stack import SqueezeProbabilitySignal
from app.models.company import Company
from app.models.enums import SignalType
from app.models.nadir_signal import NadirSignal

logger = logging.getLogger(__name__)


def _get_market_data(ticker: str) -> Dict[str, Any]:
    """Pull required market data from Polygon/yfinance."""
    settings = get_settings()
    data: Dict[str, Any] = {
        "avg_volume_30d": 0,
        "outstanding_shares": 0,
        "put_call_ratio": 1.0,
        "current_price": 0.0,
        "week52_low": 0.0,
    }

    try:
        with httpx.Client() as client:
            # Ticker details for shares outstanding
            resp = client.get(
                f"https://api.polygon.io/v3/reference/tickers/{ticker}",
                params={"apiKey": settings.polygon_api_key},
                timeout=15,
            )
            if resp.status_code == 200:
                results = resp.json().get("results", {})
                data["outstanding_shares"] = results.get("share_class_shares_outstanding", 0) or 0
                data["current_price"] = results.get("market_cap", 0) / max(data["outstanding_shares"], 1)

            # Previous close + aggregates for volume and 52-week low
            agg_resp = client.get(
                f"https://api.polygon.io/v2/aggs/ticker/{ticker}/prev",
                params={"apiKey": settings.polygon_api_key},
                timeout=15,
            )
            if agg_resp.status_code == 200:
                results = agg_resp.json().get("results", [])
                if results:
                    data["current_price"] = results[0].get("c", data["current_price"])
                    data["avg_volume_30d"] = results[0].get("v", 0)

            # 52-week range from snapshot
            snap_resp = client.get(
                f"https://api.polygon.io/v2/snapshot/locale/us/markets/stocks/tickers/{ticker}",
                params={"apiKey": settings.polygon_api_key},
                timeout=15,
            )
            if snap_resp.status_code == 200:
                ticker_data = snap_resp.json().get("ticker", {})
                day = ticker_data.get("day", {})
                data["avg_volume_30d"] = day.get("v", data["avg_volume_30d"]) or data["avg_volume_30d"]
                min_data = ticker_data.get("min", {})
                prev_day = ticker_data.get("prevDay", {})
                # Approximate 52w low from available data
                data["week52_low"] = min(
                    data["current_price"] * 0.5,  # fallback heuristic
                    prev_day.get("l", data["current_price"]),
                )

            # Options data for put/call ratio
            opts_resp = client.get(
                f"https://api.polygon.io/v3/snapshot/options/{ticker}",
                params={"apiKey": settings.polygon_api_key},
                timeout=15,
            )
            if opts_resp.status_code == 200:
                opts_results = opts_resp.json().get("results", [])
                puts = sum(1 for o in opts_results if o.get("details", {}).get("contract_type") == "put")
                calls = sum(1 for o in opts_results if o.get("details", {}).get("contract_type") == "call")
                data["put_call_ratio"] = puts / max(calls, 1)

    except Exception as e:
        logger.warning("Market data fetch failed for %s: %s", ticker, e)

    return data


def collect_squeeze_probability(db: Session, company: Company) -> Optional[NadirSignal]:
    """Calculate short squeeze probability score."""
    # Get short interest data from latest nadir signal
    latest_short = (
        db.query(NadirSignal)
        .filter(NadirSignal.company_id == company.id)
        .filter(NadirSignal.signal_type == SignalType.SHORT_INTEREST.value)
        .order_by(NadirSignal.last_updated.desc())
        .first()
    )

    short_float = float(latest_short.current_value) if latest_short and latest_short.current_value else 0.0
    borrow_rate = 0.0
    if latest_short and latest_short.raw_data:
        borrow_rate = latest_short.raw_data.get("borrow_rate", 0.0) or 0.0

    market_data = _get_market_data(company.ticker)

    outstanding = market_data["outstanding_shares"]
    avg_volume = market_data["avg_volume_30d"] or 1
    current_price = market_data["current_price"]
    week52_low = market_data["week52_low"] or current_price * 0.5
    put_call_ratio = market_data["put_call_ratio"]

    # Core calculations
    short_shares = short_float * outstanding if outstanding else 0
    days_to_cover = short_shares / max(avg_volume, 1) if avg_volume else 0
    cost_of_carry = borrow_rate / 365 * days_to_cover
    price_proximity = (current_price - week52_low) / max(week52_low, 0.01) if week52_low else 0

    # Squeeze score (0 to 1)
    squeeze_score = (
        (min(days_to_cover, 20) / 20) * 0.35
        + (min(borrow_rate, 0.50) / 0.50) * 0.25
        + (1 - min(price_proximity, 1.0)) * 0.25
        + (min(put_call_ratio, 3.0) / 3.0) * 0.15
    )

    today = date.today()

    # Store in squeeze-specific table
    squeeze_sig = SqueezeProbabilitySignal(
        company_id=company.id,
        signal_date=today,
        days_to_cover=Decimal(str(round(days_to_cover, 4))),
        borrow_rate=Decimal(str(round(borrow_rate, 8))),
        put_call_ratio=Decimal(str(round(put_call_ratio, 8))),
        price_proximity_52w_low=Decimal(str(round(price_proximity, 8))),
        squeeze_score=Decimal(str(round(squeeze_score, 8))),
        raw_inputs={
            "short_float": short_float,
            "outstanding_shares": outstanding,
            "avg_volume_30d": avg_volume,
            "current_price": current_price,
            "week52_low": week52_low,
            "cost_of_carry": round(cost_of_carry, 6),
        },
    )
    db.add(squeeze_sig)

    # Write to nadir_signals for condition evaluation
    prev = (
        db.query(NadirSignal.current_value)
        .filter(NadirSignal.company_id == company.id)
        .filter(NadirSignal.signal_type == SignalType.SQUEEZE_PROBABILITY.value)
        .order_by(NadirSignal.last_updated.desc())
        .first()
    )

    condition_met = squeeze_score > 0.65

    signal = NadirSignal(
        company_id=company.id,
        signal_type=SignalType.SQUEEZE_PROBABILITY.value,
        current_value=Decimal(str(round(squeeze_score, 8))),
        previous_value=prev[0] if prev else None,
        threshold=Decimal("0.65"),
        condition_met=condition_met,
        raw_data={
            "squeeze_score": round(squeeze_score, 4),
            "days_to_cover": round(days_to_cover, 2),
            "borrow_rate": round(borrow_rate, 4),
            "put_call_ratio": round(put_call_ratio, 4),
            "price_proximity_52w_low": round(price_proximity, 4),
            "cost_of_carry": round(cost_of_carry, 6),
        },
        source="polygon,finviz",
    )
    db.add(signal)
    return signal


def run_squeeze_collector(db: Session, companies: List[Company]):
    """Run squeeze probability collection for all companies."""
    for company in companies:
        try:
            collect_squeeze_probability(db, company)
            db.flush()
        except Exception as e:
            logger.error("Squeeze probability collection failed for %s: %s", company.ticker, e)
            continue
    db.commit()
