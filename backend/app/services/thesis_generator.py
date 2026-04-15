"""
Thesis Generator — generates formatted investment thesis when NADIR_COMPLETE is validated.
Uses Claude Opus for high-quality thesis generation.
"""
import logging
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.core.claude import call_opus, parse_json_response
from app.models.belief_stack import BeliefStack
from app.models.company import Company
from app.models.nadir_signal import NadirSignal

logger = logging.getLogger(__name__)

THESIS_PROMPT = """Generate a complete investment thesis for {ticker} ({company_name}).

This company has triggered all 5 NADIR conditions:
- Short interest: {short_interest}% (extreme bearish positioning)
- Analyst sell ratings: {sell_pct}% (consensus abandonment)
- Insider buying score: {insider_score} (management conviction)
- GRR: {grr}% (operational stability)
- Moral language score: {moral_score}/10 (narrative at peak condemnation)

Validation result: {validation_status} (confidence: {confidence})
Primary risk: {primary_risk}
Rehabilitation mechanism: {rehabilitation_mechanism}
Rehabilitation timeline: {rehabilitation_timeline}

Belief stack weakest node: {weakest_node}

Generate a thesis covering:
1. What the market consensus currently believes (the narrative)
2. What the operational signals actually show (the reality)
3. The specific disconnect between narrative and reality
4. The mechanism by which narrative corrects
5. The timeline for correction
6. What would prove the thesis wrong (falsification)
7. Key risks and monitoring signals

Return ONLY valid JSON in this exact format:
{{"narrative": "<what market believes>", "reality": "<what signals show>", "disconnect": "<why narrative has overshot reality>", "rehabilitation_mechanism": "<specific event causing correction>", "rehabilitation_timeline": "<expected timeframe>", "falsification_condition": "<observable outcome proving thesis wrong>", "time_horizon": "<maximum holding period>", "variant_view_summary": "<one paragraph precise variant view>", "key_risks": ["<risk 1>", "<risk 2>", "<risk 3>"], "monitoring_signals": ["<signal 1>", "<signal 2>", "<signal 3>"]}}"""


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
    grr_sig = signal_map.get("GRR_STABILITY")
    moral = signal_map.get("MORAL_LANGUAGE")

    beliefs = db.query(BeliefStack).filter(BeliefStack.company_id == company.id).all()
    weakest = "unknown"
    for b in beliefs:
        if b.net_direction == "STRONGLY_CONTRADICTING":
            weakest = b.layer
            break

    prompt = THESIS_PROMPT.format(
        ticker=company.ticker,
        company_name=company.name,
        short_interest=f"{float(short_interest.current_value)*100:.1f}" if short_interest and short_interest.current_value else "N/A",
        sell_pct=f"{float(analyst.raw_data.get('sell_pct', 0))*100:.1f}" if analyst and analyst.raw_data else "N/A",
        insider_score=f"{float(insider.current_value):.1f}" if insider and insider.current_value else "N/A",
        grr=f"{float(grr_sig.current_value)*100:.1f}" if grr_sig and grr_sig.current_value else "N/A",
        moral_score=f"{float(moral.current_value):.1f}" if moral and moral.current_value else "N/A",
        validation_status=validation_result.get("validation_status", ""),
        confidence=validation_result.get("confidence", ""),
        primary_risk=validation_result.get("primary_risk", ""),
        rehabilitation_mechanism=validation_result.get("rehabilitation_mechanism", ""),
        rehabilitation_timeline=validation_result.get("rehabilitation_timeline", ""),
        weakest_node=weakest,
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
