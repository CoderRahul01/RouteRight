"""Configuration for RouteRight - all settings come from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from dotenv import load_dotenv


load_dotenv()


@dataclass
class RouterConfig:
    """All RouteRight settings. Never hardcodes model IDs or secrets."""

    # AWS / Bedrock
    aws_region: str = field(default_factory=lambda: os.getenv("AWS_REGION", "us-east-1"))
    frontier_model_id: str = field(
        default_factory=lambda: os.getenv(
            "ROUTERIGHT_FRONTIER_MODEL",
            "us.anthropic.claude-3-7-sonnet-20250219-v1:0",
        )
    )
    small_model_id: str = field(
        default_factory=lambda: os.getenv(
            "ROUTERIGHT_SMALL_MODEL",
            "us.anthropic.claude-3-haiku-20240307-v1:0",
        )
    )

    # Decider 2B
    decider_model_id: str = field(
        default_factory=lambda: os.getenv(
            "ROUTERIGHT_DECIDER_MODEL",
            "StrandsAgents/strands-decider-2B-hobson-v21",
        )
    )
    decider_device: str = field(
        default_factory=lambda: os.getenv("ROUTERIGHT_DECIDER_DEVICE", "cpu")
    )
    decider_url: str | None = field(
        default_factory=lambda: os.getenv("ROUTERIGHT_DECIDER_URL")
    )

    # Router behavior
    confidence_threshold: float = field(
        default_factory=lambda: float(os.getenv("ROUTERIGHT_CONFIDENCE_THRESHOLD", "0.7"))
    )
    max_tokens: int = field(
        default_factory=lambda: int(os.getenv("ROUTERIGHT_MAX_TOKENS", "1024"))
    )

    # Mock mode
    mock_mode: bool = field(
        default_factory=lambda: os.getenv("ROUTERIGHT_MOCK_MODE", "false").lower() == "true"
    )

    # Server
    host: str = field(default_factory=lambda: os.getenv("ROUTERIGHT_HOST", "0.0.0.0"))
    port: int = field(default_factory=lambda: int(os.getenv("ROUTERIGHT_PORT", "8080")))
