"""RouteRight Reusable Decision Pattern for Strands Agents.

Exposes the typed question specification, option set, and agent wiring
to enable intelligent model routing in any Strands agent.
"""

from routeright.pattern.spec import (
    ModelRoutingQuestion,
    ROUTING_OPTIONS,
    DEFAULT_QUESTION_ID,
    DEFAULT_INSTRUCTIONS,
)
from routeright.pattern.wiring import (
    DeciderRoutingStrategy,
    RouteRightPattern,
    RouteRightInterventionHandler,
    create_decider_router,
)

__all__ = [
    "ModelRoutingQuestion",
    "ROUTING_OPTIONS",
    "DEFAULT_QUESTION_ID",
    "DEFAULT_INSTRUCTIONS",
    "DeciderRoutingStrategy",
    "RouteRightPattern",
    "RouteRightInterventionHandler",
    "create_decider_router",
]
