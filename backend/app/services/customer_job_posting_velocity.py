"""
Customer Job Posting Velocity — measures weekly hiring velocity at a company's
customers for roles naming the company's product as a required skill.

Detection condition: velocity_score > -0.10
(Customers STILL hiring for this product despite negative narrative.)
"""
import logging
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

import httpx
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.belief_stack import JobPostingSignal
from app.models.company import Company
from app.models.enums import SignalType
from app.models.nadir_signal import NadirSignal

logger = logging.getLogger(__name__)

HEADERS = {"User-Agent": "NADIR-Research-Bot/1.0"}

# Map tickers to product search terms; auto-derived from company name for most
PRODUCT_OVERRIDES = {
    "CRM": "Salesforce",
    "SNOW": "Snowflake",
    "DDOG": "Datadog",
    "CRWD": "CrowdStrike",
    "ZS": "Zscaler",
    "NET": "Cloudflare",
    "PANW": "Palo Alto Networks",
    "NOW": "ServiceNow",
    "WDAY": "Workday",
    "HUBS": "HubSpot",
    "MDB": "MongoDB",
    "ESTC": "Elastic",
    "CFLT": "Confluent",
    "PATH": "UiPath",
    "S": "SentinelOne",
    "OKTA": "Okta",
    "TWLO": "Twilio",
    "VEEV": "Veeva",
    "TEAM": "Atlassian OR Jira OR Confluence",
    "ADBE": "Adobe",
    "MSFT": "Azure OR Microsoft 365",
    "SHOP": "Shopify",
    "PLTR": "Palantir",
    "GTLB": "GitLab",
    "MNDY": "monday.com",
    "DOCN": "DigitalOcean",
    "DT": "Dynatrace",
    "FRSH": "Freshworks",
    "ZI": "ZoomInfo",
    "CYBR": "CyberArk",
    "QLYS": "Qualys",
    "TENB": "Tenable",
}


def _get_product_name(company: Company) -> str:
    return PRODUCT_OVERRIDES.get(company.ticker, company.name)


def _search_jobs_serpapi(query: str, settings: Any) -> int:
    """Use SerpAPI Google Jobs as fallback source."""
    try:
        with httpx.Client() as client:
            resp = client.get("https://serpapi.com/search", params={
                "engine": "google_jobs",
                "q": query,
                "chips": "date_posted:week",
                "api_key": settings.polygon_api_key,  # reuse key slot or add SERPAPI_KEY
            }, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                return len(data.get("jobs_results", []))
    except Exception as e:
        logger.debug("SerpAPI jobs search failed: %s", e)
    return 0


def _search_jobs_theirstack(query: str, posted_days: int = 7) -> int:
    """Query Theirstack API for job postings."""
    try:
        with httpx.Client() as client:
            resp = client.post(
                "https://api.theirstack.com/v1/jobs/search",
                json={
                    "query": query,
                    "posted_at_max_age_days": posted_days,
                    "limit": 0,
                },
                headers=HEADERS,
                timeout=15,
            )
            if resp.status_code == 200:
                data = resp.json()
                return data.get("total", 0)
    except Exception as e:
        logger.debug("Theirstack search failed: %s", e)
    return 0


def _count_job_postings(query: str) -> int:
    """Try Theirstack first, fall back to SerpAPI, fall back to zero."""
    count = _search_jobs_theirstack(query)
    if count > 0:
        return count
    settings = get_settings()
    return _search_jobs_serpapi(query, settings)


def collect_job_posting_velocity(db: Session, company: Company) -> Optional[NadirSignal]:
    """Collect weekly job posting velocity for a company."""
    product = _get_product_name(company)
    today = date.today()
    week_start = today - timedelta(days=today.weekday())  # Monday

    # Demand signal: jobs anywhere mentioning this product
    demand_query = f'"{product}" skills requirements'
    demand_count = _count_job_postings(demand_query)

    # Supply signal: engineering/product jobs at the company itself
    supply_query = f'"{company.name}" engineer OR developer OR product'
    supply_count = _count_job_postings(supply_query)

    # Store both raw signals
    for subtype, count in [("DEMAND", demand_count), ("SUPPLY", supply_count)]:
        jp = JobPostingSignal(
            company_id=company.id,
            signal_subtype=subtype,
            week_start_date=week_start,
            weekly_count=count,
        )

        # Calculate moving averages from history
        history = (
            db.query(JobPostingSignal)
            .filter(JobPostingSignal.company_id == company.id)
            .filter(JobPostingSignal.signal_subtype == subtype)
            .order_by(JobPostingSignal.week_start_date.desc())
            .limit(52)
            .all()
        )

        counts = [h.weekly_count for h in history]
        recent_4 = counts[:4] if len(counts) >= 4 else counts
        recent_13 = counts[:13] if len(counts) >= 13 else counts

        jp.four_week_avg = Decimal(str(sum(recent_4) / len(recent_4))) if recent_4 else Decimal(str(count))
        jp.thirteen_week_avg = Decimal(str(sum(recent_13) / len(recent_13))) if recent_13 else Decimal(str(count))

        # YoY comparison (52 weeks back)
        yoy_candidates = [h for h in history if abs((h.week_start_date - week_start).days - 364) < 10]
        if yoy_candidates:
            yoy_count = yoy_candidates[0].weekly_count
            jp.yoy_change = Decimal(str((count - yoy_count) / max(yoy_count, 1)))

        # WoW comparison
        if len(history) >= 1:
            prev_count = history[0].weekly_count
            jp.wow_change = Decimal(str((count - prev_count) / max(prev_count, 1)))

        db.add(jp)

    db.flush()

    # Calculate composite velocity score
    demand_history = (
        db.query(JobPostingSignal)
        .filter(JobPostingSignal.company_id == company.id)
        .filter(JobPostingSignal.signal_subtype == "DEMAND")
        .order_by(JobPostingSignal.week_start_date.desc())
        .limit(13)
        .all()
    )
    supply_history = (
        db.query(JobPostingSignal)
        .filter(JobPostingSignal.company_id == company.id)
        .filter(JobPostingSignal.signal_subtype == "SUPPLY")
        .order_by(JobPostingSignal.week_start_date.desc())
        .limit(13)
        .all()
    )

    def _momentum(signals: List[JobPostingSignal]) -> float:
        if len(signals) < 4:
            return 0.0
        counts = [s.weekly_count for s in signals]
        avg_4 = sum(counts[:4]) / 4
        avg_13 = sum(counts[:min(13, len(counts))]) / min(13, len(counts))
        if avg_13 == 0:
            return 0.0
        return (avg_4 - avg_13) / avg_13

    demand_momentum = _momentum(demand_history)
    supply_momentum = _momentum(supply_history)
    velocity_score = (demand_momentum * 0.7) + (supply_momentum * 0.3)

    # Store composite velocity score in job posting table
    for jp_sig in db.query(JobPostingSignal).filter(
        JobPostingSignal.company_id == company.id,
        JobPostingSignal.week_start_date == week_start,
    ).all():
        jp_sig.velocity_score = Decimal(str(round(velocity_score, 8)))

    # Write to nadir_signals for condition evaluation
    prev = (
        db.query(NadirSignal.current_value)
        .filter(NadirSignal.company_id == company.id)
        .filter(NadirSignal.signal_type == SignalType.JOB_POSTING_VELOCITY.value)
        .order_by(NadirSignal.last_updated.desc())
        .first()
    )

    # Condition: velocity > -0.10 means customers still hiring despite narrative
    condition_met = velocity_score > -0.10

    signal = NadirSignal(
        company_id=company.id,
        signal_type=SignalType.JOB_POSTING_VELOCITY.value,
        current_value=Decimal(str(round(velocity_score, 8))),
        previous_value=prev[0] if prev else None,
        threshold=Decimal("-0.10"),
        condition_met=condition_met,
        raw_data={
            "demand_count": demand_count,
            "supply_count": supply_count,
            "demand_momentum": round(demand_momentum, 4),
            "supply_momentum": round(supply_momentum, 4),
            "velocity_score": round(velocity_score, 4),
            "product_name": product,
            "week_start": str(week_start),
        },
        source="theirstack,serpapi",
    )
    db.add(signal)
    return signal


def run_job_posting_collector(db: Session, companies: List[Company]):
    """Run job posting velocity collection for all companies."""
    for company in companies:
        try:
            collect_job_posting_velocity(db, company)
            db.flush()
        except Exception as e:
            logger.error("Job posting collection failed for %s: %s", company.ticker, e)
            continue
    db.commit()
