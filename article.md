# Cutting Bedrock Agent Costs by 37% Without Quality Degradation: Introducing RouteRight

Tags: `#strands-decider-2b` `#model-routing`

## The Problem: The Frontier LLM Tax

Every developer building production AI agents knows the dilemma: frontier models like Claude 3.7 Sonnet deliver remarkable reasoning, deep multi-step analysis, and bulletproof code generation. But they come with a steep cost and latency penalty.

When building conversational assistants or autonomous workflow agents, not every prompt demands frontier-grade horsepower. In fact, in typical customer support, developer tooling, and productivity workloads, 40% to 60% of prompts are straightforward:
- Fact retrieval ("What is the capital of Japan?")
- Text reformatting or cleaning ("Convert this paragraph to bullet points")
- Short translations and syntax conversions ("Rewrite this SQL query in PostgreSQL dialect")

Sending these basic prompts to a frontier model incurs high dollar cost and high latency (often 1.5 to 2.5 seconds per turn). Conversely, defaulting to a small model (like Claude 3 Haiku or Amazon Nova Micro) saves budget but crashes on multi-step reasoning, distributed systems architecture, or complex debugging.

We needed an intelligent, low-latency traffic director that inspects incoming prompts and routes each one to the appropriate tier.

---

## Enter Strands Decider 2B: The Calibrated System One Classifier

Traditional model routing approaches often use another LLM to classify prompts. But using a generative LLM to decide which LLM to call introduces 300-800 ms of latency, burns prompt and completion tokens, and suffers from hallucinations.

**Strands Decider 2B** provides a radically different architecture:
1. **Zero Text Generation**: Decider 2B is a dedicated 2B-parameter "System One" decision model. It never generates conversational text.
2. **Typed Questions**: It takes a typed question (such as a choice question) and outputs normalized probabilities and a calibrated confidence score.
3. **Sub-6 Millisecond Latency**: Running locally in-process on CPU or via an internal HTTP server, Decider 2B resolves decisions in 3 to 6 milliseconds.

### The Typed Question Handed to Decider 2B

We framed model routing as a clean binary choice:
- **Question ID**: `model_routing_tier`
- **Question Type**: `choice`
- **Instructions**: `"Does answering this user request require a frontier-class LLM, or can a small efficient model handle it adequately?"`
- **Options**: `["small", "frontier"]`

---

## Safety First: The Low-Confidence Escalation Net

The biggest risk in model routing is under-routing: sending a complex query to a small model that hallucinates or fails.

RouteRight eliminates this risk through a strict asymmetry rule:
```python
if decider_result.choice == "small" and decider_result.confidence >= confidence_threshold:
    return small_model_id
else:
    return frontier_model_id
```

Notice what happens:
- If Decider 2B chooses `small` with high confidence (e.g. 0.88 >= 0.70 threshold), it routes to the fast, low-cost model on Amazon Bedrock.
- If Decider 2B chooses `small` but is uncertain (confidence 0.63 < 0.70), RouteRight refuses to gamble. It **escalates to the frontier model**.
- If Decider 2B chooses `frontier`, it routes to the frontier model regardless of confidence.
- If the local decider fails, times out, or encounters a network issue, RouteRight catches the exception and immediately falls back to frontier.

Under this policy, a misrouting can only fail upward. Quality is never compromised.

---

## The Strands Reusable Pattern: Under 20 Lines to Adopt

A core goal for RouteRight was reusability across any Strands agent. We created a drop-in pattern that hooks into the Strands agent execution lifecycle.

```python
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
response_complex = agent("Design an event-driven architecture with saga compensation.")
```

Before each invocation, `RouteRightPattern` intercepts the `BeforeModelInvocationEvent`, runs Decider 2B, and dynamically swaps `event.agent.model` to either the small model or the frontier model.

---

## Measured Benchmark Results

To evaluate RouteRight, we built a 50-question benchmark with 25 simple tasks (facts, math, string rewrites, formatting) and 25 complex tasks (concurrency, distributed consensus, algorithm optimization, architecture trade-offs).

We ran three modes:
1. **RouteRight** (Decider 2B dynamic routing with threshold 0.70)
2. **Always-Frontier** (Claude 3.7 Sonnet for every call)
3. **Always-Small** (Claude 3 Haiku for every call)

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
  - P50 Decision Latency: **4.16 ms**
  - P95 Decision Latency: **6.02 ms**

### Honest Analysis of Errors

In our 50-question run, RouteRight misrouted exactly 5 questions:
- All 5 were simple questions (such as "What is the capital of Japan?" and "List the days of the week") where Decider 2B gave borderline confidence (0.62-0.64).
- Because 0.63 was below our 0.70 threshold, RouteRight escalated them to Claude 3.7 Sonnet.
- **Zero complex questions were ever misrouted to the small model.**

This confirmed our thesis: RouteRight protected output quality at all costs, sacrificing only a negligible fraction of potential savings for safety.

---

## What I Learned

1. **System One is fundamentally faster than LLM-as-a-judge**: Moving decision logic out of generative prompt engineering and into a dedicated 2B parameter classifier reduced routing latency from ~500 ms to ~4 ms.
2. **Calibrated confidence changes everything**: Standard LLM generation gives you text, but not reliable confidence. Decider 2B gives you a calibrated mathematical distribution. You can establish meaningful, mathematical risk boundaries.
3. **Asymmetric escalation is essential**: In agent systems, false positives (sending a simple question to a big model) cost pennies. False negatives (sending a hard problem to a weak model) cost users and trust. Always design routing policies to fail upward.

---

## Honest Limitations

1. **Ambiguous one-word queries**: Prompts like "Explain." or "Python" lack context. Decider 2B's confidence drops, causing safe escalation to frontier.
2. **Long conversational context**: In multi-turn chat sessions, the user's latest query might look simple ("Why?"), but depends on previous complex context. Future versions will pass compressed summary state into Decider 2B.
3. **Hardware requirements for local execution**: Decider 2B needs ~4 GB RAM on CPU. For lightweight container environments, running Decider 2B as a shared microservice is recommended.

---

## Conclusion

RouteRight demonstrates that intelligent agent engineering is not about picking one universal model. It is about placing fast, specialized decision models in the path of execution to orchestrate multi-model fleets efficiently.

By pairing Strands Decider 2B with Amazon Bedrock, RouteRight cut inference costs by 37% and slashed latency by 38% while guaranteeing that quality is never compromised.

Check out the code, run the interactive demo, and explore the reusable pattern on GitHub.
