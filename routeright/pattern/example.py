"""Example demonstrating RouteRight ModelRouter integration with a real Strands Agent.

Uses Strands Decider 2B (System 1) as a Strands RoutingStrategy with strands.models.ModelRouter
to dynamically dispatch prompts between frontier and small BedrockModel candidates.
"""

from strands import Agent
from strands.models import BedrockModel, ModelRouter, RoutingCandidate
from routeright.pattern import DeciderRoutingStrategy

# 1. Define candidate Amazon Bedrock models
frontier_model = BedrockModel(
    model_id="us.anthropic.claude-3-7-sonnet-20250219-v1:0",
    region_name="us-east-1",
)
small_model = BedrockModel(
    model_id="amazon.nova-micro-v1:0",
    region_name="us-east-1",
)

# 2. Wrap them into RoutingCandidate instances with explicit tier metadata
candidate_frontier = RoutingCandidate(
    model=frontier_model,
    name="frontier",
    description="Frontier reasoning model for complex tasks",
    metadata={"tier": "frontier"},
)
candidate_small = RoutingCandidate(
    model=small_model,
    name="small",
    description="Efficient small model for simple facts and formatting",
    metadata={"tier": "small"},
)

# 3. Create ModelRouter with DeciderRoutingStrategy (Strands Decider 2B System 1)
routing_strategy = DeciderRoutingStrategy(confidence_threshold=0.70)
router = ModelRouter(
    models=[candidate_frontier, candidate_small],
    strategy=routing_strategy,
)

# 4. Instantiate a real Strands Agent with the ModelRouter
agent = Agent(model=router)

if __name__ == "__main__":
    # Test simple query - routes to small model
    print("Executing simple query...")
    resp_simple = agent("What is the capital of Japan?")
    print("Response:", resp_simple)

    # Test complex query - escalates to frontier model
    print("\nExecuting complex query...")
    resp_complex = agent("Design an event-driven architecture with saga compensation.")
    print("Response:", resp_complex)
