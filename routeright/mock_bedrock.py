"""Mock Bedrock client for zero-cost testing.

Provides fake LLM responses with realistic token counts and latency simulation.
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass


@dataclass
class MockBedrockResponse:
    """Simulated Bedrock response."""

    text: str
    model_id: str
    tokens_in: int
    tokens_out: int
    latency_ms: float


# Simple canned responses for mock mode
_SMALL_RESPONSES = [
    "The answer is 42.",
    "Paris is the capital of France.",
    "Here is the formatted text as requested.",
    "The sum of 2 + 2 is 4.",
    "Python was created by Guido van Rossum in 1991.",
]

_FRONTIER_RESPONSES = [
    "Let me break this down step by step. First, we need to consider the underlying architecture...",
    "Here is a detailed analysis with multiple perspectives on this complex topic...",
    "The debugging process reveals several interconnected issues. Let me walk through each one...",
    "This requires careful multi-step reasoning. Starting with the fundamentals...",
    "After thorough analysis, here are the key findings and recommendations...",
]


class MockBedrockClient:
    """Simulates Bedrock API calls with configurable latency."""

    def __init__(self, seed: int = 42):
        self._rng = random.Random(seed)

    def invoke(self, model_id: str, prompt: str, max_tokens: int = 1024) -> MockBedrockResponse:
        """Simulate a Bedrock model invocation."""
        is_frontier = "sonnet" in model_id.lower() or "opus" in model_id.lower()

        # Simulate latency - frontier models are slower
        if is_frontier:
            latency = self._rng.uniform(800, 2500)
            response_text = self._rng.choice(_FRONTIER_RESPONSES)
            tokens_out = self._rng.randint(150, 400)
        else:
            latency = self._rng.uniform(200, 600)
            response_text = self._rng.choice(_SMALL_RESPONSES)
            tokens_out = self._rng.randint(20, 80)

        time.sleep(latency / 1000)  # Actually wait to simulate real latency

        tokens_in = len(prompt.split()) * 2  # Rough token estimate

        return MockBedrockResponse(
            text=response_text,
            model_id=model_id,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            latency_ms=round(latency, 2),
        )
