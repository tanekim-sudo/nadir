"""
Belief Stack Engine — Constrained Reverse-DCF with Assumption Isolation.

Replaces the old qualitative belief_stack_builder.py with a rigorous
quantitative decomposition framework.
"""
import logging
import math
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

import httpx
import numpy as np
from scipy.optimize import minimize
from sqlalchemy.orm import Session

from app.core.claude import call_opus, parse_json_response
from app.core.config import get_settings
from app.models.belief_stack import BeliefStackNode, DCFDecomposition, JobPostingSignal
from app.models.company import Company
from app.models.nadir_signal import NadirSignal

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────
# Default parameters
# ─────────────────────────────────────────────────
DEFAULT_TAX_RATE = 0.21
DEFAULT_TERMINAL_GROWTH = 0.025
DEFAULT_ERP = 0.055
DEFAULT_RISK_FREE = 0.043  # updated by FRED pull

# Node definitions for the decomposition tree
NODE_DEFINITIONS = {
    "A": {"name": "Revenue Growth", "parent": None, "children": ["A1", "A2", "A3", "A4"]},
    "A1": {"name": "Market Size Growth (TAM)", "parent": "A"},
    "A2": {"name": "Market Share Trajectory", "parent": "A"},
    "A3": {"name": "Pricing Power", "parent": "A"},
    "A4": {"name": "Expansion Revenue", "parent": "A"},
    "B": {"name": "Terminal Operating Margin", "parent": None, "children": ["B1", "B2", "B3", "B4"]},
    "B1": {"name": "Gross Margin at Scale", "parent": "B"},
    "B2": {"name": "Sales Efficiency (S&M Leverage)", "parent": "B"},
    "B3": {"name": "R&D Leverage", "parent": "B"},
    "B4": {"name": "Competitive Intensity", "parent": "B"},
    "C": {"name": "Discount Rate (WACC)", "parent": None, "children": ["C1", "C2", "C3"]},
    "C1": {"name": "Business Risk", "parent": "C"},
    "C2": {"name": "Financial Risk", "parent": "C"},
    "C3": {"name": "Execution Risk", "parent": "C"},
}

CONFIDENCE_WEIGHTS = {"HIGH": 1.0, "MEDIUM": 0.6, "LOW": 0.3}


# ─────────────────────────────────────────────────
# STEP 1: Market Price Decomposition
# ─────────────────────────────────────────────────

def _fetch_financials(ticker: str) -> Dict[str, Any]:
    """Pull financial data from Polygon API."""
    settings = get_settings()
    data: Dict[str, Any] = {
        "shares": 0, "debt": 0, "cash": 0, "current_price": 0,
        "ttm_revenue": 0, "ttm_gross_profit": 0, "ttm_ebit": 0,
        "total_assets": 0, "current_liabilities": 0,
        "beta": 1.2, "consensus_growth_y1": 0.10, "consensus_growth_y2": 0.08,
    }
    try:
        with httpx.Client() as client:
            # Ticker details
            resp = client.get(
                f"https://api.polygon.io/v3/reference/tickers/{ticker}",
                params={"apiKey": settings.polygon_api_key}, timeout=15,
            )
            if resp.status_code == 200:
                r = resp.json().get("results", {})
                data["shares"] = r.get("share_class_shares_outstanding", 0) or 0
                data["current_price"] = (r.get("market_cap", 0) or 0) / max(data["shares"], 1)

            # Financials
            fin_resp = client.get(
                f"https://api.polygon.io/vX/reference/financials",
                params={"ticker": ticker, "limit": 4, "timeframe": "quarterly",
                        "apiKey": settings.polygon_api_key},
                timeout=15,
            )
            if fin_resp.status_code == 200:
                results = fin_resp.json().get("results", [])
                for q in results[:4]:
                    financials = q.get("financials", {})
                    income = financials.get("income_statement", {})
                    balance = financials.get("balance_sheet", {})

                    data["ttm_revenue"] += income.get("revenues", {}).get("value", 0) or 0
                    data["ttm_gross_profit"] += income.get("gross_profit", {}).get("value", 0) or 0
                    data["ttm_ebit"] += income.get("operating_income_loss", {}).get("value", 0) or 0

                    if results.index(q) == 0:
                        data["debt"] = balance.get("long_term_debt", {}).get("value", 0) or 0
                        data["cash"] = balance.get("cash_and_cash_equivalents", {}).get("value", 0) or 0
                        data["total_assets"] = balance.get("total_assets", {}).get("value", 0) or 0
                        data["current_liabilities"] = balance.get("current_liabilities", {}).get("value", 0) or 0

    except Exception as e:
        logger.warning("Financial data fetch failed for %s: %s", ticker, e)

    return data


def _get_risk_free_rate() -> float:
    """Pull 10-year Treasury yield from FRED."""
    try:
        with httpx.Client() as client:
            resp = client.get(
                "https://api.stlouisfed.org/fred/series/observations",
                params={
                    "series_id": "DGS10", "sort_order": "desc",
                    "limit": 1, "file_type": "json",
                    "api_key": "DEMO_KEY",
                },
                timeout=10,
            )
            if resp.status_code == 200:
                obs = resp.json().get("observations", [])
                if obs and obs[0].get("value") != ".":
                    return float(obs[0]["value"]) / 100
    except Exception:
        pass
    return DEFAULT_RISK_FREE


# ─────────────────────────────────────────────────
# STEP 2: Solve for Implied Assumptions
# ─────────────────────────────────────────────────

def _dcf_value(
    ttm_revenue: float, current_ebit_margin: float,
    g1: float, terminal_margin: float, wacc: float,
    sales_to_capital: float,
) -> float:
    """Forward DCF model that returns enterprise value."""
    if wacc <= DEFAULT_TERMINAL_GROWTH:
        return 1e15
    revenue = ttm_revenue
    ev = 0.0
    g = g1
    for year in range(1, 11):
        if year <= 3:
            growth = g1 * (1 - (year - 1) * 0.05)
        else:
            t = (year - 3) / 7
            growth = g1 * (1 - 0.15) * (1 - t) + DEFAULT_TERMINAL_GROWTH * t

        revenue *= (1 + growth)
        margin_progress = min(year / 10, 1.0)
        margin = current_ebit_margin + (terminal_margin - current_ebit_margin) * margin_progress
        ebit = revenue * margin
        nopat = ebit * (1 - DEFAULT_TAX_RATE)
        reinvestment = max(revenue * growth / max(sales_to_capital, 0.5), 0)
        fcff = nopat - reinvestment
        ev += fcff / (1 + wacc) ** year

    # Terminal value
    terminal_fcff = revenue * terminal_margin * (1 - DEFAULT_TAX_RATE)
    tv = terminal_fcff * (1 + DEFAULT_TERMINAL_GROWTH) / (wacc - DEFAULT_TERMINAL_GROWTH)
    ev += tv / (1 + wacc) ** 10
    return ev


def solve_implied_assumptions(financials: Dict[str, Any]) -> Dict[str, Any]:
    """Solve backward from EV to find implied growth, margin, WACC."""
    price = financials["current_price"]
    shares = financials["shares"]
    debt = financials["debt"]
    cash = financials["cash"]
    current_ev = (price * shares) + debt - cash
    ttm_rev = max(financials["ttm_revenue"], 1)
    ttm_ebit = financials["ttm_ebit"]
    current_margin = ttm_ebit / ttm_rev if ttm_rev else 0
    total_assets = financials["total_assets"]
    current_liab = financials["current_liabilities"]
    invested_capital = total_assets - cash - current_liab
    sales_to_capital = ttm_rev / max(invested_capital, 1)

    risk_free = _get_risk_free_rate()
    beta = financials.get("beta", 1.2)
    cost_of_equity = risk_free + beta * DEFAULT_ERP
    equity_weight = (price * shares) / max((price * shares) + debt, 1)
    debt_weight = 1 - equity_weight
    base_wacc = cost_of_equity * equity_weight + risk_free * 1.2 * (1 - DEFAULT_TAX_RATE) * debt_weight

    def objective(params):
        g1, term_margin = params
        dcf_ev = _dcf_value(ttm_rev, current_margin, g1, term_margin, base_wacc, sales_to_capital)
        return (dcf_ev - current_ev) ** 2

    result = minimize(
        objective,
        x0=[0.15, 0.20],
        bounds=[(-0.30, 1.50), (0.0, 0.50)],
        method="L-BFGS-B",
    )

    return {
        "current_ev": current_ev,
        "implied_year1_growth": float(result.x[0]),
        "implied_terminal_margin": float(result.x[1]),
        "implied_wacc": base_wacc,
        "solver_converged": result.success,
        "solver_error": float(result.fun ** 0.5),
        "ev_revenue_multiple": current_ev / ttm_rev if ttm_rev else 0,
        "current_margin": current_margin,
        "risk_free_rate": risk_free,
        "beta": beta,
        "sales_to_capital": sales_to_capital,
    }


# ─────────────────────────────────────────────────
# STEP 3-4: Node Decomposition + Evidence Scoring
# ─────────────────────────────────────────────────

EVIDENCE_PROMPT = """You are scoring the evidence for a specific assumption node in a reverse-DCF decomposition.

Company: {ticker} ({name})
Node: {node_id} — {node_name}
Parent assumption: {parent_label}

The market is currently pricing this assumption at: {implied_value}

Available evidence:
- Short interest: {short_interest}%
- Job posting velocity score: {job_velocity}
- Squeeze probability: {squeeze_score}
- Current gross margin: {gross_margin}%
- Revenue growth (TTM): {rev_growth}%

Score this node's evidence:
1. What does observable evidence suggest the actual value should be?
2. How confident are you in that evidence? (HIGH/MEDIUM/LOW)
3. What direction does evidence point relative to market implied? (STRONGLY_BULLISH/BULLISH/NEUTRAL/BEARISH/STRONGLY_BEARISH)
4. What is the gap magnitude? (numerical, positive = bullish gap, negative = bearish gap)

Return ONLY valid JSON:
{{"evidence_value": "<what evidence suggests>", "evidence_label": "<one sentence summary>", "evidence_direction": "<STRONGLY_BULLISH|BULLISH|NEUTRAL|BEARISH|STRONGLY_BEARISH>", "evidence_confidence": "<HIGH|MEDIUM|LOW>", "gap_magnitude": <float>, "evidence_sources": ["<source1>", "<source2>"]}}"""


def _score_nodes_with_claude(
    db: Session, company: Company, dcf_result: Dict[str, Any],
    signal_map: Dict[str, NadirSignal],
) -> List[Dict[str, Any]]:
    """Use Claude to score evidence for each leaf node."""
    short_interest = signal_map.get("SHORT_INTEREST")
    job_vel = signal_map.get("JOB_POSTING_VELOCITY")
    squeeze = signal_map.get("SQUEEZE_PROBABILITY")

    si_val = f"{float(short_interest.current_value)*100:.1f}" if short_interest and short_interest.current_value else "N/A"
    jv_val = f"{float(job_vel.current_value):.4f}" if job_vel and job_vel.current_value else "N/A"
    sq_val = f"{float(squeeze.current_value):.4f}" if squeeze and squeeze.current_value else "N/A"
    gm_val = f"{dcf_result.get('current_margin', 0)*100:.1f}"
    rg_val = f"{dcf_result.get('implied_year1_growth', 0)*100:.1f}"

    scored_nodes = []
    leaf_nodes = [nid for nid, nd in NODE_DEFINITIONS.items() if "children" not in nd]

    # Group scoring: batch leaf nodes into one prompt for efficiency
    for node_id in leaf_nodes:
        nd = NODE_DEFINITIONS[node_id]
        parent = NODE_DEFINITIONS.get(nd["parent"], {})

        if nd["parent"] == "A":
            implied = f"{dcf_result['implied_year1_growth']*100:.1f}% growth"
        elif nd["parent"] == "B":
            implied = f"{dcf_result['implied_terminal_margin']*100:.1f}% terminal margin"
        else:
            implied = f"{dcf_result['implied_wacc']*100:.1f}% WACC"

        try:
            from app.core.claude import call_haiku
            prompt = EVIDENCE_PROMPT.format(
                ticker=company.ticker, name=company.name,
                node_id=node_id, node_name=nd["name"],
                parent_label=parent.get("name", ""),
                implied_value=implied,
                short_interest=si_val, job_velocity=jv_val,
                squeeze_score=sq_val, gross_margin=gm_val, rev_growth=rg_val,
            )
            result = call_haiku(prompt)
            parsed = parse_json_response(result)
            if parsed:
                scored_nodes.append({"node_id": node_id, **parsed})
        except Exception as e:
            logger.warning("Evidence scoring failed for %s/%s: %s", company.ticker, node_id, e)
            scored_nodes.append({
                "node_id": node_id,
                "evidence_value": "insufficient data",
                "evidence_label": "Automated scoring failed",
                "evidence_direction": "NEUTRAL",
                "evidence_confidence": "LOW",
                "gap_magnitude": 0.0,
                "evidence_sources": [],
            })

    return scored_nodes


# ─────────────────────────────────────────────────
# STEP 5-6: Conviction Scoring + Variant View
# ─────────────────────────────────────────────────

def _calculate_conviction(scored_nodes: List[Dict]) -> Tuple[List[Dict], Dict]:
    """Calculate conviction scores and identify primary mispricing."""
    for node in scored_nodes:
        gap = abs(node.get("gap_magnitude", 0))
        conf = CONFIDENCE_WEIGHTS.get(node.get("evidence_confidence", "LOW"), 0.3)
        node["conviction_score"] = round(gap * conf, 4)

    sorted_nodes = sorted(scored_nodes, key=lambda n: n.get("conviction_score", 0), reverse=True)
    primary = sorted_nodes[0] if sorted_nodes else {}
    return scored_nodes, primary


# ─────────────────────────────────────────────────
# Main Entry Point
# ─────────────────────────────────────────────────

def run_belief_stack_engine(db: Session, company: Company) -> Optional[Dict[str, Any]]:
    """Full belief stack engine run: decompose, solve, score, identify mispricing."""
    logger.info("Running belief stack engine for %s", company.ticker)

    # Step 1: Fetch financials and decompose
    financials = _fetch_financials(company.ticker)
    if financials["ttm_revenue"] == 0:
        logger.warning("No financial data for %s, skipping DCF", company.ticker)
        return None

    # Step 2: Solve for implied assumptions
    dcf_result = solve_implied_assumptions(financials)

    # Store DCF decomposition
    dcf_record = DCFDecomposition(
        company_id=company.id,
        current_ev=int(dcf_result["current_ev"]),
        current_price=Decimal(str(financials["current_price"])),
        shares=financials["shares"],
        debt=financials["debt"],
        cash=financials["cash"],
        ttm_revenue=financials["ttm_revenue"],
        ttm_gross_profit=financials["ttm_gross_profit"],
        ttm_ebit=financials["ttm_ebit"],
        implied_year1_growth=Decimal(str(round(dcf_result["implied_year1_growth"], 8))),
        implied_terminal_margin=Decimal(str(round(dcf_result["implied_terminal_margin"], 8))),
        implied_wacc=Decimal(str(round(dcf_result["implied_wacc"], 8))),
        ev_revenue_multiple=Decimal(str(round(dcf_result["ev_revenue_multiple"], 6))),
        solver_converged=dcf_result["solver_converged"],
        solver_error=Decimal(str(round(dcf_result["solver_error"], 4))),
        raw_solver_output=dcf_result,
    )
    db.add(dcf_record)

    # Step 3-4: Get signals and score nodes
    signals = (
        db.query(NadirSignal)
        .filter(NadirSignal.company_id == company.id)
        .order_by(NadirSignal.last_updated.desc())
        .all()
    )
    signal_map = {}
    for s in signals:
        if s.signal_type not in signal_map:
            signal_map[s.signal_type] = s

    scored_nodes = _score_nodes_with_claude(db, company, dcf_result, signal_map)

    # Step 5: Calculate conviction and find primary mispricing
    scored_nodes, primary_node = _calculate_conviction(scored_nodes)

    # Step 6: Store all nodes
    db.query(BeliefStackNode).filter(BeliefStackNode.company_id == company.id).delete()

    # Store root nodes (A, B, C)
    root_values = {
        "A": f"{dcf_result['implied_year1_growth']*100:.1f}%",
        "B": f"{dcf_result['implied_terminal_margin']*100:.1f}%",
        "C": f"{dcf_result['implied_wacc']*100:.1f}%",
    }
    for root_id in ["A", "B", "C"]:
        nd = NODE_DEFINITIONS[root_id]
        db.add(BeliefStackNode(
            company_id=company.id,
            node_id=root_id,
            node_name=nd["name"],
            parent_node=None,
            market_implied_value=root_values[root_id],
            market_implied_label=f"Market implies {nd['name'].lower()} of {root_values[root_id]}",
        ))

    # Store leaf nodes with evidence
    for node_data in scored_nodes:
        node_id = node_data["node_id"]
        nd = NODE_DEFINITIONS.get(node_id, {})
        parent = nd.get("parent", "")
        is_primary = node_data.get("node_id") == primary_node.get("node_id")

        db.add(BeliefStackNode(
            company_id=company.id,
            node_id=node_id,
            node_name=nd.get("name", node_id),
            parent_node=parent,
            market_implied_value=root_values.get(parent, ""),
            market_implied_label=f"Implied by parent {parent}",
            evidence_value=node_data.get("evidence_value", ""),
            evidence_label=node_data.get("evidence_label", ""),
            evidence_direction=node_data.get("evidence_direction", "NEUTRAL"),
            evidence_confidence=node_data.get("evidence_confidence", "LOW"),
            gap_magnitude=Decimal(str(node_data.get("gap_magnitude", 0))),
            conviction_score=Decimal(str(node_data.get("conviction_score", 0))),
            evidence_sources=node_data.get("evidence_sources"),
        ))

    db.commit()

    # Build summary
    summary = {
        "implied_ev": dcf_result["current_ev"],
        "implied_year1_growth": dcf_result["implied_year1_growth"],
        "implied_terminal_margin": dcf_result["implied_terminal_margin"],
        "implied_wacc": dcf_result["implied_wacc"],
        "solver_converged": dcf_result["solver_converged"],
        "primary_mispricing_node": primary_node.get("node_id"),
        "primary_mispricing_name": NODE_DEFINITIONS.get(primary_node.get("node_id", ""), {}).get("name"),
        "primary_conviction": primary_node.get("conviction_score", 0),
        "primary_direction": primary_node.get("evidence_direction"),
        "all_nodes": scored_nodes,
    }

    logger.info(
        "Belief stack for %s: implied growth=%.1f%%, margin=%.1f%%, primary=%s (%.2f)",
        company.ticker,
        dcf_result["implied_year1_growth"] * 100,
        dcf_result["implied_terminal_margin"] * 100,
        primary_node.get("node_id", "?"),
        primary_node.get("conviction_score", 0),
    )

    return summary
