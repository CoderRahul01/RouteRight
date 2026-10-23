"""Decider client - wraps Strands Decider 2B for model routing decisions.

Supports two real execution modes:
1. HTTP server mode: calls a running `strands-decider serve <model> --port <port>` instance.
   Official command: strands-decider serve StrandsAgents/strands-decider-2B-hobson-v21 --port 8001
2. Local in-process mode: loads model directly via `StrandsDeciderModel.load()`.

Never falls back to fake/mock output in runtime code. If unreachable, raises clear
descriptive error with exact setup instructions.
"""

from __future__ import annotations

import logging
import platform
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
    """Result from a Strands Decider 2B routing decision."""

    choice: str                      # "small" or "frontier"
    confidence: float                # 0.0 - 1.0 (calibrated)
    probabilities: dict[str, float]  # per-option probabilities
    latency_ms: float                # real execution time in milliseconds
    raw_response: dict[str, Any] | None = None


# ---------------------------------------------------------------------------
# The typed question definition for Decider 2B
# ---------------------------------------------------------------------------

ROUTING_QUESTION_ID = "model_routing"
ROUTING_QUESTION = {
    "type": "choice",
    "instructions": (
        "Does answering this user request require a frontier-class LLM "
        "(for multi-step reasoning, code debugging, complex analysis, mathematical proofs), "
        "or can a small efficient model handle it adequately "
        "(for simple facts, formatting, short translations, greetings)?"
    ),
    "criteria": {
        "small": "Simple facts, definitions, lookup, short summaries, translations",
        "frontier": "Complex multi-step reasoning, algorithm design, system architecture, security debugging",
    },
}


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------

class BaseDeciderClient(ABC):
    """Base interface for decider clients."""

    @abstractmethod
    def decide(self, user_message: str) -> DeciderResult:
        """Ask Decider 2B whether this message needs a frontier or small model."""
        ...

    @abstractmethod
    def check_health(self) -> dict[str, Any]:
        """Health check decider model status, device, and connectivity."""
        ...


# ---------------------------------------------------------------------------
# Real Decider Client
# ---------------------------------------------------------------------------

class DeciderClient(BaseDeciderClient):
    """Real Strands Decider 2B client communicating via HTTP server or in-process."""

    def __init__(
        self,
        model_id: str = "StrandsAgents/strands-decider-2B-hobson-v21",
        device: str = "cpu",
        server_url: str | None = "http://127.0.0.1:8001",
    ):
        self._server_url = server_url.rstrip("/") if server_url else "http://127.0.0.1:8001"
        self._model_id = model_id
        self._device = device
        self._local_model = None
        self.last_latency_ms: float = 0.0

        logger.info(
            "DeciderClient configured for model %s (HTTP target: %s, device: %s)",
            self._model_id, self._server_url, self._device,
        )

    def check_health(self) -> dict[str, Any]:
        """Query the /health endpoint of the running strands-decider server."""
        if self._server_url:
            try:
                with httpx.Client(timeout=2.0) as client:
                    resp = client.get(f"{self._server_url}/health")
                    if resp.status_code == 200:
                        data = resp.json()
                        data["connected"] = True
                        data["url"] = self._server_url
                        data["os"] = platform.system()
                        return data
            except Exception as exc:
                logger.debug("Decider health check probe failed: %s", exc)

        return {
            "status": "unreachable",
            "connected": False,
            "url": self._server_url,
            "model": self._model_id,
            "device": self._device,
            "os": platform.system(),
            "instructions": (
                f"Start Decider 2B locally with: "
                f"strands-decider serve {self._model_id} --port {self._server_url.split(':')[-1]}"
            ),
        }

    def _ensure_local_engine(self):
        """Lazy load local model if in-process inference is needed."""
        if self._local_model is None:
            from strands_decider.infer import EngineConfig, SystemOneEngine
            from strands_decider.modeling import StrandsDeciderModel

            logger.info("Loading local StrandsDeciderModel in-process: %s", self._model_id)
            model = StrandsDeciderModel.load(self._model_id)
            cfg = EngineConfig(device=self._device, model_name=self._model_id)
            self._local_model = SystemOneEngine(model, cfg)
        return self._local_model

    def decide(self, user_message: str) -> DeciderResult:
        """Route the prompt using real Strands Decider 2B.

        Times the decision strictly with time.perf_counter() around the real call.
        Disables caching headers to ensure pure execution latency measurement.
        """
        payload = {
            "state": user_message,
            "questions": {ROUTING_QUESTION_ID: ROUTING_QUESTION},
            "model": self._model_id,
        }

        # Attempt HTTP call to strands-decider serve
        try:
            headers = {
                "Cache-Control": "no-cache, no-store",
                "Pragma": "no-cache",
                "Content-Type": "application/json",
            }
            start = time.perf_counter()
            with httpx.Client(timeout=15.0) as client:
                resp = client.post(
                    f"{self._server_url}/v1/systemone",
                    json=payload,
                    headers=headers,
                )
            elapsed_ms = (time.perf_counter() - start) * 1000
            resp.raise_for_status()
            data = resp.json()

            answers = data.get("answers", {})
            ans = answers.get(ROUTING_QUESTION_ID, {})

            # In strands-decider, ChoiceAnswer has field 'choice'
            choice = ans.get("choice", "frontier")
            confidence = float(ans.get("confidence", 0.0))
            probabilities = {k: float(v) for k, v in ans.get("probabilities", {}).items()}

            self.last_latency_ms = round(elapsed_ms, 2)

            return DeciderResult(
                choice=choice,
                confidence=confidence,
                probabilities=probabilities,
                latency_ms=self.last_latency_ms,
                raw_response=data,
            )

        except Exception as http_exc:
            logger.warning(
                "Decider HTTP call to %s failed (%s). Trying local in-process fallback.",
                self._server_url, http_exc,
            )

            # Try local in-process execution before failing
            try:
                from strands_decider.schema import ChoiceQuestion, SystemOneRequest

                engine = self._ensure_local_engine()
                q = ChoiceQuestion(
                    type="choice",
                    instructions=ROUTING_QUESTION["instructions"],
                    criteria=ROUTING_QUESTION["criteria"],
                )
                req = SystemOneRequest(
                    state=user_message,
                    questions={ROUTING_QUESTION_ID: q},
                    model=self._model_id,
                )

                start = time.perf_counter()
                resp = engine.evaluate(req)
                elapsed_ms = (time.perf_counter() - start) * 1000

                ans = resp.answers[ROUTING_QUESTION_ID]
                self.last_latency_ms = round(elapsed_ms, 2)

                return DeciderResult(
                    choice=ans.choice,
                    confidence=ans.confidence,
                    probabilities=ans.probabilities,
                    latency_ms=self.last_latency_ms,
                    raw_response=resp.model_dump(),
                )
            except Exception as local_exc:
                raise ConnectionError(
                    f"Strands Decider 2B is unreachable via HTTP at {self._server_url} ({http_exc}) "
                    f"and local in-process execution failed ({local_exc}). "
                    f"To start the decider server, run:\n"
                    f"  strands-decider serve {self._model_id} --port 8001"
                ) from http_exc
