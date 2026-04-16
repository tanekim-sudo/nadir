"""
Nadir Validator — secondary validation when all 5 conditions are met.
Updated to use the new 5 signals (no GRR/moral language in detection).
"""
import logging
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.core.claude import call_opus, parse_json_response
from app.models.company import Company
from app.models.nadir_signal import NadirSignal

logger = logging.getLogger(__name__)

VALIDATION_PROMPT = """You are validating whether a Nadir Package setup represents a genuine investment opportunity or a false positive.

The Nadir Package identifies companies where market narrative has maximally condemned a business whose underlying operational reality may be intact.

Company: {ticker}
All five detection conditions are currently met:
- Short interest: {short_interest}% of float (>20%, top quintile borrow rate)
- Analyst sell ratings: {sell_pct}% (>70%)
- Insider buying score: {insider_score} (>8.0)
- Customer job posting velocity: {job_velocity} (>-0.10, customers still hiring)
- Short squeeze probability: {squeeze_score} (>0.65)

Additional context:
- Job posting demand momentum: {demand_momentum}
- Job posting supply momentum: {supply_momentum}
- Squeeze days to cover: {days_to_cover}
- Days since last insider purchase: {days_since_insider}

A FALSE POSITIVE occurs when:
1. Customer hiring is mimetic not genuine (adopted because others did)
2. Short squeeze mechanics are the ONLY driver (no fundamental support)
3. Insider buying is tax-motivated or governance-mandated, not conviction
4. The bear thesis is fundamentally correct and operational metrics will confirm it
5. The company has a structural moat erosion problem that signals can't capture

Return ONLY valid JSON in this exact format:
{{"validation_status": "<VALID|FALSE_POSITIVE|INSUFFICIENT_DATA>", "confidence": "<high|medium|low>", "primary_risk": "<text describing biggest risk to thesis>", "grr_assessment": "<stable_genuine|stable_uncertain|declining_risk>", "adoption_assessment": "<genuine_operational|uncertain|mimetic_dominant>", "rehabilitation_mechanism": "<text describing how narrative corrects>", "rehabilitation_timeline": "<weeks|months|quarters>", "falsification_condition": "<specific observable outcome that proves thesis wrong>", "recommended_position_size": "<full|half|quarter|skip>", "reasoning": "<paragraph explaining full assessment>"}}"""


def validate_nadir(db: Session, company: Company) -> Optional[Dict[str, Any]]:
    """Run full validation on a NADIR_COMPLETE company."""
    signals = (
        db.query(NadirSignal)
        .filter(NadirSignal.company_id == company.id)
        .order_by(NadirSignal.last_updated.desc())
        .all()
    )

    signal_map: Dict[str, NadirSignal] = {}
    for s in signals:
        if s.signal_type not in signal_map:
            signal_map[s.signal_type] = s

    short_interest = signal_map.get("SHORT_INTEREST")
    analyst = signal_map.get("ANALYST_SENTIMENT")
    insider = signal_map.get("INSIDER_BUYING")
    job_vel = signal_map.get("JOB_POSTING_VELOCITY")
    squeeze = signal_map.get("SQUEEZE_PROBABILITY")

    # Days since last insider purchase
    days_since = "unknown"
    if insider and insider.raw_data:
        purchases = insider.raw_data.get("purchases", [])
        if purchases:
            from datetime import datetime, timezone
            try:
                latest_date = max(p.get("date", "") for p in purchases)
                if latest_date:
                    parsed_date = datetime.fromisoformat(latest_date.replace("Z", "+00:00"))
                    days_since = str((datetime.now(timezone.utc) - parsed_date).days)
            except Exception:
                pass

    prompt = VALIDATION_PROMPT.format(
        ticker=company.ticker,
        short_interest=f"{float(short_interest.current_value)*100:.1f}" if short_interest and short_interest.current_value else "N/A",
        sell_pct=f"{float(analyst.raw_data.get('sell_pct', 0))*100:.1f}" if analyst and analyst.raw_data else "N/A",
        insider_score=f"{float(insider.current_value):.1f}" if insider and insider.current_value else "N/A",
        job_velocity=f"{float(job_vel.current_value):.4f}" if job_vel and job_vel.current_value else "N/A",
        squeeze_score=f"{float(squeeze.current_value):.4f}" if squeeze and squeeze.current_value else "N/A",
        demand_momentum=f"{job_vel.raw_data.get('demand_momentum', 0):.4f}" if job_vel and job_vel.raw_data else "N/A",
        supply_momentum=f"{job_vel.raw_data.get('supply_momentum', 0):.4f}" if job_vel and job_vel.raw_data else "N/A",
        days_to_cover=f"{squeeze.raw_data.get('days_to_cover', 0):.1f}" if squeeze and squeeze.raw_data else "N/A",
        days_since_insider=days_since,
    )

    try:
        result = call_opus(prompt)
        parsed = parse_json_response(result)

        if not parsed or "validation_status" not in parsed:
            logger.error("Invalid validation response for %s", company.ticker)
            return None

        logger.info(
            "Validation for %s: %s (confidence: %s)",
            company.ticker, parsed.get("validation_status"), parsed.get("confidence"),
        )
        return parsed

    except Exception as e:
        logger.error("Validation failed for %s: %s", company.ticker, e)
        return None
