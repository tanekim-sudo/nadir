"""
Universe Manager — maintains the list of enterprise tech companies to screen.
Pulls holdings from QQQ, IGV, WCLD, BUG ETFs and deduplicates.
"""
import logging
import time
from typing import Dict, List, Set

import httpx
from bs4 import BeautifulSoup
from sqlalchemy.orm import Session

from app.db.session import _get_session_factory
from app.models.company import Company

logger = logging.getLogger(__name__)

ETF_HOLDINGS_URLS: Dict[str, str] = {
    "QQQ": "https://www.invesco.com/us/financial-products/etfs/holdings?audienceType=Investor&ticker=QQQ",
    "IGV": "https://www.ishares.com/us/products/239774/ishares-expanded-techsoftware-sector-etf/1467271812596.ajax?tab=holdings&fileType=csv",
    "WCLD": "https://www.wisdomtree.com/investments/etfs/megatrends/wcld",
    "BUG": "https://www.globalxetfs.com/funds/bug/",
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}


def _fetch_qqq_tickers(client: httpx.Client) -> Set[str]:
    """Parse QQQ top holdings from Invesco."""
    tickers: Set[str] = set()
    try:
        resp = client.get(ETF_HOLDINGS_URLS["QQQ"], headers=HEADERS, timeout=30)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "lxml")
            for row in soup.select("table tbody tr"):
                cells = row.select("td")
                if cells and len(cells) >= 2:
                    ticker = cells[0].get_text(strip=True).upper()
                    if ticker and ticker.isalpha() and len(ticker) <= 6:
                        tickers.add(ticker)
    except Exception as e:
        logger.warning("Failed to fetch QQQ holdings: %s", e)
    return tickers


def _fetch_ishares_csv_tickers(client: httpx.Client) -> Set[str]:
    """Parse iShares IGV holdings CSV."""
    tickers: Set[str] = set()
    try:
        resp = client.get(ETF_HOLDINGS_URLS["IGV"], headers=HEADERS, timeout=30)
        if resp.status_code == 200:
            lines = resp.text.strip().split("\n")
            for line in lines[10:]:  # skip header rows
                parts = line.split(",")
                if len(parts) >= 2:
                    ticker = parts[0].strip().strip('"').upper()
                    if ticker and ticker.isalpha() and len(ticker) <= 6:
                        tickers.add(ticker)
    except Exception as e:
        logger.warning("Failed to fetch IGV holdings: %s", e)
    return tickers


def _fetch_generic_page_tickers(client: httpx.Client, url: str, label: str) -> Set[str]:
    """Attempt to parse tickers from an ETF holdings page."""
    tickers: Set[str] = set()
    try:
        resp = client.get(url, headers=HEADERS, timeout=30)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "lxml")
            for row in soup.select("table tbody tr"):
                cells = row.select("td")
                if cells:
                    candidate = cells[0].get_text(strip=True).upper()
                    if candidate and candidate.isalpha() and 1 <= len(candidate) <= 6:
                        tickers.add(candidate)
    except Exception as e:
        logger.warning("Failed to fetch %s holdings: %s", label, e)
    return tickers


# Well-known enterprise tech tickers as fallback seed
SEED_TICKERS = [
    "CRM", "NOW", "WDAY", "SNOW", "DDOG", "CRWD", "ZS", "NET", "PANW", "FTNT",
    "MNDY", "HUBS", "VEEV", "TEAM", "ADBE", "MSFT", "ORCL", "SAP", "INTU", "SHOP",
    "MDB", "ESTC", "CFLT", "PATH", "S", "OKTA", "TWLO", "BILL", "PCOR", "FROG",
    "DOCN", "DT", "TOST", "BRZE", "GTLB", "SMAR", "TYL", "PAYC", "GWRE", "ALTR",
    "TENB", "VRNS", "QLYS", "RPD", "CYBR", "SAIL", "ZI", "ENVX", "CERT", "WK",
    "KNBE", "SPSC", "NCNO", "APPF", "QTWO", "CWAN", "BSY", "FRSH", "PTC", "ANSS",
    "CDNS", "SNPS", "PLTR", "AI", "CLSK", "RIOT", "AVLR", "ZEN", "SPLK", "BL",
    "COUP", "FIVN", "LSPD", "JAMF", "SUMO", "NEWR", "RNG", "NTNX", "BOX", "PRGS",
]


def fetch_all_tickers() -> Set[str]:
    """Fetch and deduplicate tickers from all ETF sources + seed list."""
    all_tickers: Set[str] = set(SEED_TICKERS)
    with httpx.Client() as client:
        all_tickers.update(_fetch_qqq_tickers(client))
        time.sleep(0.5)
        all_tickers.update(_fetch_ishares_csv_tickers(client))
        time.sleep(0.5)
        all_tickers.update(_fetch_generic_page_tickers(client, ETF_HOLDINGS_URLS["WCLD"], "WCLD"))
        time.sleep(0.5)
        all_tickers.update(_fetch_generic_page_tickers(client, ETF_HOLDINGS_URLS["BUG"], "BUG"))
    logger.info("Total unique tickers after dedup: %d", len(all_tickers))
    return all_tickers


def sync_universe(db: Session | None = None) -> int:
    """Sync tickers into companies table. Returns count of new companies added."""
    close_db = False
    if db is None:
        db = _get_session_factory()()
        close_db = True

    try:
        tickers = fetch_all_tickers()
        existing = {c.ticker for c in db.query(Company.ticker).all()}
        new_count = 0
        for ticker in sorted(tickers - existing):
            company = Company(ticker=ticker, name=ticker, sector="Technology")
            db.add(company)
            new_count += 1
        db.commit()
        logger.info("Added %d new companies to universe (%d total)", new_count, len(existing) + new_count)
        return new_count
    finally:
        if close_db:
            db.close()


def add_ticker(db: Session, ticker: str, name: str = "", sector: str = "Technology") -> Company:
    ticker = ticker.upper().strip()
    existing = db.query(Company).filter(Company.ticker == ticker).first()
    if existing:
        return existing
    company = Company(ticker=ticker, name=name or ticker, sector=sector)
    db.add(company)
    db.commit()
    db.refresh(company)
    return company


def remove_ticker(db: Session, ticker: str) -> bool:
    company = db.query(Company).filter(Company.ticker == ticker.upper()).first()
    if not company:
        return False
    db.delete(company)
    db.commit()
    return True
