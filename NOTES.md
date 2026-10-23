# RouteRight - Research Notes (Phase 0)

## Strands Decider 2B - Verified API

### What it is
- A "System One" decision model (2B params, Qwen3.5-2B-Base backbone)
- Never generates text - only picks from typed options with calibrated confidence
- Apache-2.0 license
- Checkpoints on HuggingFace: `StrandsAgents/strands-decider-2B-hobson-v21` (recommended)

### Install
```bash
pip install strands-decider
```

### Three question types
1. **noul** (yes/no) - returns probability of true (no separate confidence field)
2. **choice** - picks from N options, returns per-option probabilities + confidence score
3. **score** - ordered scale rating

### CLI usage
```bash
strands-decider ask StrandsAgents/strands-decider-2B-hobson-v21 \
  --state "Help! My payouts have been failing for 3 days!" \
  --choice "Which team should handle this?=billing,sales,retail"
```

### Python programmatic API
```python
from strands_decider.modeling import StrandsDeciderModel
from strands_decider.schema import ChoiceQuestion, NoulQuestion

model = StrandsDeciderModel.load("StrandsAgents/strands-decider-2B-hobson-v21", device="cpu")
```

### Local HTTP server
```bash
strands-decider serve StrandsAgents/strands-decider-2B-hobson-v21 --port 8000
```

### Server API endpoint: POST /v1/systemone
```json
// Request
{
  "state": "user message text",
  "questions": {
    "my_question_id": {
      "type": "choice",
      "instructions": "Which model tier?",
      "options": ["small", "frontier"]
    }
  }
}

// Response
{
  "model": "strands-decider-2B",
  "answers": {
    "my_question_id": {
      "value": "small",
      "confidence": 0.768,
      "probabilities": {
        "small": 0.845,
        "frontier": 0.155
      }
    }
  },
  "usage": {
    "prompt_tokens": 42,
    "completion_tokens": 0
  },
  "latency_ms": 115
}
```

### Confidence behavior
- For `choice`/`score`: explicit confidence field (distribution concentration metric)
- For `noul`: probability value IS the confidence (no separate field)
- Confidence >= 0.9 is right ~95% of the time per the docs

---

## Strands Agents SDK - Verified API

### Install
```bash
pip install strands-agents strands-agents-tools
```

### BedrockModel usage
```python
from strands import Agent
from strands.models import BedrockModel

bedrock_model = BedrockModel(
    model_id="us.anthropic.claude-3-7-sonnet-20250219-v1:0",
    region_name="us-east-1",
    temperature=0.2
)
agent = Agent(model=bedrock_model)
```

### Dynamic model switching via hooks (experimental)
```python
from strands.hooks import HookProvider, HookRegistry
from strands.experimental.hooks import BeforeModelInvocationEvent
from strands.models import BedrockModel

class DynamicModelRouterHook(HookProvider):
    def register_hooks(self, registry: HookRegistry) -> None:
        registry.add_callback(BeforeModelInvocationEvent, self.on_before_model_call)

    def on_before_model_call(self, event: BeforeModelInvocationEvent) -> None:
        messages = event.agent.messages
        # Swap model dynamically:
        event.agent.model = BedrockModel(model_id="...")
```

### InterventionHandler (typed decisions)
```python
from strands.interventions import InterventionHandler, Proceed, Guide, Deny

class MyHandler(InterventionHandler):
    name = "my-handler"

    def before_model_call(self, event):
        return Proceed()  # or Guide(reason="...") or Deny(reason="...")
```

---

## Architecture Decision: Which hook mechanism to use

**Primary approach: HookProvider with BeforeModelInvocationEvent**
- This gives us access to `event.agent.model` which we can swap dynamically
- Perfect for model routing - we intercept before the call and swap to the right model

**Secondary/fallback: InterventionHandler**
- More limited - returns Proceed/Deny/Guide but does not expose model swapping
- Better for guardrails than for routing
- We will ALSO expose this pattern since hackathon requires a reusable pattern

**Decision: Use BOTH**
- HookProvider for the actual routing (swaps model on event.agent.model)
- InterventionHandler wrapper as the reusable pattern (simpler API for users)

---

## Our typed question for Decider 2B (choice type)

```
instructions: "Does answering this user request require a frontier-class LLM, or can a small efficient model handle it adequately?"
options: ["small", "frontier"]
```

Router logic:
- If choice == "small" AND confidence >= threshold (default 0.7): use small model
- Otherwise: use frontier model (safe default)

---

## Open questions / assumptions

1. **ASSUMPTION**: The `strands_decider.modeling.StrandsDeciderModel` API exists and works
   as documented. We will also support the HTTP server mode as a fallback.
   If the Python API differs at runtime, we fall back to HTTP client to local server.

2. **ASSUMPTION**: `event.agent.model` assignment in BeforeModelInvocationEvent works
   for swapping models mid-loop. If not, we fall back to wrapping two separate
   BedrockModel instances and calling them directly.

3. **Mock mode**: We will mock both the decider (random confidence with configurable
   bias) and Bedrock (echo responses with fake token counts) for zero-cost testing.

4. **Model IDs**: Will use environment variables. Likely defaults for demo:
   - Frontier: `us.anthropic.claude-3-7-sonnet-20250219-v1:0`
   - Small: `us.anthropic.claude-3-haiku-20240307-v1:0`
   These are NOT hardcoded - just suggested in .env.example.
