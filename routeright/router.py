"""Core router logic - decides which model to use and tracks metrics."""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any

from routeright.config import RouterConfig
from routeright.decider import BaseDeciderClient, DeciderResult

logger = logging.getLogger("routeright.router")


@dataclass
class RoutingDecision:
    """Structured log entry for a single routing decision."""

    question: str
    choice: str                # "small" or "frontier"
    confidence: float
    decision_latency_ms: float
    model_used: str            # actual Bedrock model ID
    tokens_in: int = 0
    tokens_out: int = 0
    estimated_cost_usd: float = 0.0
    total_latency_ms: float = 0.0
    response_text: str = ""
    probabilities: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "question": self.question,
            "choice": self.choice,
            "confidence": self.confidence,
            "decision_latency_ms": self.decision_latency_ms,
            "model_used": self.model_used,
            "tokens_in": self.tokens_in,
            "tokens_out": self.tokens_out,
            "estimated_cost_usd": self.estimated_cost_usd,
            "total_latency_ms": self.total_latency_ms,
            "probabilities": self.probabilities,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict())


# ---------------------------------------------------------------------------
# Pricing config - loaded from file, NOT guessed
# ---------------------------------------------------------------------------

DEFAULT_PRICING = {
    "_note": "Prices per 1K tokens in USD. Fill in your actual prices.",
    "models": {}
}


def load_pricing(path: str = "config/pricing.json") -> dict[str, dict[str, float]]:
    """Load pricing from config file. Returns model_id -> {input, output} per 1K tokens."""
    try:
        with open(path) as f:
            data = json.load(f)
        return data.get("models", {})
    except FileNotFoundError:
        logger.warning("Pricing file %s not found - cost estimates will be zero", path)
        return {}


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

class RouteRightRouter:
    """Main router - uses Decider 2B to route requests to the right model."""

    def __init__(
        self,
        decider: BaseDeciderClient,
        config: RouterConfig | None = None,
        pricing_path: str = "config/pricing.json",
    ):
        self.config = config or RouterConfig()
        self.decider = decider
        self.pricing = load_pricing(pricing_path)
        self.history: list[RoutingDecision] = []

        logger.info(
            "RouteRightRouter initialized: threshold=%.2f frontier=%s small=%s",
            self.config.confidence_threshold,
            self.config.frontier_model_id,
            self.config.small_model_id,
        )

    def route(self, user_message: str) -> tuple[str, DeciderResult]:
        """Decide which model to use for this message.

        Returns (model_id, decider_result).
        Logic: use small model ONLY if choice is "small" AND confidence >= threshold.
        Otherwise always use frontier (safe default).
        """
        result = self.decider.decide(user_message)

        if result.choice == "small" and result.confidence >= self.config.confidence_threshold:
            model_id = self.config.small_model_id
        else:
            model_id = self.config.frontier_model_id

        logger.info(
            "Route decision: choice=%s conf=%.3f threshold=%.2f -> model=%s",
            result.choice, result.confidence, self.config.confidence_threshold,
            model_id.split("/")[-1] if "/" in model_id else model_id,
        )

        return model_id, result

    def estimate_cost(self, model_id: str, tokens_in: int, tokens_out: int) -> float:
        """Estimate cost in USD for a given model call."""
        model_pricing = self.pricing.get(model_id, {})
        input_cost = model_pricing.get("input_per_1k", 0.0) * (tokens_in / 1000)
        output_cost = model_pricing.get("output_per_1k", 0.0) * (tokens_out / 1000)
        return round(input_cost + output_cost, 6)

    def record_decision(
        self,
        user_message: str,
        model_id: str,
        decider_result: DeciderResult,
        tokens_in: int = 0,
        tokens_out: int = 0,
        total_latency_ms: float = 0.0,
        response_text: str = "",
    ) -> RoutingDecision:
        """Record a complete routing decision with all metrics."""
        cost = self.estimate_cost(model_id, tokens_in, tokens_out)

        decision = RoutingDecision(
            question=user_message,
            choice=decider_result.choice,
            confidence=decider_result.confidence,
            decision_latency_ms=decider_result.latency_ms,
            model_used=model_id,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            estimated_cost_usd=cost,
            total_latency_ms=total_latency_ms,
            response_text=response_text,
            probabilities=decider_result.probabilities,
        )

        self.history.append(decision)
        logger.info("Decision recorded: %s", decision.to_json())
        return decision

    def get_savings_summary(self) -> dict[str, Any]:
        """Calculate cumulative savings vs always-frontier."""
        if not self.history:
            return {"total_decisions": 0}

        total = len(self.history)
        routed_small = sum(1 for d in self.history if d.model_used == self.config.small_model_id)
        actual_cost = sum(d.estimated_cost_usd for d in self.history)

        # Hypothetical cost if all went to frontier
        frontier_cost = 0.0
        for d in self.history:
            frontier_cost += self.estimate_cost(
                self.config.frontier_model_id, d.tokens_in, d.tokens_out
            )

        cost_saved = frontier_cost - actual_cost
        pct_saved = (cost_saved / frontier_cost * 100) if frontier_cost > 0 else 0.0

        avg_decision_latency = sum(d.decision_latency_ms for d in self.history) / total

        return {
            "total_decisions": total,
            "routed_small": routed_small,
            "routed_frontier": total - routed_small,
            "percent_small": round(routed_small / total * 100, 1),
            "actual_cost_usd": round(actual_cost, 6),
            "frontier_only_cost_usd": round(frontier_cost, 6),
            "cost_saved_usd": round(cost_saved, 6),
            "percent_cost_saved": round(pct_saved, 1),
            "avg_decision_latency_ms": round(avg_decision_latency, 2),
        }
