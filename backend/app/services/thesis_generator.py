"""
Thesis Generator — generates formatted investment thesis when NADIR_COMPLETE is validated.
Updated to use the new 5 signals and DCF-based belief stack.
"""
import logging
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.core.claude import call_opus, parse_json_response
from app.models.belief_stack import BeliefStackNode, DCFDecomposition
from app.models.company import Company
from app.models.nadir_signal import NadirSignal

logger = logging.getLogger(__name__)

THESIS_PROMPT = """Generate a complete investment thesis for {ticker} ({company_name}).

This company has triggered all 5 NADIR detection conditions:
- Short interest: {short_interest}% (extreme bearish positioning)
- Analyst sell ratings: {sell_pct}% (consensus abandonment)
- Insider buying score: {insider_score} (management conviction)
- Customer job posting velocity: {job_velocity} (customers still hiring for product)
- Short squeeze probability: {squeeze_score} (mechanical squeeze conditions present)

DCF Decomposition:
- Current EV: ${current_ev:,.0f}
- Implied year 1 growth: {implied_growth}%
- Implied terminal margin: {implied_margin}%
- Primary mispricing node: {primary_node} — {primary_node_name}
- Primary conviction score: {primary_conviction}

Validation result: {validation_status} (confidence: {confidence})
Primary risk: {primary_risk}
Rehabilitation mechanism: {rehabilitation_mechanism}
Rehabilitation timeline: {rehabilitation_timeline}

Generate a thesis covering:
1. What the market consensus currently believes (the narrative)
2. What the operational signals actually show (the reality)
3. The specific disconnect between narrative and reality
4. The quantitative expression of the mispricing (from DCF decomposition)
5. The mechanism by which narrative corrects
6. The timeline for correction
7. What would prove the thesis wrong (falsification)
8. Key risks and monitoring signals
9. GRR monitoring threshold for post-entry falsification

Return ONLY valid JSON in this exact format:
{{"narrative": "<what market believes>", "reality": "<what signals show>", "disconnect": "<why narrative has overshot reality>", "quantitative_mispricing": "<DCF-based statement of the mispricing>", "rehabilitation_mechanism": "<specific event causing correction>", "rehabilitation_timeline": "<expected timeframe>", "falsification_condition": "<observable outcome proving thesis wrong>", "grr_falsification_threshold": 0.85, "time_horizon": "<maximum holding period>", "variant_view_summary": "<one paragraph precise variant view>", "key_risks": ["<risk 1>", "<risk 2>", "<risk 3>"], "monitoring_signals": ["<signal 1>", "<signal 2>", "<signal 3>"]}}"""


def generate_thesis(
    db: Session,
    company: Company,
    validation_result: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """Generate investment thesis for a validated NADIR_COMPLETE company."""
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

    dcf = (
        db.query(DCFDecomposition)
        .filter(DCFDecomposition.company_id == company.id)
        .order_by(DCFDecomposition.scan_date.desc())
        .first()
    )

    primary_node = (
        db.query(BeliefStackNode)
        .filter(BeliefStackNode.company_id == company.id)
        .filter(BeliefStackNode.conviction_score.isnot(None))
        .order_by(BeliefStackNode.conviction_score.desc())
        .first()
    )

    prompt = THESIS_PROMPT.format(
        ticker=company.ticker,
        company_name=company.name,
        short_interest=f"{float(short_interest.current_value)*100:.1f}" if short_interest and short_interest.current_value else "N/A",
        sell_pct=f"{float(analyst.raw_data.get('sell_pct', 0))*100:.1f}" if analyst and analyst.raw_data else "N/A",
        insider_score=f"{float(insider.current_value):.1f}" if insider and insider.current_value else "N/A",
        job_velocity=f"{float(job_vel.current_value):.4f}" if job_vel and job_vel.current_value else "N/A",
        squeeze_score=f"{float(squeeze.current_value):.4f}" if squeeze and squeeze.current_value else "N/A",
        current_ev=float(dcf.current_ev) if dcf and dcf.current_ev else 0,
        implied_growth=f"{float(dcf.implied_year1_growth)*100:.1f}" if dcf and dcf.implied_year1_growth else "N/A",
        implied_margin=f"{float(dcf.implied_terminal_margin)*100:.1f}" if dcf and dcf.implied_terminal_margin else "N/A",
        primary_node=primary_node.node_id if primary_node else "N/A",
        primary_node_name=primary_node.node_name if primary_node else "N/A",
        primary_conviction=f"{float(primary_node.conviction_score):.2f}" if primary_node and primary_node.conviction_score else "N/A",
        validation_status=validation_result.get("validation_status", ""),
        confidence=validation_result.get("confidence", ""),
        primary_risk=validation_result.get("primary_risk", ""),
        rehabilitation_mechanism=validation_result.get("rehabilitation_mechanism", ""),
        rehabilitation_timeline=validation_result.get("rehabilitation_timeline", ""),
    )

    try:
        result = call_opus(prompt)
        thesis = parse_json_response(result)

        if not thesis or "narrative" not in thesis:
            logger.error("Invalid thesis response for %s", company.ticker)
            return None

        logger.info("Generated thesis for %s", company.ticker)
        return thesis

    except Exception as e:
        logger.error("Thesis generation failed for %s: %s", company.ticker, e)
        return None
