"""
Position Sizer — calculates optimal position size using half-Kelly criterion.
"""
import logging
import math
from decimal import Decimal
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

BASE_RATES = {
    ("VALID", "high", "genuine_operational"): 0.72,
    ("VALID", "high", "uncertain"): 0.61,
    ("VALID", "medium", "genuine_operational"): 0.63,
    ("VALID", "medium", "uncertain"): 0.54,
    ("VALID", "low", "genuine_operational"): 0.56,
    ("INSUFFICIENT_DATA", "medium", "uncertain"): 0.48,
}

B_WIN = 0.55   # Expected 55% gain when thesis correct
B_LOSE = 0.20  # Expected 20% additional loss when thesis wrong

SIZE_MODIFIERS = {
    "full": 1.0,
    "half": 0.5,
    "quarter": 0.25,
    "skip": 0.0,
}


def calculate_position_size(
    validation_result: Dict[str, Any],
    portfolio_value: float,
    open_positions: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """
    Calculate optimal position size using half-Kelly criterion.
    Returns None if position should be skipped.
    """
    key = (
        validation_result.get("validation_status", ""),
        validation_result.get("confidence", ""),
        validation_result.get("adoption_assessment", ""),
    )
    p_win = BASE_RATES.get(key, 0.45)

    b = B_WIN / B_LOSE  # payoff ratio

    # Kelly criterion
    q = 1 - p_win
    kelly = (b * p_win - q) / b
    half_kelly = kelly * 0.5

    # Minimum edge threshold
    if kelly < 0.05:
        logger.info("Kelly fraction %.4f below minimum edge threshold, skipping", kelly)
        return None

    # Concentration limit: max 20% per position
    position_pct = min(max(half_kelly, 0), 0.20)

    # Portfolio concentration check
    current_exposure = sum(p.get("position_pct", 0) for p in open_positions)
    if current_exposure > 0.80:
        position_pct = min(position_pct, 1.0 - current_exposure)

    # Apply recommended size modifier from validation
    modifier = SIZE_MODIFIERS.get(
        validation_result.get("recommended_position_size", "half"), 0.5
    )
    position_pct *= modifier

    dollar_amount = portfolio_value * position_pct

    if position_pct == 0:
        return {
            "position_pct": 0,
            "dollar_amount": 0,
            "p_win": p_win,
            "kelly_fraction": round(kelly, 4),
            "half_kelly": round(half_kelly, 4),
            "b_ratio": b,
            "skip": True,
        }

    return {
        "position_pct": round(position_pct, 4),
        "dollar_amount": round(dollar_amount, 2),
        "p_win": p_win,
        "kelly_fraction": round(kelly, 4),
        "half_kelly": round(half_kelly, 4),
        "b_ratio": b,
        "skip": False,
    }
