import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

import window_boundary_guardrail


def test_guardrail_passes_with_no_activity():
    passed, message = window_boundary_guardrail.test_window_boundary_guardrail(
        trades=0,
        initial_capital=10000,
        final_value=10000,
        positions_at_start=0,
        positions_at_end=0,
    )

    assert passed is True
    assert "return = 0.00%" in message


def test_guardrail_fails_with_phantom_return():
    passed, message = window_boundary_guardrail.test_window_boundary_guardrail(
        trades=0,
        initial_capital=10000,
        final_value=10050,
        positions_at_start=0,
        positions_at_end=0,
    )

    assert passed is False
    assert "expected 0%" in message


def test_guardrail_allows_returns_with_positions():
    passed, message = window_boundary_guardrail.test_window_boundary_guardrail(
        trades=0,
        initial_capital=10000,
        final_value=9800,
        positions_at_start=1,
        positions_at_end=1,
    )

    assert passed is True
    assert "trades" in message


def test_window_behavior_explanation_mentions_guardrail_rule():
    explanation = window_boundary_guardrail.explain_window_behavior()

    assert "Guardrail Rule" in explanation
    assert "Return MUST be 0%" in explanation
