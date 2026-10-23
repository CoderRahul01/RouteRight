"""Decider client - wraps Strands Decider 2B for routing decisions.

Supports three modes:
1. Local model (StrandsDeciderModel) - loads weights directly
2. HTTP server mode - calls a running strands-decider serve instance
3. Mock mode - deterministic fake responses for testing
"""

from __future__ import annotations

import json
import logging
import random
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

import httpx

logger = logging.getLogger("routeright.decider")


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class DeciderResult:
    """Result from a Decider 2B routing decision."""

    choice: str                    # "small" or "frontier"
    confidence: float              # 0.0 - 1.0
    probabilities: dict[str, float]  # per-option probabilities
    latency_ms: float              # time taken for the decision
    raw_response: dict[str, Any] | None = None


# ---------------------------------------------------------------------------
# The typed question we ask Decider 2B
# ---------------------------------------------------------------------------

ROUTING_QUESTION_ID = "model_routing"
ROUTING_QUESTION = {
    "type": "choice",
    "instructions": (
        "Does answering this user request require a frontier-class LLM "
        "(for multi-step reasoning, code debugging, complex analysis), "
        "or can a small efficient model handle it adequately "
        "(for simple facts, formatting, short rewrites)?"
    ),
    "options": ["small", "frontier"],
}


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------

class BaseDeciderClient(ABC):
    """Base class for decider clients."""

    @abstractmethod
    def decide(self, user_message: str) -> DeciderResult:
        """Ask Decider 2B whether this message needs a frontier or small model."""
        ...


# ---------------------------------------------------------------------------
# Real client - local model
# ---------------------------------------------------------------------------

class DeciderClient(BaseDeciderClient):
    """Calls Strands Decider 2B locally or via HTTP server."""

    def __init__(
        self,
        model_id: str = "StrandsAgents/strands-decider-2B-hobson-v21",
        device: str = "cpu",
        server_url: str | None = None,
    ):
        self._server_url = server_url
        self._model = None
        self._model_id = model_id
        self._device = device

        if server_url:
            logger.info("Decider client using HTTP server at %s", server_url)
        else:
            logger.info("Loading Decider 2B model locally: %s on %s", model_id, device)
            self._load_local_model()

    def _load_local_model(self) -> None:
        """Load the model weights locally using strands_decider."""
        try:
            from strands_decider.modeling import StrandsDeciderModel
            self._model = StrandsDeciderModel.load(self._model_id, device=self._device)
            logger.info("Decider 2B model loaded successfully")
        except ImportError:
            logger.warning(
                "strands_decider not installed or model load failed. "
                "Falling back to HTTP server mode. "
                "Start the server with: strands-decider serve %s",
                self._model_id,
            )
            if not self._server_url:
                self._server_url = "http://127.0.0.1:8000"
        except Exception as exc:
            logger.warning("Failed to load local model: %s. Falling back to HTTP.", exc)
            if not self._server_url:
                self._server_url = "http://127.0.0.1:8000"

    def decide(self, user_message: str) -> DeciderResult:
        """Route the decision through local model or HTTP server."""
        if self._server_url:
            return self._decide_http(user_message)
        return self._decide_local(user_message)

    def _decide_local(self, user_message: str) -> DeciderResult:
        """Use the locally loaded model."""
        from strands_decider.schema import ChoiceQuestion

        start = time.perf_counter()

        question = ChoiceQuestion(
            type="choice",
            instructions=ROUTING_QUESTION["instructions"],
            options=ROUTING_QUESTION["options"],
        )

        # The model evaluates state against questions
        results = self._model.ask(
            state=user_message,
            questions={ROUTING_QUESTION_ID: question},
        )

        elapsed_ms = (time.perf_counter() - start) * 1000

        answer = results.get(ROUTING_QUESTION_ID, {})
        choice = getattr(answer, "value", "frontier")
        confidence = getattr(answer, "confidence", 0.0)
        probabilities = {}
        if hasattr(answer, "probabilities"):
            probabilities = dict(answer.probabilities)

        result = DeciderResult(
            choice=choice,
            confidence=confidence,
            probabilities=probabilities,
            latency_ms=round(elapsed_ms, 2),
            raw_response={"answer": str(answer)},
        )

        logger.info(
            "Decider local: choice=%s confidence=%.3f latency=%.1fms",
            result.choice, result.confidence, result.latency_ms,
        )
        return result

    def _decide_http(self, user_message: str) -> DeciderResult:
        """Call the Decider 2B HTTP server."""
        start = time.perf_counter()

        payload = {
            "state": user_message,
            "questions": {ROUTING_QUESTION_ID: ROUTING_QUESTION},
        }

        try:
            resp = httpx.post(
                f"{self._server_url}/v1/systemone",
                json=payload,
                timeout=10.0,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            logger.error("Decider HTTP call failed: %s - defaulting to frontier", exc)
            elapsed_ms = (time.perf_counter() - start) * 1000
            return DeciderResult(
                choice="frontier",
                confidence=0.0,
                probabilities={"small": 0.0, "frontier": 1.0},
                latency_ms=round(elapsed_ms, 2),
                raw_response={"error": str(exc)},
            )

        elapsed_ms = (time.perf_counter() - start) * 1000

        answers = data.get("answers", {})
        answer = answers.get(ROUTING_QUESTION_ID, {})

        result = DeciderResult(
            choice=answer.get("value", "frontier"),
            confidence=answer.get("confidence", 0.0),
            probabilities=answer.get("probabilities", {}),
            latency_ms=round(elapsed_ms, 2),
            raw_response=data,
        )

        logger.info(
            "Decider HTTP: choice=%s confidence=%.3f latency=%.1fms",
            result.choice, result.confidence, result.latency_ms,
        )
        return result


# ---------------------------------------------------------------------------
# Mock client - zero cost testing
# ---------------------------------------------------------------------------

class MockDeciderClient(BaseDeciderClient):
    """Deterministic mock for testing. No model weights, no HTTP calls."""

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
        logger.info("MockDeciderClient initialized (randomize=%s)", randomize)

    def decide(self, user_message: str) -> DeciderResult:
        start = time.perf_counter()

        if self._randomize:
            # Use complexity signals to simulate realistic routing
            msg_lower = user_message.lower()
            msg_len = len(user_message)

            # Complexity indicators
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
                # Most simple questions are high confidence, but ~15% are borderline (0.62-0.68)
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

        # Simulate ~2-5ms decision latency
        time.sleep(self._rng.uniform(0.002, 0.005))
        elapsed_ms = (time.perf_counter() - start) * 1000

        return DeciderResult(
            choice=choice,
            confidence=round(confidence, 3),
            probabilities={"small": round(small_prob, 3), "frontier": round(frontier_prob, 3)},
            latency_ms=round(elapsed_ms, 2),
            raw_response={"mock": True},
        )
