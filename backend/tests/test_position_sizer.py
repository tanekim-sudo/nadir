"""Tests for Kelly-based position sizing."""
from app.services.position_sizer import calculate_position_size


def test_valid_high_confidence_full():
    result = calculate_position_size(
        validation_result={
            "validation_status": "VALID",
            "confidence": "high",
            "adoption_assessment": "genuine_operational",
            "recommended_position_size": "full",
        },
        portfolio_value=100000,
        open_positions=[],
    )
    assert result is not None
    assert not result["skip"]
    assert result["p_win"] == 0.72
    assert 0 < result["position_pct"] <= 0.20
    assert result["dollar_amount"] > 0
    assert result["kelly_fraction"] > 0.05


def test_valid_low_confidence_uncertain():
    result = calculate_position_size(
        validation_result={
            "validation_status": "VALID",
            "confidence": "low",
            "adoption_assessment": "genuine_operational",
            "recommended_position_size": "half",
        },
        portfolio_value=100000,
        open_positions=[],
    )
    assert result is not None
    assert result["p_win"] == 0.56


def test_skip_when_recommended():
    result = calculate_position_size(
        validation_result={
            "validation_status": "VALID",
            "confidence": "high",
            "adoption_assessment": "genuine_operational",
            "recommended_position_size": "skip",
        },
        portfolio_value=100000,
        open_positions=[],
    )
    assert result is not None
    assert result["skip"]
    assert result["position_pct"] == 0


def test_concentration_limit():
    result = calculate_position_size(
        validation_result={
            "validation_status": "VALID",
            "confidence": "high",
            "adoption_assessment": "genuine_operational",
            "recommended_position_size": "full",
        },
        portfolio_value=100000,
        open_positions=[
            {"position_pct": 0.20},
            {"position_pct": 0.20},
            {"position_pct": 0.20},
            {"position_pct": 0.15},
        ],
    )
    assert result is not None
    total = 0.75 + result["position_pct"]
    assert total <= 1.01


def test_insufficient_data_low_p():
    result = calculate_position_size(
        validation_result={
            "validation_status": "INSUFFICIENT_DATA",
            "confidence": "medium",
            "adoption_assessment": "uncertain",
            "recommended_position_size": "quarter",
        },
        portfolio_value=100000,
        open_positions=[],
    )
    assert result is not None
    assert result["p_win"] == 0.48


def test_unknown_key_fallback():
    result = calculate_position_size(
        validation_result={
            "validation_status": "UNKNOWN",
            "confidence": "unknown",
            "adoption_assessment": "unknown",
            "recommended_position_size": "half",
        },
        portfolio_value=100000,
        open_positions=[],
    )
    # p_win=0.45 => kelly might be below min edge
    # Either returns None or small position
    if result is not None:
        assert result["p_win"] == 0.45


def test_half_kelly_applied():
    result = calculate_position_size(
        validation_result={
            "validation_status": "VALID",
            "confidence": "high",
            "adoption_assessment": "genuine_operational",
            "recommended_position_size": "full",
        },
        portfolio_value=100000,
        open_positions=[],
    )
    assert result is not None
    assert result["half_kelly"] == result["kelly_fraction"] * 0.5 or abs(
        result["half_kelly"] - result["kelly_fraction"] * 0.5
    ) < 0.001
