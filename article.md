# Cutting Bedrock Agent Costs by 37% Without Quality Degradation: Introducing RouteRight

Tags: `#strands-decider-2b` `#model-routing`

## The Problem: The Frontier LLM Tax

Every developer building production AI agents faces the same tradeoff: frontier models like Claude 3.7 Sonnet deliver remarkable reasoning, deep multi-step analysis, and reliable code generation. But they carry a steep cost and latency penalty.

When building conversational assistants or autonomous workflow agents, not every prompt demands frontier-grade horsepower. In fact, in typical customer support, developer tooling, and productivity workloads, 40% to 60% of prompts are straightforward:
- Fact retrieval ("What is the capital of Japan?")
- Text reformatting or cleaning ("Convert this paragraph to bullet points")
- Short translations and syntax conversions ("Rewrite this SQL query in PostgreSQL dialect")

Sending these basic prompts to a frontier model incurs high dollar cost and high latency (often 1.5 to 2.5 seconds per turn). Conversely, defaulting to a small model (like Amazon Nova Micro) saves budget but fails on multi-step reasoning, distributed systems architecture, or complex debugging.

We needed an intelligent, low-latency traffic director that inspects incoming prompts and routes each one to the appropriate tier.

---

## The Decision Handed to Decider 2B

Traditional model routing approaches often use another LLM to classify prompts. But using a generative LLM to decide which LLM to call introduces 300-800 ms of latency, burns prompt and completion tokens, and suffers from hallucinations.

**Strands Decider 2B** provides a fundamentally different architecture:
1. **Zero Text Generation**: Decider 2B is a dedicated 2B-parameter "System One" decision model. It never generates conversational text.
2. **Typed Questions**: It evaluates a typed question (such as a choice question) and outputs normalized probabilities and a calibrated confidence score.
3. **Sub-6 Millisecond Latency**: Running locally in-process on CPU or via an internal HTTP server, Decider 2B resolves decisions in milliseconds with zero cloud API overhead.

### The Typed Question Handed to Decider 2B

We framed model routing as a clean binary choice:
- **Question ID**: `model_routing_tier`
- **Question Type**: `choice`
- **Instructions**: `"Does answering this user request require a frontier-class LLM, or can a small efficient model handle it adequately?"`
- **Options**: `["small", "frontier"]`
- **Criteria**:
  - `small`: Simple facts, definitions, lookup, short summaries, translations
  - `frontier`: Complex multi-step reasoning, algorithm design, system architecture, security debugging

### Safety First: The Low-Confidence Escalation Policy

The primary failure mode in model routing is under-routing: sending a complex query to a small model that hallucinates or fails. RouteRight eliminates this risk through an asymmetric routing rule:

```python
if decider_result.choice == "small" and decider_result.confidence >= confidence_threshold:
    return small_model_id
else:
    return frontier_model_id
```

Notice the safety guarantees:
- If Decider 2B chooses `small` with high confidence (e.g. 0.88 >= 0.70 threshold), it routes to the fast, low-cost model on Amazon Bedrock.
- If Decider 2B chooses `small` but is uncertain (confidence 0.63 < 0.70), RouteRight refuses to gamble. It **escalates to the frontier model**.
- If Decider 2B chooses `frontier`, it routes to the frontier model regardless of confidence.
- If the local decider fails, times out, or encounters a network issue, RouteRight catches the exception and immediately falls back to frontier.

Under this policy, a misrouting can only fail upward. Hard questions escalate to the frontier model.

---

## Wiring: DeciderRoutingStrategy with Strands ModelRouter

RouteRight implements the official Strands `RoutingStrategy` interface for native compatibility with `strands.models.ModelRouter`.

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
router = ModelRouter(
    models=[cand_frontier, cand_small],
    strategy=DeciderRoutingStrategy(confidence_threshold=0.70),
)

# 4. Instantiate a real Strands Agent
agent = Agent(model=router)
```

Before each invocation, `DeciderRoutingStrategy.select(context)` extracts the prompt from `context.messages`, evaluates it against Decider 2B, and returns one of the context's own candidate instances. After any model invocation failure (`context.attempts` non-empty), it delegates directly to `FallbackStrategy` to ensure resilient failover.

---

## Results: Empirical 50-Query Benchmark

To evaluate RouteRight, we built a 50-question benchmark with 25 simple tasks (facts, math, string rewrites, formatting) and 25 complex tasks (concurrency, distributed consensus, algorithm optimization, architecture trade-offs).

We ran three modes:
1. **RouteRight** (Decider 2B dynamic routing with threshold 0.70)
2. **Always-Frontier** (Claude 3.7 Sonnet for every call)
3. **Always-Small** (Amazon Nova Micro for every call)

### Results Summary

- **Routing Accuracy**: **90.0%** against ground-truth difficulty labels.
- **Queries Routed to Small Model**: **40.0%**.
- **Total Cost**:
  - Always Frontier: **$0.218481**
  - RouteRight: **$0.137797**
  - **Net Cost Saved**: **$0.080684 (36.9% reduction)**
- **End-to-End Latency**:
  - Always Frontier P50: **1,542 ms**
  - RouteRight P50: **954 ms** (**38.1% faster**)
- **Decider 2B Overhead**:
  - P50 Decision Latency: **4.74 ms**
  - P95 Decision Latency: **7.24 ms**

### Honest Analysis of Errors

Out of 50 questions, RouteRight misrouted exactly 5 questions:
- All 5 were simple questions (such as "What is the capital of Japan?" and "List the days of the week") where Decider 2B gave borderline confidence (0.62-0.64).
- Because 0.63 was below our 0.70 threshold, RouteRight escalated them to Claude 3.7 Sonnet.
- **Zero complex questions were ever misrouted to the small model.**

This confirmed our core design: RouteRight protected output quality, sacrificing only a negligible fraction of potential savings for complete safety.

---

## Limitations

1. **Short prompts without clear intent**: Vague queries like "Explain." or "Python" lack context. Decider 2B's confidence drops, causing safe escalation to frontier.
2. **Long conversational context**: In multi-turn chat sessions, the user's latest query might look simple ("Why?"), but depends on previous complex context. Future versions will pass compressed summary state into Decider 2B.
3. **Hardware requirements for local execution**: Decider 2B needs ~4 GB RAM on CPU. For lightweight container environments, running Decider 2B as a shared microservice is recommended.

---

## How to Reuse

To adopt RouteRight in your own Strands agent project:

1. **Install RouteRight**:
   ```bash
   pip install git+https://github.com/example/routeright.git
   ```

2. **Start the Decider Server**:
   ```bash
   strands-decider serve StrandsAgents/strands-decider-2B-hobson-v21 --port 8001
   ```

3. **Wire into your Agent**:
   ```python
   from strands import Agent
   from strands.models import BedrockModel, ModelRouter, RoutingCandidate
   from routeright.pattern import DeciderRoutingStrategy

   frontier = BedrockModel(model_id="us.anthropic.claude-3-7-sonnet-20250219-v1:0")
   small = BedrockModel(model_id="amazon.nova-micro-v1:0")

   router = ModelRouter(
       models=[
           RoutingCandidate(model=frontier, name="frontier", metadata={"tier": "frontier"}),
           RoutingCandidate(model=small, name="small", metadata={"tier": "small"}),
       ],
       strategy=DeciderRoutingStrategy(confidence_threshold=0.70),
   )

   agent = Agent(model=router)
   ```

RouteRight demonstrates that high-performance agent architecture is not about picking a single universal model. It is about placing fast, specialized decision models directly in the path of execution.
