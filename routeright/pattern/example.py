from strands import Agent
from strands.models import BedrockModel
from routeright.pattern import RouteRightPattern

# Initialize your agent with a default base model
base_model = BedrockModel(model_id="us.anthropic.claude-3-7-sonnet-20250219-v1:0")
agent = Agent(model=base_model)

# Attach RouteRight: Decider 2B now intercepts every call before Bedrock
router_pattern = RouteRightPattern()
router_pattern.attach(agent)

# Simple queries route to small model; complex queries route to frontier
response_simple = agent("What is the capital of Japan?")
print("Simple query response:", response_simple)

response_complex = agent("Design an event-driven architecture with saga compensation.")
print("Complex query response:", response_complex)

print("Savings meter summary:", router_pattern.router.get_savings_summary())
