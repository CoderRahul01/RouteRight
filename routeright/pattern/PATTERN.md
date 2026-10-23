# Reusable Decision Pattern: RouteRight Dynamic Model Router

## Overview

RouteRight is a drop-in decision pattern for Strands agents that intercepts prompts before every LLM invocation. By using Strands Decider 2B (a calibrated 2B parameter decision model that outputs probabilities and confidence without generating conversational text), RouteRight dynamically routes easy requests to efficient small models and complex requests to frontier models on Amazon Bedrock.

Low-confidence decisions always escalate to the frontier model, ensuring hard questions escalate to the frontier model.

---

## The Decision Handed to Decider 2B

### Typed Question Specification
- **Question ID**: `model_routing_tier`
- **Question Type**: `choice`
- **Instructions**: `"Does answering this user request require a frontier-class LLM, or can a small efficient model handle it adequately?"`
- **Option Set**: `["small", "frontier"]`

### System One vs System Two Separation
- **System One (Decider 2B)**: Runs locally on CPU/GPU. Produces a calibrated probability distribution and confidence score. It never generates conversational text.
- **System Two (Amazon Bedrock)**: Runs the selected model (e.g., Amazon Nova Micro for small tier; Claude 3.7 Sonnet for frontier tier) to generate the actual response.

---

## Strands Agent Wiring

RouteRight implements the official Strands `RoutingStrategy` interface for native integration with `strands.models.ModelRouter`:

### 1. Native ModelRouter Pattern (Primary)
Wrap your candidate Bedrock models into `RoutingCandidate` instances, pair them with `DeciderRoutingStrategy`, and pass the resulting `ModelRouter` directly into your Strands `Agent`:

```python
from strands import Agent
from strands.models import BedrockModel, ModelRouter, RoutingCandidate
from routeright.pattern import DeciderRoutingStrategy

# 1. Define candidate Amazon Bedrock models
frontier_model = BedrockModel(model_id="us.anthropic.claude-3-7-sonnet-20250219-v1:0", region_name="us-east-1")
small_model = BedrockModel(model_id="amazon.nova-micro-v1:0", region_name="us-east-1")

# 2. Wrap into RoutingCandidate instances
cand_frontier = RoutingCandidate(model=frontier_model, name="frontier", metadata={"tier": "frontier"})
cand_small = RoutingCandidate(model=small_model, name="small", metadata={"tier": "small"})

# 3. Create ModelRouter with DeciderRoutingStrategy
strategy = DeciderRoutingStrategy(confidence_threshold=0.70)
router = ModelRouter(models=[cand_frontier, cand_small], strategy=strategy)

# 4. Instantiate a real Strands Agent
agent = Agent(model=router)

response = agent("What is the capital of Japan?")
```

### 2. Resilient Failover Protocol
`DeciderRoutingStrategy` complies strictly with the Strands routing lifecycle:
- Returns one of the context's own candidate instances.
- After any model invocation failure (`context.attempts` non-empty), it delegates directly to `FallbackStrategy` to select the next healthiest available candidate.

### 3. Alternative: HookProvider Pattern
For existing agents that do not use `ModelRouter`, RouteRight provides a hook provider:

```python
from strands import Agent
from routeright.pattern import RouteRightPattern

pattern = RouteRightPattern()
agent = Agent(model="us.anthropic.claude-3-7-sonnet-20250219-v1:0")
pattern.attach(agent)
```

---

## Tuning the Confidence Threshold

The confidence threshold (`ROUTERIGHT_CONFIDENCE_THRESHOLD`, default `0.70`) controls how conservative the router is when picking the small model.

| Profile | Threshold | Description | Best For |
|---------|-----------|-------------|----------|
| **Conservative (Default: 0.75 - 0.80)** | High | Routes to small only when Decider 2B is highly confident. Most borderline questions escalate to frontier. | Production customer-facing bots, medical, legal, financial workflows. |
| **Balanced (0.70)** | Medium | Healthy balance between cost savings (~35-45%) and zero quality degradation. | General assistance, developer tools, internal enterprise chat. |
| **Aggressive (0.55 - 0.65)** | Low | Routes to small whenever small probability is slightly favored. Maximizes cost savings (>50%). | High-volume extraction, translation, data summarization, internal testing. |

### Routing Truth Table

| Decider Choice | Decider Confidence | Threshold | Route Result | Rationale |
|----------------|--------------------|-----------|--------------|-----------|
| `small` | 0.88 | 0.70 | **Small Model** | Clear simple query, high confidence. |
| `small` | 0.63 | 0.70 | **Frontier Model** | Low confidence safety escalation. Hard questions escalate to frontier. |
| `frontier` | 0.94 | 0.70 | **Frontier Model** | Complex query, needs frontier reasoning. |
| `frontier` | 0.58 | 0.70 | **Frontier Model** | Uncertain complexity, always defaults to safety. |
| Any failure | 0.00 | Any | **Frontier Model** | Network error or timeout defaults to frontier. |

---

## Honest Limitations

1. **Short prompts without clear intent**: Vague queries like "Help me with this" provide little complexity signal. Decider 2B assigns moderate confidence, causing RouteRight to safely default to frontier.
2. **Context-heavy chat history**: If earlier turns in a multi-turn conversation contain deep code snippets, routing must inspect conversation context, not just the latest user turn.
3. **Model size on device**: Strands Decider 2B requires ~4 GB RAM on CPU or GPU memory. For constrained edge devices, the HTTP client mode should point to an internal microservice instance.
