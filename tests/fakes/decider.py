"""Mock Decider client for automated unit tests."""

from __future__ import annotations

import logging
import random
import time

from routeright.decider import BaseDeciderClient, DeciderResult

logger = logging.getLogger("tests.fakes.decider")


class MockDeciderClient(BaseDeciderClient):
    """Deterministic mock for unit testing only."""

    def __init__(
        self,
        default_choice: str = "small",
        default_confidence: float = 0.85,
        randomize: bool = False,
        seed: int = 42,
    ):
        self._default_choice = default_choice
        self._default_confidence = default_confidence
        self._randomize = randomize
        self._rng = random.Random(seed)

    def decide(self, user_message: str) -> DeciderResult:
        start = time.perf_counter()

        if self._randomize:
            msg_lower = user_message.lower()
            msg_len = len(user_message)

            complex_keywords = [
                "explain", "debug", "design", "analyze", "compare", "implement",
                "write a", "walk through", "trade-off", "architecture",
                "step by step", "optimize", "security", "vulnerab", "concurrent",
                "distributed", "algorithm", "complexity", "refactor",
                "multi-step", "reasoning", "race condition", "protocol",
                "trade-offs", "database schema", "crawler", "internals",
            ]
            simple_keywords = [
                "what is", "how many", "name", "list", "capital", "convert",
                "define", "translate", "reverse", "sort", "plural", "stand for",
                "color", "symbol", "year", "boiling", "square root", "rewrite",
                "capitalize", "remove", "who wrote", "what does", "who is",
                "which", "calculate", "math", "past tense", "ocean",
            ]

            complex_score = sum(1 for kw in complex_keywords if kw in msg_lower)
            simple_score = sum(1 for kw in simple_keywords if kw in msg_lower)

            if complex_score > simple_score or msg_len > 180:
                frontier_prob = 0.82 + self._rng.random() * 0.15
                choice = "frontier"
                confidence = 0.75 + self._rng.random() * 0.22
            elif simple_score > 0 and complex_score == 0:
                frontier_prob = 0.05 + self._rng.random() * 0.18
                choice = "small"
                if self._rng.random() < 0.16:
                    confidence = 0.62 + self._rng.random() * 0.06
                else:
                    confidence = 0.76 + self._rng.random() * 0.20
            else:
                frontier_prob = 0.45 + self._rng.random() * 0.2
                choice = "frontier" if frontier_prob > 0.5 else "small"
                confidence = 0.60 + self._rng.random() * 0.25

            small_prob = 1.0 - frontier_prob
        else:
            choice = self._default_choice
            confidence = self._default_confidence
            small_prob = 0.85 if choice == "small" else 0.15
            frontier_prob = 1.0 - small_prob

        time.sleep(self._rng.uniform(0.002, 0.005))
        elapsed_ms = (time.perf_counter() - start) * 1000

        return DeciderResult(
            choice=choice,
            confidence=round(confidence, 3),
            probabilities={"small": round(small_prob, 3), "frontier": round(frontier_prob, 3)},
            latency_ms=round(elapsed_ms, 2),
            raw_response={"mock": True},
        )

    def check_health(self) -> dict[str, Any]:
        return {
            "status": "ok",
            "connected": True,
            "mock": True,
            "model": "mock-strands-decider-2b",
            "device": "cpu",
        }
