"""Strands agent wiring for RouteRight dynamic model router.

Provides drop-in integration into the Strands agent execution lifecycle via:
1. RouteRightPattern - high-level wrapper and hook provider
2. RouteRightInterventionHandler - Strands InterventionHandler implementation
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from routeright.config import RouterConfig
from routeright.decider import BaseDeciderClient, MockDeciderClient
from routeright.pattern.spec import ModelRoutingQuestion, ROUTING_OPTIONS
from routeright.router import RouteRightRouter

logger = logging.getLogger("routeright.pattern")


class RouteRightPattern:
    """Reusable wiring pattern to place RouteRight before an agent's LLM call.

    Can be registered with any Strands Agent:
        pattern = RouteRightPattern()
        pattern.attach(agent)
    """

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
                decider = MockDeciderClient(randomize=True)
            else:
                from routeright.decider import DeciderClient
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
    """Strands InterventionHandler implementation for model routing decisions.

    Follows the Strands intervention pattern:
    - Inspects incoming user state before model call
    - Executes Decider 2B typed question
    - Escalates low-confidence queries to frontier
    - Returns Proceed with decision metadata attached
    """

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
            return Proceed(
                metadata={
                    "routed_model": model_id,
                    "choice": decider_result.choice,
                    "confidence": decider_result.confidence,
                    "latency_ms": decider_result.latency_ms,
                }
            )

        return Proceed()
