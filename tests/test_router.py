"""Tests for RouteRight router logic using mock mode."""

import pytest

from routeright.config import RouterConfig
from routeright.decider import DeciderResult
from tests.fakes.decider import MockDeciderClient
from routeright.router import RouteRightRouter


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def config():
    return RouterConfig(
        frontier_model_id="frontier-model",
        small_model_id="small-model",
        confidence_threshold=0.7,
        mock_mode=True,
    )


@pytest.fixture
def mock_decider():
    return MockDeciderClient(default_choice="small", default_confidence=0.85)


@pytest.fixture
def router(mock_decider, config):
    return RouteRightRouter(
        decider=mock_decider,
        config=config,
        pricing_path="config/pricing.json",
    )


# ---------------------------------------------------------------------------
# Decider tests
# ---------------------------------------------------------------------------

class TestMockDecider:
    def test_returns_default_choice(self):
        client = MockDeciderClient(default_choice="small", default_confidence=0.9)
        result = client.decide("What is 2 + 2?")
        assert result.choice == "small"
        assert result.confidence == 0.9

    def test_returns_frontier(self):
        client = MockDeciderClient(default_choice="frontier", default_confidence=0.8)
        result = client.decide("Debug this complex async code")
        assert result.choice == "frontier"

    def test_has_latency(self):
        client = MockDeciderClient()
        result = client.decide("test")
        assert result.latency_ms > 0

    def test_has_probabilities(self):
        client = MockDeciderClient(default_choice="small")
        result = client.decide("test")
        assert "small" in result.probabilities
        assert "frontier" in result.probabilities
        assert abs(sum(result.probabilities.values()) - 1.0) < 0.01

    def test_randomize_mode(self):
        client = MockDeciderClient(randomize=True, seed=42)
        choices = set()
        for i in range(20):
            result = client.decide(f"message {i}" * (i + 1))
            choices.add(result.choice)
        # With randomization, we should get both choices
        assert len(choices) == 2


# ---------------------------------------------------------------------------
# Router tests
# ---------------------------------------------------------------------------

class TestRouter:
    def test_routes_to_small_when_confident(self, config):
        decider = MockDeciderClient(default_choice="small", default_confidence=0.85)
        router = RouteRightRouter(decider=decider, config=config)

        model_id, result = router.route("What is the capital of France?")
        assert model_id == "small-model"
        assert result.choice == "small"

    def test_routes_to_frontier_when_low_confidence(self, config):
        decider = MockDeciderClient(default_choice="small", default_confidence=0.5)
        router = RouteRightRouter(decider=decider, config=config)

        model_id, result = router.route("Explain quantum computing")
        assert model_id == "frontier-model"

    def test_routes_to_frontier_when_choice_is_frontier(self, config):
        decider = MockDeciderClient(default_choice="frontier", default_confidence=0.95)
        router = RouteRightRouter(decider=decider, config=config)

        model_id, result = router.route("Debug this multi-threaded race condition")
        assert model_id == "frontier-model"

    def test_threshold_boundary_below(self, config):
        """Confidence exactly below threshold should route to frontier."""
        decider = MockDeciderClient(default_choice="small", default_confidence=0.69)
        router = RouteRightRouter(decider=decider, config=config)

        model_id, _ = router.route("test")
        assert model_id == "frontier-model"

    def test_threshold_boundary_at(self, config):
        """Confidence exactly at threshold should route to small."""
        decider = MockDeciderClient(default_choice="small", default_confidence=0.7)
        router = RouteRightRouter(decider=decider, config=config)

        model_id, _ = router.route("test")
        assert model_id == "small-model"

    def test_configurable_threshold(self):
        config = RouterConfig(
            frontier_model_id="frontier",
            small_model_id="small",
            confidence_threshold=0.9,
        )
        decider = MockDeciderClient(default_choice="small", default_confidence=0.85)
        router = RouteRightRouter(decider=decider, config=config)

        model_id, _ = router.route("test")
        assert model_id == "frontier"  # 0.85 < 0.9 threshold


# ---------------------------------------------------------------------------
# Decision recording tests
# ---------------------------------------------------------------------------

class TestDecisionRecording:
    def test_records_decision(self, router):
        model_id, result = router.route("test question")
        decision = router.record_decision(
            user_message="test question",
            model_id=model_id,
            decider_result=result,
            tokens_in=50,
            tokens_out=100,
            total_latency_ms=500.0,
        )

        assert decision.question == "test question"
        assert decision.tokens_in == 50
        assert decision.tokens_out == 100
        assert len(router.history) == 1

    def test_to_dict(self, router):
        model_id, result = router.route("test")
        decision = router.record_decision(
            user_message="test",
            model_id=model_id,
            decider_result=result,
        )
        d = decision.to_dict()
        assert "question" in d
        assert "choice" in d
        assert "confidence" in d
        assert "decision_latency_ms" in d

    def test_to_json(self, router):
        model_id, result = router.route("test")
        decision = router.record_decision(
            user_message="test",
            model_id=model_id,
            decider_result=result,
        )
        import json
        parsed = json.loads(decision.to_json())
        assert parsed["question"] == "test"


# ---------------------------------------------------------------------------
# Savings summary tests
# ---------------------------------------------------------------------------

class TestSavingsSummary:
    def test_empty_history(self, router):
        summary = router.get_savings_summary()
        assert summary["total_decisions"] == 0

    def test_savings_calculation(self, config):
        decider = MockDeciderClient(default_choice="small", default_confidence=0.9)
        router = RouteRightRouter(decider=decider, config=config)

        # Record a few decisions
        for _ in range(5):
            model_id, result = router.route("simple question")
            router.record_decision(
                user_message="simple question",
                model_id=model_id,
                decider_result=result,
                tokens_in=50,
                tokens_out=100,
            )

        summary = router.get_savings_summary()
        assert summary["total_decisions"] == 5
        assert summary["routed_small"] == 5
        assert summary["percent_small"] == 100.0


# ---------------------------------------------------------------------------
# Real Decider Client tests
# ---------------------------------------------------------------------------

class TestRealDeciderClient:
    def test_health_check_unreachable(self):
        from routeright.decider import DeciderClient
        client = DeciderClient(server_url="http://127.0.0.1:9999")
        health = client.check_health()
        assert health["status"] == "unreachable"
        assert health["connected"] is False
        assert "instructions" in health
        assert "strands-decider serve" in health["instructions"]

    def test_unreachable_raises_descriptive_error(self):
        from routeright.decider import DeciderClient
        client = DeciderClient(
            server_url="http://127.0.0.1:9999",
            model_id="non-existent-model-id-xyz",
        )
        with pytest.raises(ConnectionError) as exc_info:
            client.decide("Hello world")
        assert "strands-decider serve" in str(exc_info.value)
