"""
Five signal collectors for the NADIR system.
Each writes to the nadir_signals table (append-only for history).
"""
import json
import logging
import math
import time
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

import httpx
from bs4 import BeautifulSoup
from sqlalchemy.orm import Session

from app.core.claude import call_haiku, parse_json_response
from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.company import Company
from app.models.enums import SignalType
from app.models.nadir_signal import NadirSignal

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "NADIR-Research-Bot/1.0 (investment research; nadir@example.com)"
}
SEC_HEADERS = {
    "User-Agent": "NADIR-Research-Bot/1.0 (investment research; nadir@example.com)",
    "Accept": "application/json",
}
EDGAR_DELAY = 0.12  # SEC: 10 req/s max


# ─────────────────────────────────────────────────
# SIGNAL 1: Short Interest
# ─────────────────────────────────────────────────

def collect_short_interest(db: Session, company: Company) -> Optional[NadirSignal]:
    """Scrape short interest from finviz for a single ticker."""
    try:
        with httpx.Client() as client:
            url = f"https://finviz.com/quote.ashx?t={company.ticker}&ty=c&ta=1&p=d"
            resp = client.get(url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }, timeout=15)
            if resp.status_code != 200:
                logger.warning("Finviz returned %d for %s", resp.status_code, company.ticker)
                return None

            soup = BeautifulSoup(resp.text, "lxml")
            short_float = None
            for cell in soup.select("td.snapshot-td2-cp"):
                label_cell = cell.find_previous_sibling("td")
                if label_cell and "Short Float" in label_cell.get_text():
                    val = cell.get_text(strip=True).replace("%", "")
                    try:
                        short_float = Decimal(val) / Decimal(100)
                    except Exception:
                        pass

            borrow_rate = None
            try:
                iborrow_resp = client.get(
                    f"https://iborrowdesk.com/report/{company.ticker}",
                    headers=HEADERS, timeout=10,
                )
                if iborrow_resp.status_code == 200:
                    iborrow_soup = BeautifulSoup(iborrow_resp.text, "lxml")
                    rows = iborrow_soup.select("table tbody tr")
                    if rows:
                        last_row = rows[-1]
                        cells = last_row.select("td")
                        if len(cells) >= 2:
                            rate_text = cells[1].get_text(strip=True).replace("%", "")
                            borrow_rate = Decimal(rate_text) / Decimal(100)
            except Exception as e:
                logger.debug("IBorrowDesk failed for %s: %s", company.ticker, e)

            if short_float is None:
                return None

            prev = _get_previous_signal(db, company.id, SignalType.SHORT_INTEREST)

            signal = NadirSignal(
                company_id=company.id,
                signal_type=SignalType.SHORT_INTEREST.value,
                current_value=short_float,
                previous_value=prev,
                threshold=Decimal("0.20"),
                condition_met=short_float > Decimal("0.20"),
                raw_data={"short_float": float(short_float), "borrow_rate": float(borrow_rate) if borrow_rate else None},
                source="finviz,iborrowdesk",
            )
            db.add(signal)
            return signal

    except Exception as e:
        logger.error("Short interest collection failed for %s: %s", company.ticker, e)
        return None


def finalize_short_interest_universe(db: Session):
    """After collecting all tickers, mark borrow_rate top-20% condition."""
    from sqlalchemy import desc
    recent_signals = (
        db.query(NadirSignal)
        .filter(NadirSignal.signal_type == SignalType.SHORT_INTEREST.value)
        .filter(NadirSignal.last_updated >= datetime.now(timezone.utc) - timedelta(hours=2))
        .all()
    )
    borrow_rates = []
    for s in recent_signals:
        if s.raw_data and s.raw_data.get("borrow_rate") is not None:
            borrow_rates.append((s, s.raw_data["borrow_rate"]))

    if not borrow_rates:
        return

    borrow_rates.sort(key=lambda x: x[1], reverse=True)
    top_20_cutoff = max(1, len(borrow_rates) // 5)
    top_20_set = {s.id for s, _ in borrow_rates[:top_20_cutoff]}

    for s in recent_signals:
        sf = float(s.current_value) if s.current_value else 0
        in_top_20 = s.id in top_20_set
        s.condition_met = sf > 0.20 and in_top_20
        s.raw_data = {**(s.raw_data or {}), "in_top_20_borrow": in_top_20}


# ─────────────────────────────────────────────────
# SIGNAL 2: Analyst Sentiment + Moral Language
# ─────────────────────────────────────────────────

MORAL_LANGUAGE_PROMPT = """Score this analyst report on a scale of 0-10 for moral condemnation language. Moral condemnation language frames the company's situation as deserved punishment, inevitable reckoning, or trust violation rather than as a business challenge requiring financial analysis.

Specific language to detect: deserved, finally, reckless, credibility destroyed, trust violated, caught up with them, paying the price, inevitable collapse, management destroyed value, shareholders betrayed, long overdue, accountability moment, house of cards.

Return ONLY valid JSON in this exact format:
{"score": <integer 0-10>, "examples": ["<string>", "<string>"], "classification": "<analytical|negative_analytical|moral_condemnation>", "reasoning": "<one sentence>"}

Report text:
{report_text}"""


def collect_analyst_sentiment(db: Session, company: Company) -> Tuple[Optional[NadirSignal], Optional[NadirSignal]]:
    """Collect analyst sentiment from Polygon + moral language scoring."""
    settings = get_settings()
    sentiment_signal = None
    moral_signal = None

    try:
        with httpx.Client() as client:
            # Analyst ratings from Polygon
            buy_count = hold_count = sell_count = 0
            try:
                url = f"https://api.polygon.io/v3/reference/tickers/{company.ticker}/ratings"
                resp = client.get(url, params={"apiKey": settings.polygon_api_key}, timeout=15)
                if resp.status_code == 200:
                    data = resp.json()
                    if "results" in data:
                        ratings = data["results"]
                        buy_count = ratings.get("buy", 0) + ratings.get("strong_buy", 0)
                        hold_count = ratings.get("hold", 0)
                        sell_count = ratings.get("sell", 0) + ratings.get("strong_sell", 0)
            except Exception as e:
                logger.warning("Polygon ratings failed for %s: %s", company.ticker, e)

            total = buy_count + hold_count + sell_count
            sell_pct = Decimal(str(sell_count / total)) if total > 0 else Decimal(0)

            # Moral language scoring via simulated analyst report scraping
            moral_scores: List[float] = []
            report_texts = _fetch_analyst_report_snippets(client, company.ticker)

            for text in report_texts[:5]:
                try:
                    prompt = MORAL_LANGUAGE_PROMPT.replace("{report_text}", text[:3000])
                    result = call_haiku(prompt)
                    parsed = parse_json_response(result)
                    if "score" in parsed:
                        moral_scores.append(float(parsed["score"]))
                except Exception as e:
                    logger.warning("Moral language scoring failed: %s", e)

            avg_moral = Decimal(str(sum(moral_scores) / len(moral_scores))) if moral_scores else Decimal(0)

            prev_sent = _get_previous_signal(db, company.id, SignalType.ANALYST_SENTIMENT)
            sentiment_signal = NadirSignal(
                company_id=company.id,
                signal_type=SignalType.ANALYST_SENTIMENT.value,
                current_value=sell_pct,
                previous_value=prev_sent,
                threshold=Decimal("0.70"),
                condition_met=sell_pct > Decimal("0.70") and avg_moral > Decimal("6.0"),
                raw_data={
                    "buy_count": buy_count, "hold_count": hold_count, "sell_count": sell_count,
                    "sell_pct": float(sell_pct), "avg_moral_score": float(avg_moral),
                    "moral_scores": moral_scores,
                },
                source="polygon,seekingalpha",
            )
            db.add(sentiment_signal)

            # Separate moral language signal record
            prev_moral = _get_previous_signal(db, company.id, SignalType.MORAL_LANGUAGE)
            moral_signal = NadirSignal(
                company_id=company.id,
                signal_type=SignalType.MORAL_LANGUAGE.value,
                current_value=avg_moral,
                previous_value=prev_moral,
                threshold=Decimal("6.0"),
                condition_met=avg_moral > Decimal("6.0"),
                raw_data={"scores": moral_scores, "avg_score": float(avg_moral)},
                source="seekingalpha,claude",
            )
            db.add(moral_signal)

    except Exception as e:
        logger.error("Analyst sentiment collection failed for %s: %s", company.ticker, e)

    return sentiment_signal, moral_signal


def _fetch_analyst_report_snippets(client: httpx.Client, ticker: str) -> List[str]:
    """Fetch recent analyst report text snippets. Falls back to news headlines."""
    snippets = []
    try:
        settings = get_settings()
        url = f"https://api.polygon.io/v2/reference/news"
        resp = client.get(url, params={
            "ticker": ticker, "limit": 5, "apiKey": settings.polygon_api_key,
        }, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            for article in data.get("results", []):
                text = article.get("description", "") or article.get("title", "")
                if text:
                    snippets.append(text)
    except Exception as e:
        logger.debug("News fetch failed for %s: %s", ticker, e)
    return snippets


# ─────────────────────────────────────────────────
# SIGNAL 3: Insider Buying
# ─────────────────────────────────────────────────

def collect_insider_buying(db: Session, company: Company) -> Optional[NadirSignal]:
    """Parse SEC EDGAR Form 4 filings for insider purchases."""
    try:
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=90)
        start_str = start_date.strftime("%Y-%m-%d")
        end_str = end_date.strftime("%Y-%m-%d")

        with httpx.Client() as client:
            url = "https://efts.sec.gov/LATEST/search-index"
            params = {
                "q": f'"{company.ticker}"',
                "forms": "4",
                "dateRange": "custom",
                "startdt": start_str,
                "enddt": end_str,
            }
            time.sleep(EDGAR_DELAY)
            resp = client.get(url, params=params, headers=SEC_HEADERS, timeout=20)

            purchases: List[Dict[str, Any]] = []
            unique_insiders: set = set()
            distinct_dates: set = set()
            total_value = Decimal(0)

            if resp.status_code == 200:
                data = resp.json()
                filings = data.get("hits", {}).get("hits", [])

                for filing in filings[:30]:
                    try:
                        source = filing.get("_source", {})
                        # Skip 10b5-1 plan transactions
                        display = source.get("display_names", [])
                        file_description = source.get("file_description", "")
                        if "10b5-1" in str(display) + str(file_description):
                            continue

                        person_name = source.get("display_names", ["Unknown"])[0] if display else "Unknown"
                        file_date = source.get("file_date", "")

                        unique_insiders.add(person_name)
                        if file_date:
                            distinct_dates.add(file_date[:10])

                        # Estimate value from filing metadata
                        est_value = Decimal("50000")
                        total_value += est_value

                        purchases.append({
                            "person": person_name,
                            "date": file_date,
                            "estimated_value": float(est_value),
                        })
                    except Exception:
                        continue

            n_insiders = len(unique_insiders)
            n_dates = len(distinct_dates)
            log_val = Decimal(str(math.log10(max(float(total_value), 1) / 10000))) if total_value > 0 else Decimal(0)
            score = Decimal(str(n_insiders * 2 + n_dates)) + log_val

            prev = _get_previous_signal(db, company.id, SignalType.INSIDER_BUYING)
            signal = NadirSignal(
                company_id=company.id,
                signal_type=SignalType.INSIDER_BUYING.value,
                current_value=score,
                previous_value=prev,
                threshold=Decimal("8.0"),
                condition_met=score >= Decimal("8.0"),
                raw_data={
                    "unique_insiders": n_insiders,
                    "distinct_dates": n_dates,
                    "total_value": float(total_value),
                    "score": float(score),
                    "purchases": purchases[:10],
                },
                source="sec_edgar",
            )
            db.add(signal)
            return signal

    except Exception as e:
        logger.error("Insider buying collection failed for %s: %s", company.ticker, e)
        return None


# ─────────────────────────────────────────────────
# SIGNAL 4: GRR Stability
# ─────────────────────────────────────────────────

GRR_PROMPT = """Extract gross revenue retention or the closest available retention metric from this SEC filing text.

Gross Revenue Retention (GRR) measures what percentage of prior period subscription revenue from existing customers was retained, explicitly EXCLUDING any expansion revenue. It should be a percentage at or below 100%.

Search for these terms: 'gross retention', 'gross dollar retention', 'dollar-based gross retention', 'net retention', 'revenue retention'. If you find net revenue retention (NRR) but not GRR, note that NRR includes expansion and will be above 100%.

Return ONLY valid JSON in this exact format:
{"metric_found": "<exact metric name as written in filing>", "value": <decimal between 0 and 1, e.g. 0.91 for 91%>, "is_exact_grr": <boolean>, "period": "<quarter and year>", "excerpt": "<exact quote from filing, max 200 chars>", "confidence": "<high|medium|low>"}

Filing text:
{filing_text}"""


def collect_grr_stability(db: Session, company: Company) -> Optional[NadirSignal]:
    """Extract GRR from most recent 10-Q/10-K filing."""
    try:
        filing_text = _fetch_latest_filing(company.ticker)
        if not filing_text:
            return None

        prompt = GRR_PROMPT.replace("{filing_text}", filing_text[:15000])
        result = call_haiku(prompt)
        parsed = parse_json_response(result)

        if not parsed or "value" not in parsed:
            return None

        grr_value = Decimal(str(parsed["value"]))
        confidence = parsed.get("confidence", "low")
        is_exact = parsed.get("is_exact_grr", False)

        # Calculate stability from historical signals
        historical = (
            db.query(NadirSignal)
            .filter(NadirSignal.company_id == company.id)
            .filter(NadirSignal.signal_type == SignalType.GRR_STABILITY.value)
            .order_by(NadirSignal.last_updated.desc())
            .limit(4)
            .all()
        )

        grr_values = [float(h.current_value) for h in historical if h.current_value]
        trailing_avg = sum(grr_values) / len(grr_values) if grr_values else float(grr_value)
        trailing_std = (
            (sum((v - trailing_avg) ** 2 for v in grr_values) / len(grr_values)) ** 0.5
            if len(grr_values) > 1
            else 0.0
        )
        is_stable = abs(float(grr_value) - trailing_avg) < 0.02

        condition = (
            grr_value > Decimal("0.88")
            and is_stable
            and confidence != "low"
        )

        prev = _get_previous_signal(db, company.id, SignalType.GRR_STABILITY)
        signal = NadirSignal(
            company_id=company.id,
            signal_type=SignalType.GRR_STABILITY.value,
            current_value=grr_value,
            previous_value=prev,
            threshold=Decimal("0.88"),
            condition_met=condition,
            raw_data={
                "metric_found": parsed.get("metric_found", ""),
                "is_exact_grr": is_exact,
                "period": parsed.get("period", ""),
                "excerpt": parsed.get("excerpt", ""),
                "confidence": confidence,
                "trailing_4q_avg": trailing_avg,
                "trailing_4q_std": trailing_std,
                "is_stable": is_stable,
            },
            source="sec_edgar,claude",
        )
        db.add(signal)
        return signal

    except Exception as e:
        logger.error("GRR collection failed for %s: %s", company.ticker, e)
        return None


def _fetch_latest_filing(ticker: str) -> Optional[str]:
    """Fetch most recent 10-Q or 10-K from EDGAR full-text search."""
    try:
        with httpx.Client() as client:
            time.sleep(EDGAR_DELAY)
            url = "https://efts.sec.gov/LATEST/search-index"
            resp = client.get(url, params={
                "q": f'"{ticker}"',
                "forms": "10-Q,10-K",
                "dateRange": "custom",
                "startdt": (datetime.now(timezone.utc) - timedelta(days=180)).strftime("%Y-%m-%d"),
                "enddt": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            }, headers=SEC_HEADERS, timeout=20)

            if resp.status_code != 200:
                return None

            data = resp.json()
            hits = data.get("hits", {}).get("hits", [])
            if not hits:
                return None

            filing_url = hits[0].get("_source", {}).get("file_url", "")
            if not filing_url:
                return None

            if not filing_url.startswith("http"):
                filing_url = f"https://www.sec.gov{filing_url}"

            time.sleep(EDGAR_DELAY)
            doc_resp = client.get(filing_url, headers=SEC_HEADERS, timeout=30)
            if doc_resp.status_code == 200:
                soup = BeautifulSoup(doc_resp.text, "lxml")
                return soup.get_text(separator=" ", strip=True)[:30000]
    except Exception as e:
        logger.warning("Filing fetch failed for %s: %s", ticker, e)
    return None


# ─────────────────────────────────────────────────
# Utility
# ─────────────────────────────────────────────────

def _get_previous_signal(db: Session, company_id, signal_type: SignalType) -> Optional[Decimal]:
    prev = (
        db.query(NadirSignal.current_value)
        .filter(NadirSignal.company_id == company_id)
        .filter(NadirSignal.signal_type == signal_type.value)
        .order_by(NadirSignal.last_updated.desc())
        .first()
    )
    return prev[0] if prev else None


def run_all_collectors(db: Session, companies: List[Company], signal_type: Optional[str] = None):
    """Run specified (or all) signal collectors for a list of companies."""
    for company in companies:
        try:
            if signal_type is None or signal_type == SignalType.SHORT_INTEREST.value:
                collect_short_interest(db, company)
            if signal_type is None or signal_type in (
                SignalType.ANALYST_SENTIMENT.value, SignalType.MORAL_LANGUAGE.value
            ):
                collect_analyst_sentiment(db, company)
            if signal_type is None or signal_type == SignalType.INSIDER_BUYING.value:
                collect_insider_buying(db, company)
            if signal_type is None or signal_type == SignalType.GRR_STABILITY.value:
                collect_grr_stability(db, company)
            db.flush()
        except Exception as e:
            logger.error("Signal collection failed for %s: %s", company.ticker, e)
            db.rollback()
            continue

    if signal_type is None or signal_type == SignalType.SHORT_INTEREST.value:
        finalize_short_interest_universe(db)

    db.commit()
