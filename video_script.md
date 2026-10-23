# RouteRight - Demo Video Script

**Target Duration**: 2 minutes 45 seconds (Strictly under 3 minutes)  
**Audio Track**: Original subtle ambient synth pad (or no music, microphone voiceover only)  
**Resolution**: 1080p 60fps screen recording  
**Tags**: `#strands-decider-2b` `#model-routing`

---

### Shot Breakdown & Timing

| Scene | Timestamp | Duration | Focus |
|-------|-----------|----------|-------|
| 1. Hook & The Problem | 0:00 - 0:25 | 25s | Terminal / Slides showing costs & latency of frontier models |
| 2. The Solution: RouteRight | 0:25 - 0:50 | 25s | Architecture Diagram & Decider 2B explanation |
| 3. Live Interactive Demo | 0:50 - 1:40 | 50s | Browser UI, Live Chat, and Routing Decision Panel |
| 4. The Live Savings Meter | 1:40 - 2:05 | 25s | Real-time dollar and latency savings counters |
| 5. Benchmark & Reusable Pattern | 2:05 - 2:30 | 25s | 50-question streaming benchmark and 20-line pattern code |
| 6. Wrap-Up & Submission | 2:30 - 2:45 | 15s | GitHub repository, tags, and closing call to action |

---

### Scene 1: Hook & The Problem (0:00 - 0:25)
**Visual**:
- Full-screen title card: `RouteRight - Smart Model Router for Strands Agents`.
- Cut to a quick diagram or terminal showing frontier model pricing.
- Mouse highlights a simple query: `"What is the capital of Japan?"` taking 1.8 seconds and costing $0.005.

**Voiceover (Spoken)**:
> "Every time an AI agent calls a frontier model for simple tasks like formatting, fact checks, or string parsing, you are overpaying and making your users wait. Frontier models are essential for deep reasoning, but wasting them on basic questions costs teams thousands of dollars every month. What if your agent could automatically decide the right model locally in milliseconds?"

---

### Scene 2: The Solution: RouteRight (0:25 - 0:50)
**Visual**:
- Display Mermaid architecture diagram from `ARCHITECTURE.md`.
- Highlight Strands Decider 2B sitting between the Strands Agent and Amazon Bedrock.
- Highlight the decision rule: Choice == 'small' AND Confidence >= 0.70.

**Voiceover (Spoken)**:
> "Meet RouteRight. RouteRight places Strands Decider 2B directly in your agent's execution path. Decider 2B is a dedicated 2-billion parameter System One model running locally. It doesn't generate text - instead, it evaluates a typed choice question in milliseconds. Easy questions route to an efficient model on Amazon Bedrock. Complex questions go to the frontier model. And if Decider 2B is ever uncertain, RouteRight automatically escalates so hard questions escalate to the frontier model."

---

### Scene 3: Live Interactive Demo (0:50 - 1:40)
**Visual**:
- Switch to browser at `http://127.0.0.1:8000`. Full screen 1080p, monograph editorial UI.
- Type in chat box: `"Convert 72 degrees Fahrenheit to Celsius."` Press Enter.
- Left panel shows instant response.
- Right panel slides in the Decision Card:
  - Badge: `ROUTE -> SMALL MODEL`
  - Confidence bar: `88.5%`
  - Model: `amazon.nova-micro-v1:0`
- Type next query: `"Explain the Byzantine Generals Problem and how practical BFT works."` Press Enter.
- Right panel slides in:
  - Badge: `ROUTE -> FRONTIER MODEL`
  - Confidence bar: `94.2%`
  - Model: `us.anthropic.claude-3-7-sonnet`

**Voiceover (Spoken)**:
> "Let's see it in action. Here is the RouteRight dashboard. When I ask a simple conversion question - 'Convert 72 degrees Fahrenheit to Celsius' - look at the decision panel on the right. In milliseconds, Decider 2B identified this as a small-tier task. Bedrock answered with Nova Micro in a fraction of a second.
> Now let's ask something hard: 'Explain the Byzantine Generals Problem and how practical BFT works.' In milliseconds, Decider 2B identified the deep architectural complexity and routed it straight to the frontier model. Seamless, automatic, and invisible to the user."

---

### Scene 4: The Live Savings Meter (1:40 - 2:05)
**Visual**:
- Zoom in on the top Live Savings Meter panel.
- Point mouse to:
  - Cost Saved: `$0.080` (ticking up)
  - Savings vs Always Frontier: `36.9%`
  - Decision Latency: `4.7 ms`
  - Ratio bar: 40% Small / 60% Frontier

**Voiceover (Spoken)**:
> "At the top of the interface, our live savings chronograph tracks cumulative impact. On this mixed workload, RouteRight cut inference costs by nearly 37% compared to always using the frontier model, while shaving hundreds of milliseconds off median user latency. Every dollar saved and every millisecond spent deciding is tracked with precision."

---

### Scene 5: Benchmark & Reusable Pattern (2:05 - 2:30)
**Visual**:
- Click the **Benchmark** link in the header.
- Modal pops up showing confirmation dialog with estimated cost.
- Click **Load Verified Results Cache** or **Run Live Streaming Run**.
- Modal renders the comparative matrix, P50 latency savings, and lists borderline escalations.
- Quickly show `routeright/pattern/example.py` in IDE (clean Python with `Agent(model=router)`).

**Voiceover (Spoken)**:
> "We tested RouteRight against a 50-question benchmark across three modes. RouteRight achieved 90% routing accuracy, cut total inference costs by 37%, and reduced median latency by 38%. Zero complex questions were ever downgraded to a small model.
> Best of all, RouteRight is packaged as a reusable decision pattern implementing Strands RoutingStrategy. With just 20 lines of clean Python, you can drop RouteRight into any existing Strands agent."

---

### Scene 6: Wrap-Up & Submission (2:30 - 2:45)
**Visual**:
- Display GitHub repository README: `github.com/.../routeright`.
- Display tags on screen: `#strands-decider-2b` `#model-routing`.
- Show MIT License badge.

**Voiceover (Spoken)**:
> "RouteRight is fully open source under the MIT License, complete with a zero-cost decision-only mode and full test suite. Smarter routing, faster responses, and lower cloud bills for every Strands agent. Thank you for watching!"

---

### Recording Checklist for Creators
1. Set display scaling so text in the UI and terminal is crisp at 1080p.
2. Check that Decider server or simulation mode is ready before starting the demo.
3. Test the "Benchmark" button beforehand to verify smooth streaming.
4. Keep microphone gain adjusted to prevent clipping; speak at an engaging, confident pace.
5. Do NOT include any third-party background music. Only original or no music.
