"""Typed question specification and option set for Strands Decider 2B."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List


# Canonical option set for model routing
ROUTING_OPTIONS: List[str] = ["small", "frontier"]

DEFAULT_QUESTION_ID = "model_routing_tier"
DEFAULT_INSTRUCTIONS = (
    "Does answering this user request require a frontier-class LLM, "
    "or can a small efficient model handle it adequately?"
)


@dataclass
class ModelRoutingQuestion:
    """Typed decision question specification for Strands Decider 2B.

    Decider 2B operates as a calibrated System One classifier. It evaluates
    the prompt state against typed options without text generation overhead.
    """

    question_id: str = DEFAULT_QUESTION_ID
    question_type: str = "choice"
    instructions: str = DEFAULT_INSTRUCTIONS
    options: List[str] = field(default_factory=lambda: list(ROUTING_OPTIONS))
    default_confidence_threshold: float = 0.70

    def to_decider_payload(self, user_message: str) -> dict[str, Any]:
        """Format request payload for Strands Decider 2B HTTP endpoint (/v1/systemone)."""
        return {
            "state": user_message,
            "questions": {
                self.question_id: {
                    "type": self.question_type,
                    "instructions": self.instructions,
                    "options": self.options,
                }
            },
        }

    def evaluate_decision(self, choice: str, confidence: float, threshold: float | None = None) -> str:
        """Apply safety-first routing policy.

        Returns:
            "small" if choice is "small" AND confidence >= threshold.
            "frontier" for all other cases (low confidence, ambiguous, or complex).
        """
        effective_threshold = threshold if threshold is not None else self.default_confidence_threshold
        if choice == "small" and confidence >= effective_threshold:
            return "small"
        return "frontier"
