"""Strands agent wiring for RouteRight dynamic model router.

Provides drop-in integration into the Strands agent execution lifecycle via:
1. DeciderRoutingStrategy: Strands RoutingStrategy implementation used with strands.models.ModelRouter.
2. RouteRightPattern: high-level wrapper and hook provider for existing agents.
3. RouteRightInterventionHandler: Strands InterventionHandler implementation.
"""

from __future__ import annotations

import logging
from typing import Any, Optional, Sequence

from strands.models import FallbackStrategy, ModelRouter, RoutingCandidate, RoutingContext, RoutingStrategy

from routeright.config import RouterConfig
from routeright.decider import BaseDeciderClient, DeciderClient
from routeright.pattern.spec import ModelRoutingQuestion, ROUTING_OPTIONS
from routeright.router import RouteRightRouter

logger = logging.getLogger("routeright.pattern")


# ---------------------------------------------------------------------------
# DeciderRoutingStrategy (Strands RoutingStrategy)
# ---------------------------------------------------------------------------

class DeciderRoutingStrategy(RoutingStrategy):
    """Strands RoutingStrategy driven by Strands Decider 2B.

    Evaluates prompt complexity before model invocation. Returns the small
    model candidate only if Decider 2B classifies the query as 'small' with
    confidence >= confidence_threshold. Otherwise returns the frontier model candidate.

    Guarantees:
    - Must return one of the context's own RoutingCandidate instances.
    - After a failure (context.attempts non-empty), delegates to FallbackStrategy.
    - Only ASCII hyphens (-) used in code comments and logs.
    """

    def __init__(
        self,
        decider: BaseDeciderClient | None = None,
        confidence_threshold: float = 0.70,
        fallback_strategy: RoutingStrategy | None = None,
    ):
        self.decider = decider or DeciderClient()
        self.confidence_threshold = confidence_threshold
        self.fallback_strategy = fallback_strategy or FallbackStrategy()

    async def select(self, context: RoutingContext, **kwargs: Any) -> RoutingCandidate | None:
        """Select one of context.candidates based on Decider 2B complexity evaluation."""
        # After any failure (context.attempts non-empty), delegate to FallbackStrategy
        if context.attempts:
            logger.info("Previous attempt failed; delegating to FallbackStrategy.")
            return await self.fallback_strategy.select(context, **kwargs)

        if not context.candidates:
            return None

        # Identify candidate tiers from context's own candidate instances
        small_candidate: RoutingCandidate | None = None
        frontier_candidate: RoutingCandidate | None = None

        for candidate in context.candidates:
            tier_name = ""
            if candidate.metadata and "tier" in candidate.metadata:
                tier_name = str(candidate.metadata["tier"]).lower()
            elif candidate.name:
                tier_name = candidate.name.lower()

            if any(k in tier_name for k in ("small", "haiku", "nova", "micro", "lite")):
                small_candidate = candidate
            elif any(k in tier_name for k in ("frontier", "sonnet", "opus", "pro")):
                frontier_candidate = candidate

        # Fallback candidate assignment if tags are not explicit
        if frontier_candidate is None:
            frontier_candidate = context.candidates[0]
        if small_candidate is None and len(context.candidates) > 1:
            small_candidate = context.candidates[1]

        # Extract prompt text from context.messages
        prompt = ""
        if context.messages:
            last_msg = context.messages[-1]
            content = last_msg.get("content", "") if isinstance(last_msg, dict) else getattr(last_msg, "content", "")
            if isinstance(content, str):
                prompt = content
            elif isinstance(content, list):
                parts = []
                for b in content:
                    if isinstance(b, dict) and "text" in b:
                        parts.append(b["text"])
                    elif isinstance(b, str):
                        parts.append(b)
                    elif hasattr(b, "text"):
                        parts.append(b.text)
                prompt = " ".join(parts)
            else:
                prompt = str(content)

        if not prompt:
            return frontier_candidate

        # Ask Decider 2B for complexity routing
        try:
            decider_res = self.decider.decide(prompt)
            # Policy: use small model only if choice is small and confidence >= threshold
            if (
                decider_res.choice == "small"
                and decider_res.confidence >= self.confidence_threshold
                and small_candidate is not None
            ):
                logger.info(
                    "Decider routed to small model (conf=%.2f >= %.2f)",
                    decider_res.confidence, self.confidence_threshold,
                )
                return small_candidate
        except Exception as exc:
            logger.warning("Decider routing failed (%s); escalating to frontier candidate.", exc)

        logger.info("Routing to frontier candidate.")
        return frontier_candidate


# ---------------------------------------------------------------------------
# Factory Helper for ModelRouter
# ---------------------------------------------------------------------------

def create_decider_router(
    frontier_model: Any | None = None,
    small_model: Any | None = None,
    decider: BaseDeciderClient | None = None,
    confidence_threshold: float = 0.70,
    config: RouterConfig | None = None,
) -> ModelRouter:
    """Create a strands.models.ModelRouter powered by DeciderRoutingStrategy."""
    from strands.models import BedrockModel

    cfg = config or RouterConfig()
    threshold = confidence_threshold or cfg.confidence_threshold

    if decider is None:
        if cfg.mock_mode:
            from tests.fakes.decider import MockDeciderClient
            decider = MockDeciderClient(randomize=True)
        else:
            decider = DeciderClient(
                model_id=cfg.decider_model_id,
                device=cfg.decider_device,
                server_url=cfg.decider_url,
            )

    if frontier_model is None:
        frontier_model = BedrockModel(model_id=cfg.frontier_model_id, region_name=cfg.aws_region)
    if small_model is None:
        small_model = BedrockModel(model_id=cfg.small_model_id, region_name=cfg.aws_region)

    candidate_frontier = RoutingCandidate(
        model=frontier_model,
        name="frontier",
        description="Frontier model for complex reasoning and architecture",
        metadata={"tier": "frontier"},
    )
    candidate_small = RoutingCandidate(
        model=small_model,
        name="small",
        description="Small efficient model for facts and formatting",
        metadata={"tier": "small"},
    )

    strategy = DeciderRoutingStrategy(decider=decider, confidence_threshold=threshold)
    return ModelRouter(models=[candidate_frontier, candidate_small], strategy=strategy)


# ---------------------------------------------------------------------------
# Existing Pattern Wrapper & InterventionHandler
# ---------------------------------------------------------------------------

class RouteRightPattern:
    """Reusable wiring pattern to place RouteRight before an agent's LLM call."""

    def __init__(
        self,
        config: Optional[RouterConfig] = None,
        decider: Optional[BaseDeciderClient] = None,
        question_spec: Optional[ModelRoutingQuestion] = None,
    ):
        self.config = config or RouterConfig()
        self.spec = question_spec or ModelRoutingQuestion(
            default_confidence_threshold=self.config.confidence_threshold
        )

        if decider is None:
            if self.config.mock_mode:
                from tests.fakes.decider import MockDeciderClient
                decider = MockDeciderClient(randomize=True)
            else:
                decider = DeciderClient(
                    model_id=self.config.decider_model_id,
                    device=self.config.decider_device,
                    server_url=self.config.decider_url,
                )

        self.router = RouteRightRouter(decider=decider, config=self.config)
        self._model_cache: dict[str, Any] = {}

    def get_bedrock_model(self, model_id: str) -> Any:
        """Resolve or cache a Strands BedrockModel instance."""
        if model_id not in self._model_cache:
            try:
                from strands.models import BedrockModel
                self._model_cache[model_id] = BedrockModel(
                    model_id=model_id,
                    region_name=self.config.aws_region,
                )
            except ImportError:
                logger.warning("strands-agents not installed; skipping BedrockModel creation")
                return None
        return self._model_cache[model_id]

    def route_message(self, user_message: str) -> tuple[str, Any]:
        """Route user message and return target model ID and decider metadata."""
        return self.router.route(user_message)

    def attach(self, agent: Any) -> None:
        """Attach RouteRight hook to a Strands agent."""
        from routeright.hook import RouteRightHook
        hook = RouteRightHook(decider=self.router.decider, config=self.config)
        if hasattr(agent, "hooks") and hasattr(agent.hooks, "register"):
            agent.hooks.register(hook)
            logger.info("RouteRight pattern attached to agent hooks")
        elif hasattr(agent, "add_hook"):
            agent.add_hook(hook)
            logger.info("RouteRight pattern added via add_hook")
        else:
            logger.info("Agent does not expose hooks; manual routing mode available")


class RouteRightInterventionHandler:
    """Strands InterventionHandler implementation for model routing decisions."""

    name = "routeright-model-routing"

    def __init__(self, pattern: Optional[RouteRightPattern] = None):
        self.pattern = pattern or RouteRightPattern()

    def before_model_call(self, event: Any) -> Any:
        """Invoked before the agent calls the model."""
        try:
            from strands.interventions import Proceed
        except ImportError:
            Proceed = lambda **kwargs: kwargs

        # Extract message content
        messages = getattr(getattr(event, "agent", None), "messages", [])
        text = ""
        if messages:
            last = messages[-1]
            if isinstance(last, dict):
                text = last.get("content", "")
            elif isinstance(last, str):
                text = last

        if text:
            model_id, decider_result = self.pattern.route_message(text)
            new_model = self.pattern.get_bedrock_model(model_id)
            if new_model and hasattr(event, "agent"):
                event.agent.model = new_model
            reason = (
                f"RouteRight routed to {model_id} (choice={decider_result.choice}, "
                f"conf={decider_result.confidence:.2f}, lat={decider_result.latency_ms:.1f}ms)"
            )
            return Proceed(reason=reason)

        return Proceed()
