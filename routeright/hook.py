"""Strands SDK integration - HookProvider that swaps models before each LLM call.

This is the drop-in integration point for any Strands agent.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from routeright.config import RouterConfig
from routeright.decider import BaseDeciderClient, MockDeciderClient
from routeright.router import RouteRightRouter

logger = logging.getLogger("routeright.hook")


class RouteRightHook:
    """Strands HookProvider that routes each model call through Decider 2B.

    Usage with Strands SDK:
        from strands import Agent
        from routeright import RouteRightHook

        hook = RouteRightHook()
        agent = Agent(model="default-model")
        agent.hooks.register(hook)
        agent("Your question here")

    The hook intercepts BeforeModelInvocationEvent and swaps the agent's
    model to either the frontier or small model based on Decider 2B's decision.
    """

    def __init__(
        self,
        decider: BaseDeciderClient | None = None,
        config: RouterConfig | None = None,
        pricing_path: str = "config/pricing.json",
    ):
        self.config = config or RouterConfig()

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

        self.router = RouteRightRouter(
            decider=decider,
            config=self.config,
            pricing_path=pricing_path,
        )

        # Cache BedrockModel instances to avoid recreating them
        self._model_cache: dict[str, Any] = {}

    def _get_bedrock_model(self, model_id: str) -> Any:
        """Get or create a BedrockModel instance for the given model ID."""
        if model_id not in self._model_cache:
            try:
                from strands.models import BedrockModel
                self._model_cache[model_id] = BedrockModel(
                    model_id=model_id,
                    region_name=self.config.aws_region,
                )
                logger.info("Created BedrockModel for %s", model_id)
            except ImportError:
                logger.error("strands-agents not installed - cannot create BedrockModel")
                return None
        return self._model_cache[model_id]

    def register_hooks(self, registry: Any) -> None:
        """Register with Strands HookRegistry (HookProvider protocol)."""
        try:
            from strands.experimental.hooks import BeforeModelInvocationEvent
            registry.add_callback(BeforeModelInvocationEvent, self.on_before_model_call)
            logger.info("RouteRight hook registered with Strands agent")
        except ImportError:
            logger.warning(
                "Could not import Strands experimental hooks. "
                "Make sure strands-agents is installed."
            )

    def on_before_model_call(self, event: Any) -> None:
        """Intercept model calls and swap to the appropriate model."""
        # Extract the last user message from the conversation
        messages = getattr(event.agent, "messages", [])
        if not messages:
            return

        last_msg = messages[-1]
        content = ""
        if isinstance(last_msg, dict):
            content = last_msg.get("content", "")
            if isinstance(content, list):
                # Handle structured content blocks
                content = " ".join(
                    block.get("text", "") for block in content
                    if isinstance(block, dict) and "text" in block
                )
        elif isinstance(last_msg, str):
            content = last_msg

        if not content:
            return

        # Route the decision
        model_id, decider_result = self.router.route(content)

        # Swap the model on the agent
        new_model = self._get_bedrock_model(model_id)
        if new_model:
            event.agent.model = new_model
            logger.info(
                "Swapped model to %s (choice=%s, confidence=%.3f)",
                model_id, decider_result.choice, decider_result.confidence,
            )


# ---------------------------------------------------------------------------
# Standalone function for direct usage (no Strands SDK required)
# ---------------------------------------------------------------------------

def create_router(
    config: RouterConfig | None = None,
    pricing_path: str = "config/pricing.json",
) -> RouteRightRouter:
    """Create a standalone RouteRightRouter (no Strands SDK dependency).

    This is useful for benchmarking or integrating with non-Strands agents.
    """
    config = config or RouterConfig()

    if config.mock_mode:
        from routeright.decider import MockDeciderClient
        decider = MockDeciderClient(randomize=True)
    else:
        from routeright.decider import DeciderClient
        decider = DeciderClient(
            model_id=config.decider_model_id,
            device=config.decider_device,
            server_url=config.decider_url,
        )

    return RouteRightRouter(
        decider=decider,
        config=config,
        pricing_path=pricing_path,
    )
