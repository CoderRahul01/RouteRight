"""Tests for the reusable decision pattern (routeright.pattern)."""

import pytest

from routeright.pattern import (
    ModelRoutingQuestion,
    ROUTING_OPTIONS,
    DEFAULT_QUESTION_ID,
    RouteRightPattern,
    RouteRightInterventionHandler,
)
from routeright.config import RouterConfig
from routeright.decider import MockDeciderClient


def test_routing_options():
    assert "small" in ROUTING_OPTIONS
    assert "frontier" in ROUTING_OPTIONS
    assert len(ROUTING_OPTIONS) == 2


def test_question_spec_payload():
    spec = ModelRoutingQuestion()
    payload = spec.to_decider_payload("Calculate 2 + 2")
    assert payload["state"] == "Calculate 2 + 2"
    assert DEFAULT_QUESTION_ID in payload["questions"]
    q = payload["questions"][DEFAULT_QUESTION_ID]
    assert q["type"] == "choice"
    assert q["options"] == ["small", "frontier"]


def test_question_spec_evaluation():
    spec = ModelRoutingQuestion(default_confidence_threshold=0.7)
    # High confidence small
    assert spec.evaluate_decision("small", 0.85) == "small"
    # Low confidence small escalates to frontier
    assert spec.evaluate_decision("small", 0.65) == "frontier"
    # Frontier stays frontier
    assert spec.evaluate_decision("frontier", 0.95) == "frontier"
    assert spec.evaluate_decision("frontier", 0.40) == "frontier"


def test_pattern_routing():
    config = RouterConfig(
        frontier_model_id="frontier-model",
        small_model_id="small-model",
        confidence_threshold=0.7,
        mock_mode=True,
    )
    decider = MockDeciderClient(default_choice="small", default_confidence=0.85)
    pattern = RouteRightPattern(config=config, decider=decider)

    model_id, result = pattern.route_message("Simple query")
    assert model_id == "small-model"
    assert result.choice == "small"


def test_intervention_handler_fallback():
    class DummyEvent:
        class Agent:
            messages = [{"content": "Hello"}]
            model = "old-model"
        agent = Agent()

    handler = RouteRightInterventionHandler()
    event = DummyEvent()
    res = handler.before_model_call(event)
    assert res is not None
