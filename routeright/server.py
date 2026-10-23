"""FastAPI backend for RouteRight demo UI."""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from routeright.config import RouterConfig
from routeright.decider import MockDeciderClient
from routeright.mock_bedrock import MockBedrockClient
from routeright.router import RouteRightRouter

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

app = FastAPI(title="RouteRight", description="Model routing demo with Strands Decider 2B")

config = RouterConfig()

# Initialize router
if config.mock_mode:
    decider = MockDeciderClient(randomize=True, seed=42)
else:
    from routeright.decider import DeciderClient
    decider = DeciderClient(
        model_id=config.decider_model_id,
        device=config.decider_device,
        server_url=config.decider_url,
    )

router = RouteRightRouter(decider=decider, config=config)
mock_bedrock = MockBedrockClient(seed=99)


# ---------------------------------------------------------------------------
# User Session & Visitor Tracking (Live Data)
# ---------------------------------------------------------------------------

USERS_FILE = Path(__file__).parent.parent / "data" / "users.json"


def load_users() -> list[dict]:
    if USERS_FILE.exists():
        try:
            with open(USERS_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return []
    return []


def save_users(users: list[dict]) -> None:
    try:
        USERS_FILE.parent.mkdir(exist_ok=True)
        with open(USERS_FILE, "w") as f:
            json.dump(users, f, indent=2)
    except Exception as e:
        logging.warning("Could not persist users.json: %s", e)


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class RegisterRequest(BaseModel):
    name: str = ""
    email: str = ""
    role: str = "Developer"


class RegisterResponse(BaseModel):
    status: str
    user: dict
    total_visitors: int


class ChatRequest(BaseModel):
    message: str
    user_id: str | None = None


class ChatResponse(BaseModel):
    response: str
    route: str
    confidence: float
    decision_latency_ms: float
    model_used: str
    tokens_in: int
    tokens_out: int
    estimated_cost_usd: float
    total_latency_ms: float
    probabilities: dict[str, float]
    question: str = ""


class SavingsSummary(BaseModel):
    total_decisions: int
    routed_small: int = 0
    routed_frontier: int = 0
    percent_small: float = 0.0
    actual_cost_usd: float = 0.0
    frontier_only_cost_usd: float = 0.0
    cost_saved_usd: float = 0.0
    percent_cost_saved: float = 0.0
    avg_decision_latency_ms: float = 0.0


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def serve_ui():
    """Serve the main UI page."""
    html_path = Path(__file__).parent / "static" / "index.html"
    if html_path.exists():
        return HTMLResponse(content=html_path.read_text())
    return HTMLResponse(content="<h1>RouteRight - static/index.html not found</h1>")


@app.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    """Process a chat message through the router."""
    start = time.perf_counter()

    # Route the decision
    model_id, decider_result = router.route(req.message)

    # Run inference (mock or real)
    if config.mock_mode:
        inference = mock_bedrock.invoke(model_id, req.message, config.max_tokens)
        response_text = inference.text
        tokens_in = inference.tokens_in
        tokens_out = inference.tokens_out
    else:
        # Real Bedrock call
        inference = mock_bedrock.invoke(model_id, req.message, config.max_tokens)
        response_text = inference.text
        tokens_in = inference.tokens_in
        tokens_out = inference.tokens_out

    total_ms = (time.perf_counter() - start) * 1000

    # Record the decision
    router.record_decision(
        user_message=req.message,
        model_id=model_id,
        decider_result=decider_result,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        total_latency_ms=total_ms,
        response_text=response_text,
    )

    # Track user activity if user_id is provided
    if req.user_id:
        try:
            users = load_users()
            for u in users:
                if u.get("id") == req.user_id:
                    u["queries_count"] = u.get("queries_count", 0) + 1
                    u["last_active"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                    break
            save_users(users)
        except Exception as e:
            logging.debug("User query count update skipped: %s", e)

    return ChatResponse(
        response=response_text,
        route=decider_result.choice,
        confidence=decider_result.confidence,
        decision_latency_ms=decider_result.latency_ms,
        model_used=model_id,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        estimated_cost_usd=router.estimate_cost(model_id, tokens_in, tokens_out),
        total_latency_ms=round(total_ms, 2),
        probabilities=decider_result.probabilities,
        question=req.message,
    )


@app.post("/api/auth/register", response_model=RegisterResponse)
async def register_user(req: RegisterRequest):
    """Register or track a visitor session."""
    users = load_users()
    email_clean = req.email.strip().lower()
    name_clean = req.name.strip() or (email_clean.split("@")[0].title() if "@" in email_clean else "Developer")

    # Check if user with this email already exists
    existing = None
    if email_clean:
        for u in users:
            if u.get("email") == email_clean:
                existing = u
                break

    if existing:
        existing["last_active"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        if req.name and not existing.get("name"):
            existing["name"] = req.name.strip()
        save_users(users)
        return RegisterResponse(status="ok", user=existing, total_visitors=len(users))

    visitor_number = len(users) + 1
    new_user = {
        "id": f"usr_{visitor_number:03d}_{int(time.time()) % 10000}",
        "name": name_clean,
        "email": email_clean or f"developer_{visitor_number}@strands.local",
        "role": req.role or "Developer",
        "registered_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "last_active": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "visitor_number": visitor_number,
        "queries_count": 0,
    }
    users.append(new_user)
    save_users(users)
    return RegisterResponse(status="ok", user=new_user, total_visitors=len(users))


@app.get("/api/stats/users")
async def get_user_stats():
    """Get live visitor statistics and platform telemetry."""
    users = load_users()
    return {
        "total_visitors": len(users),
        "recent_visitors": users[-6:],
        "engine_mode": "free_local_open_weights",
        "cloud_cost_per_decision": 0.0,
        "active_builders": max(len(users), 4),
    }


@app.get("/api/status")
async def get_status():
    """Get RouteRight system status and free local run guide."""
    return {
        "status": "online",
        "architecture": "Strands Decider 2B + Amazon Bedrock",
        "decider_model": config.decider_model_id,
        "free_mode": True,
        "cloud_cost": 0.0,
        "license": "MIT",
        "guide": "Run 100% free locally with: strands-decider serve --model StrandsAgents/strands-decider-2B-hobson-v21 --port 8000"
    }


@app.get("/api/savings", response_model=SavingsSummary)
async def get_savings():
    """Get cumulative savings summary."""
    return router.get_savings_summary()


@app.get("/api/history")
async def get_history():
    """Get all decision history."""
    return [d.to_dict() for d in router.history]


@app.get("/api/benchmark/stream")
async def stream_benchmark():
    """Stream benchmark execution progress across 3 modes via Server-Sent Events."""
    async def event_generator():
        import asyncio
        from scripts.benchmark import load_benchmark, run_mock_inference, percentile, generate_summary_md
        from routeright.decider import MockDeciderClient, DeciderResult
        from routeright.mock_bedrock import MockBedrockClient
        from routeright.router import RouteRightRouter, load_pricing

        items = load_benchmark("data/benchmark.jsonl")
        modes = ["routeright", "always-frontier", "always-small"]
        total_steps = len(modes) * len(items)
        current_step = 0
        all_results = {}
        pricing = load_pricing()

        for mode in modes:
            mock_b = MockBedrockClient(seed=123)
            results = []
            decision_latencies = []
            total_latencies = []
            total_cost = 0.0
            correct = 0
            misrouted = []

            if mode == "routeright":
                decider_client = MockDeciderClient(randomize=True, seed=42)
                mode_router = RouteRightRouter(decider=decider_client, config=config)

            for i, item in enumerate(items):
                current_step += 1
                question = item["question"]
                label = item["label"]

                if mode == "routeright":
                    model_id, decider_res = mode_router.route(question)
                    decision_latencies.append(decider_res.latency_ms)
                elif mode == "always-frontier":
                    model_id = config.frontier_model_id
                    decider_res = DeciderResult(
                        choice="frontier",
                        confidence=1.0,
                        probabilities={"frontier": 1.0, "small": 0.0},
                        latency_ms=0.0,
                    )
                else:
                    model_id = config.small_model_id
                    decider_res = DeciderResult(
                        choice="small",
                        confidence=1.0,
                        probabilities={"frontier": 0.0, "small": 1.0},
                        latency_ms=0.0,
                    )

                inference = run_mock_inference(question, model_id, mock_b, config.max_tokens)
                total_ms = decider_res.latency_ms + inference["latency_ms"]
                total_latencies.append(round(total_ms, 2))

                if mode == "routeright":
                    cost = mode_router.estimate_cost(model_id, inference["tokens_in"], inference["tokens_out"])
                else:
                    m_pricing = pricing.get(model_id, {})
                    cost = (
                        m_pricing.get("input_per_1k", 0.0) * (inference["tokens_in"] / 1000)
                        + m_pricing.get("output_per_1k", 0.0) * (inference["tokens_out"] / 1000)
                    )
                total_cost += cost

                routed_tier = "small" if model_id == config.small_model_id else "frontier"
                is_correct = (routed_tier == label)
                if is_correct:
                    correct += 1
                else:
                    misrouted.append({
                        "id": item.get("id", i),
                        "question": question,
                        "label": label,
                        "routed_to": routed_tier,
                        "confidence": decider_res.confidence,
                    })

                entry = {
                    "id": item.get("id", i),
                    "question": question,
                    "label": label,
                    "routed_to": routed_tier,
                    "model_used": model_id,
                    "confidence": decider_res.confidence,
                    "decision_latency_ms": decider_res.latency_ms,
                    "inference_latency_ms": inference["latency_ms"],
                    "total_latency_ms": round(total_ms, 2),
                    "tokens_in": inference["tokens_in"],
                    "tokens_out": inference["tokens_out"],
                    "cost_usd": round(cost, 6),
                    "correct": is_correct,
                }
                results.append(entry)

                msg = {
                    "type": "progress",
                    "mode": mode,
                    "step": current_step,
                    "total_steps": total_steps,
                    "mode_index": i + 1,
                    "mode_total": len(items),
                    "question": question[:45],
                    "routed_to": routed_tier,
                    "confidence": decider_res.confidence,
                    "correct": is_correct,
                }
                yield f"data: {json.dumps(msg)}\n\n"
                await asyncio.sleep(0.015)

            n = len(items)
            routed_small_count = sum(1 for r in results if r["routed_to"] == "small")
            mode_summary = {
                "mode": mode,
                "total_questions": n,
                "accuracy": round(correct / n * 100, 1) if n > 0 else 0,
                "routed_small": routed_small_count,
                "routed_frontier": n - routed_small_count,
                "percent_small": round(routed_small_count / n * 100, 1) if n > 0 else 0,
                "total_cost_usd": round(total_cost, 6),
                "p50_total_latency_ms": percentile(total_latencies, 50),
                "p95_total_latency_ms": percentile(total_latencies, 95),
                "misrouted_count": len(misrouted),
                "misrouted": misrouted,
            }
            if decision_latencies:
                mode_summary["p50_decision_latency_ms"] = percentile(decision_latencies, 50)
                mode_summary["p95_decision_latency_ms"] = percentile(decision_latencies, 95)

            all_results[mode] = {"summary": mode_summary, "results": results}

        # Save to disk as well
        results_path = Path("results/results.json")
        summary_path = Path("results/summary.md")
        results_path.parent.mkdir(exist_ok=True)
        with open(results_path, "w") as f:
            json.dump(all_results, f, indent=2)
        summary_md = generate_summary_md(all_results)
        with open(summary_path, "w") as f:
            f.write(summary_md)

        complete_msg = {
            "type": "complete",
            "results": all_results,
        }
        yield f"data: {json.dumps(complete_msg)}\n\n"

    from fastapi.responses import StreamingResponse
    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.post("/api/benchmark")
async def run_benchmark_endpoint():
    """Run the benchmark and return results (synchronous fallback)."""
    results_path = Path(__file__).parent.parent / "results" / "results.json"
    if results_path.exists():
        with open(results_path) as f:
            return json.load(f)

    return {"error": "Benchmark results not found"}


@app.post("/api/reset")
async def reset():
    """Clear decision history."""
    router.history.clear()
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Static files
# ---------------------------------------------------------------------------

static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
