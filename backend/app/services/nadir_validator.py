"""
Nadir Validator — secondary validation when all 5 conditions are met.
Uses Claude Opus to detect false positives before generating a trade signal.
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
All five conditions are currently met:
- Short interest: {short_interest}% of float
- Analyst sell ratings: {sell_pct}%
- Insider buying score: {insider_score}
- GRR: {grr}% (stable: {grr_stable})
- Moral language score: {moral_score}/10

Additional context:
- GRR trend over last 4 quarters: {grr_trend}
- Customer adoption language signal: {adoption_signal}
- Earnings call linguistic trend: {linguistic_trend}
- Engineering job posting velocity: {hiring_signal}
- Days since last insider purchase: {days_since_insider}

A FALSE POSITIVE occurs when:
1. GRR is about to fall (currently stable but trend is deteriorating)
2. Customer language is mimetic not genuine (they adopted because others did)
3. Management language shows rapid specificity decline (hiding problems)
4. Engineering hiring is contracting (product investment declining)
5. The bear thesis is fundamentally correct and GRR is a lagging indicator

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
    grr_sig = signal_map.get("GRR_STABILITY")
    moral = signal_map.get("MORAL_LANGUAGE")

    # GRR trend from historical signals
    grr_history = (
        db.query(NadirSignal)
        .filter(NadirSignal.company_id == company.id)
        .filter(NadirSignal.signal_type == "GRR_STABILITY")
        .order_by(NadirSignal.last_updated.desc())
        .limit(4)
        .all()
    )
    grr_values = [float(h.current_value) for h in grr_history if h.current_value]
    if len(grr_values) >= 2:
        grr_trend = "improving" if grr_values[0] > grr_values[-1] else "declining"
    else:
        grr_trend = "insufficient_data"

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
        short_interest=f"{float(short_interest.current_value) * 100:.1f}" if short_interest and short_interest.current_value else "N/A",
        sell_pct=f"{float(analyst.raw_data.get('sell_pct', 0)) * 100:.1f}" if analyst and analyst.raw_data else "N/A",
        insider_score=f"{float(insider.current_value):.1f}" if insider and insider.current_value else "N/A",
        grr=f"{float(grr_sig.current_value) * 100:.1f}" if grr_sig and grr_sig.current_value else "N/A",
        grr_stable=str(grr_sig.raw_data.get("is_stable", "unknown")) if grr_sig and grr_sig.raw_data else "unknown",
        moral_score=f"{float(moral.current_value):.1f}" if moral and moral.current_value else "N/A",
        grr_trend=grr_trend,
        adoption_signal="uncertain",
        linguistic_trend="not_analyzed",
        hiring_signal="not_analyzed",
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
            company.ticker,
            parsed.get("validation_status"),
            parsed.get("confidence"),
        )
        return parsed

    except Exception as e:
        logger.error("Validation failed for %s: %s", company.ticker, e)
        return None
