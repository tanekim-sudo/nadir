"""
Belief Stack Builder — generates the 4-layer belief dependency analysis
when a company reaches WATCH state (3+ conditions met).
Uses Claude Opus for high-quality analysis.
"""
import logging
from typing import Dict, Optional

from sqlalchemy.orm import Session

from app.core.claude import call_opus, parse_json_response
from app.models.belief_stack import BeliefStack
from app.models.company import Company
from app.models.enums import BeliefLayer, NetDirection
from app.models.nadir_signal import NadirSignal

logger = logging.getLogger(__name__)

BELIEF_STACK_PROMPT = """Build a belief stack dependency analysis for {ticker} ({company_name}).

Current data:
- Stock price: ${price}
- EV/NTM Revenue multiple: {multiple}x
- Consensus NRR estimate: {nrr}%
- Consensus revenue growth: {growth}%
- Short interest: {short_interest}%
- Analyst sell ratings: {sell_pct}%

A belief stack has 4 layers:
- SURFACE: What analysts and media are saying (updates daily)
- FINANCIAL: The revenue/margin/multiple assumptions (updates quarterly)
- STRUCTURAL: Industry durability, moat, competitive position (updates yearly)
- AXIOM: Hidden assumptions treated as permanent truths (updates rarely)

For each layer, identify:
1. The specific assumption embedded in the current stock price
2. Whether this assumption appears correct or suspect
3. What observable signal would confirm or contradict it

Also identify: what is the WEAKEST NODE in the dependency tree? What single assumption, if wrong, most completely breaks the bull case?

Return ONLY valid JSON in this exact format:
{{"surface": {{"assumption": "<text>", "market_implied_value": "<text>", "appears_correct": false, "confirming_signal": "<text>", "contradicting_signal": "<text>"}}, "financial": {{"assumption": "<text>", "market_implied_value": "<text>", "appears_correct": false, "confirming_signal": "<text>", "contradicting_signal": "<text>"}}, "structural": {{"assumption": "<text>", "market_implied_value": "<text>", "appears_correct": false, "confirming_signal": "<text>", "contradicting_signal": "<text>"}}, "axiom": {{"assumption": "<text>", "market_implied_value": "<text>", "appears_correct": false, "confirming_signal": "<text>", "contradicting_signal": "<text>"}}, "weakest_node": "<surface|financial|structural|axiom>", "weakest_node_reasoning": "<text>", "variant_view_summary": "<two sentence summary of where market is wrong>"}}"""


def build_belief_stack(db: Session, company: Company) -> Optional[Dict]:
    """Build or refresh the belief stack for a company."""
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
    grr = signal_map.get("GRR_STABILITY")

    price = float(company.current_price) if company.current_price else 0
    nrr = float(company.market_implied_nrr or 0) * 100
    growth = float(company.market_implied_growth or 0) * 100
    multiple = float(company.current_ev or 0) / max(price * 1e6, 1) if price else 0

    prompt = BELIEF_STACK_PROMPT.format(
        ticker=company.ticker,
        company_name=company.name,
        price=f"{price:.2f}",
        multiple=f"{multiple:.1f}",
        nrr=f"{nrr:.1f}",
        growth=f"{growth:.1f}",
        short_interest=f"{float(short_interest.current_value) * 100:.1f}" if short_interest and short_interest.current_value else "N/A",
        sell_pct=f"{float(analyst.raw_data.get('sell_pct', 0)) * 100:.1f}" if analyst and analyst.raw_data else "N/A",
    )

    try:
        result = call_opus(prompt)
        parsed = parse_json_response(result)

        if not parsed or "surface" not in parsed:
            logger.error("Invalid belief stack response for %s", company.ticker)
            return None

        # Delete existing belief stack layers for this company
        db.query(BeliefStack).filter(BeliefStack.company_id == company.id).delete()

        layers = {}
        for layer_name in ["surface", "financial", "structural", "axiom"]:
            layer_data = parsed.get(layer_name, {})
            appears_correct = layer_data.get("appears_correct", False)

            if layer_name == parsed.get("weakest_node"):
                direction = NetDirection.STRONGLY_CONTRADICTING.value
            elif not appears_correct:
                direction = NetDirection.CONTRADICTING.value
            else:
                direction = NetDirection.CONFIRMING.value

            belief = BeliefStack(
                company_id=company.id,
                layer=layer_name.upper(),
                assumption_text=layer_data.get("assumption", ""),
                market_implied_value=layer_data.get("market_implied_value", ""),
                variant_value=parsed.get("variant_view_summary", ""),
                confirming_signals=1 if appears_correct else 0,
                contradicting_signals=0 if appears_correct else 1,
                net_direction=direction,
            )
            db.add(belief)
            layers[layer_name] = belief

        db.commit()
        logger.info("Built belief stack for %s (weakest: %s)", company.ticker, parsed.get("weakest_node"))
        return parsed

    except Exception as e:
        logger.error("Belief stack build failed for %s: %s", company.ticker, e)
        db.rollback()
        return None
