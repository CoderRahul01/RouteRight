"""Tests for the reusable decision pattern (routeright.pattern)."""

import pytest
from strands.models import BedrockModel, FallbackStrategy, ModelRouter, RoutingAttempt, RoutingCandidate, RoutingContext

from routeright.config import RouterConfig
from routeright.pattern import (
    DEFAULT_INSTRUCTIONS,
    DEFAULT_QUESTION_ID,
    ROUTING_OPTIONS,
    DeciderRoutingStrategy,
    ModelRoutingQuestion,
    RouteRightInterventionHandler,
    RouteRightPattern,
    create_decider_router,
)
from tests.fakes.decider import MockDeciderClient


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


@pytest.mark.asyncio
async def test_decider_routing_strategy_small():
    """Test that DeciderRoutingStrategy selects the small candidate when confidence >= threshold."""
    b_frontier = BedrockModel(model_id="frontier-id", region_name="us-east-1")
    b_small = BedrockModel(model_id="small-id", region_name="us-east-1")

    cand_frontier = RoutingCandidate(model=b_frontier, name="frontier", metadata={"tier": "frontier"})
    cand_small = RoutingCandidate(model=b_small, name="small", metadata={"tier": "small"})

    decider = MockDeciderClient(default_choice="small", default_confidence=0.85)
    strategy = DeciderRoutingStrategy(decider=decider, confidence_threshold=0.70)

    ctx = RoutingContext(
        messages=[{"role": "user", "content": "What is the capital of France?"}],
        system_prompt=None,
        tool_specs=None,
        candidates=[cand_frontier, cand_small],
        invocation_state={},
    )

    selected = await strategy.select(ctx)
    assert selected is cand_small
    assert selected in ctx.candidates


@pytest.mark.asyncio
async def test_decider_routing_strategy_escalates_on_low_confidence():
    """Test that low confidence small decision safely escalates to frontier candidate."""
    b_frontier = BedrockModel(model_id="frontier-id", region_name="us-east-1")
    b_small = BedrockModel(model_id="small-id", region_name="us-east-1")

    cand_frontier = RoutingCandidate(model=b_frontier, name="frontier", metadata={"tier": "frontier"})
    cand_small = RoutingCandidate(model=b_small, name="small", metadata={"tier": "small"})

    # Confidence 0.62 is below threshold 0.70
    decider = MockDeciderClient(default_choice="small", default_confidence=0.62)
    strategy = DeciderRoutingStrategy(decider=decider, confidence_threshold=0.70)

    ctx = RoutingContext(
        messages=[{"role": "user", "content": "Borderline query"}],
        system_prompt=None,
        tool_specs=None,
        candidates=[cand_frontier, cand_small],
        invocation_state={},
    )

    selected = await strategy.select(ctx)
    assert selected is cand_frontier
    assert selected in ctx.candidates


@pytest.mark.asyncio
async def test_decider_routing_strategy_delegates_to_fallback_on_failure():
    """Test that if context.attempts is non-empty, strategy delegates to FallbackStrategy."""
    b_frontier = BedrockModel(model_id="frontier-id", region_name="us-east-1")
    b_small = BedrockModel(model_id="small-id", region_name="us-east-1")

    cand_frontier = RoutingCandidate(model=b_frontier, name="frontier", metadata={"tier": "frontier"})
    cand_small = RoutingCandidate(model=b_small, name="small", metadata={"tier": "small"})

    decider = MockDeciderClient(default_choice="small", default_confidence=0.90)
    strategy = DeciderRoutingStrategy(decider=decider, confidence_threshold=0.70)

    # An attempt failed on cand_small
    failed_attempt = RoutingAttempt(candidate=cand_small, exception=RuntimeError("Bedrock timeout"))
    ctx = RoutingContext(
        messages=[{"role": "user", "content": "Query"}],
        system_prompt=None,
        tool_specs=None,
        candidates=[cand_frontier, cand_small],
        invocation_state={},
        attempts=[failed_attempt],
    )

    # Must delegate to fallback, which excludes cand_small and picks cand_frontier
    selected = await strategy.select(ctx)
    assert selected is cand_frontier


def test_create_decider_router():
    """Test create_decider_router factory creates a valid ModelRouter."""
    config = RouterConfig(mock_mode=True)
    router = create_decider_router(config=config)
    assert isinstance(router, ModelRouter)
    assert len(router._candidates) == 2
    assert router._candidates[0].name == "frontier"
    assert router._candidates[1].name == "small"
