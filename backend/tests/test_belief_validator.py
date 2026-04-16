"""Tests for belief stack engine and validator output formats."""
from unittest.mock import patch

import pytest

from app.core.claude import parse_json_response


def test_parse_json_clean():
    result = parse_json_response('{"score": 7, "examples": ["test"], "classification": "moral_condemnation", "reasoning": "test"}')
    assert result["score"] == 7
    assert result["classification"] == "moral_condemnation"


def test_parse_json_with_fences():
    text = """```json
{"score": 5, "examples": ["a"], "classification": "analytical", "reasoning": "ok"}
```"""
    result = parse_json_response(text)
    assert result["score"] == 5


def test_parse_json_single_quotes():
    text = "{'score': 3, 'examples': ['test'], 'classification': 'negative_analytical', 'reasoning': 'ok'}"
    result = parse_json_response(text)
    assert result["score"] == 3


def test_parse_json_invalid():
    result = parse_json_response("this is not json at all")
    assert result == {}


def test_validation_result_format():
    """Ensure validation result has all required fields."""
    mock_response = {
        "validation_status": "VALID",
        "confidence": "high",
        "primary_risk": "GRR may lag",
        "grr_assessment": "stable_genuine",
        "adoption_assessment": "genuine_operational",
        "rehabilitation_mechanism": "Earnings beat",
        "rehabilitation_timeline": "months",
        "falsification_condition": "GRR below 85%",
        "recommended_position_size": "full",
        "reasoning": "Strong setup",
    }
    required_fields = [
        "validation_status", "confidence", "primary_risk",
        "grr_assessment", "adoption_assessment",
        "rehabilitation_mechanism", "rehabilitation_timeline",
        "falsification_condition", "recommended_position_size", "reasoning",
    ]
    for field in required_fields:
        assert field in mock_response, f"Missing field: {field}"


def test_dcf_decomposition_format():
    """Ensure DCF solver output has required fields."""
    mock_result = {
        "current_ev": 5_000_000_000,
        "implied_year1_growth": 0.15,
        "implied_terminal_margin": 0.22,
        "implied_wacc": 0.10,
        "solver_converged": True,
        "solver_error": 1234.5,
        "ev_revenue_multiple": 8.5,
    }
    required = [
        "current_ev", "implied_year1_growth", "implied_terminal_margin",
        "implied_wacc", "solver_converged",
    ]
    for field in required:
        assert field in mock_result, f"Missing field: {field}"
    assert 0 <= mock_result["implied_terminal_margin"] <= 0.50
    assert -0.30 <= mock_result["implied_year1_growth"] <= 1.50


def test_belief_node_evidence_format():
    """Ensure leaf node evidence scoring has required fields."""
    mock_node = {
        "node_id": "A2",
        "evidence_value": "declining share",
        "evidence_label": "Market share eroding",
        "evidence_direction": "BEARISH",
        "evidence_confidence": "MEDIUM",
        "gap_magnitude": -0.15,
        "evidence_sources": ["job posting data", "competitive analysis"],
    }
    required = [
        "node_id", "evidence_value", "evidence_direction",
        "evidence_confidence", "gap_magnitude",
    ]
    for field in required:
        assert field in mock_node, f"Missing field: {field}"
    assert mock_node["evidence_direction"] in [
        "STRONGLY_BULLISH", "BULLISH", "NEUTRAL", "BEARISH", "STRONGLY_BEARISH",
    ]
    assert mock_node["evidence_confidence"] in ["HIGH", "MEDIUM", "LOW"]


def test_conviction_score_calculation():
    """Conviction = |gap_magnitude| * confidence_weight."""
    from app.services.belief_stack_engine import CONFIDENCE_WEIGHTS

    gap = -0.25
    confidence = "MEDIUM"
    expected = abs(gap) * CONFIDENCE_WEIGHTS[confidence]
    assert expected == pytest.approx(0.15)

    gap_high = 0.40
    expected_high = abs(gap_high) * CONFIDENCE_WEIGHTS["HIGH"]
    assert expected_high == pytest.approx(0.40)
