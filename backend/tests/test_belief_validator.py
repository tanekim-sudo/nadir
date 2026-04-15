"""Tests for belief stack builder and validator output formats."""
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


def test_belief_stack_format():
    """Ensure belief stack response has all required layers."""
    mock_response = {
        "surface": {
            "assumption": "test", "market_implied_value": "test",
            "appears_correct": False, "confirming_signal": "test",
            "contradicting_signal": "test",
        },
        "financial": {
            "assumption": "test", "market_implied_value": "test",
            "appears_correct": True, "confirming_signal": "test",
            "contradicting_signal": "test",
        },
        "structural": {
            "assumption": "test", "market_implied_value": "test",
            "appears_correct": True, "confirming_signal": "test",
            "contradicting_signal": "test",
        },
        "axiom": {
            "assumption": "test", "market_implied_value": "test",
            "appears_correct": False, "confirming_signal": "test",
            "contradicting_signal": "test",
        },
        "weakest_node": "surface",
        "weakest_node_reasoning": "test",
        "variant_view_summary": "test",
    }

    for layer in ["surface", "financial", "structural", "axiom"]:
        assert layer in mock_response
        layer_data = mock_response[layer]
        for field in ["assumption", "market_implied_value", "appears_correct"]:
            assert field in layer_data, f"Missing {field} in {layer}"

    assert "weakest_node" in mock_response
    assert mock_response["weakest_node"] in ["surface", "financial", "structural", "axiom"]
