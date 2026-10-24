"""FastAPI backend for RouteRight demo UI."""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from routeright.config import RouterConfig
from routeright.router import RouteRightRouter

# ---------------------------------------------------------------------------
# Setup & Logging
# ---------------------------------------------------------------------------

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger("routeright.server")

app = FastAPI(title="RouteRight", description="Model routing demo with Strands Decider 2B")

config = RouterConfig()

# Runtime initialization
# Runtime code never uses mocks by default. Fakes live in tests/fakes/ and are
# only loaded if ROUTERIGHT_MOCK_MODE=true is explicitly set for testing.
if config.mock_mode:
    logger.warning("ROUTERIGHT_MOCK_MODE=true is set: running in simulated mode with synthetic fakes.")
    from tests.fakes.decider import MockDeciderClient
    from tests.fakes.bedrock import MockBedrockClient
    decider = MockDeciderClient(randomize=True, seed=42)
    bedrock = MockBedrockClient(seed=99)
else:
    from routeright.decider import DeciderClient
    decider = DeciderClient(
        model_id=config.decider_model_id,
        device=config.decider_device,
        server_url=config.decider_url,
    )
    # Bedrock client will be invoked in real mode or decision-only mode
    bedrock = None

router = RouteRightRouter(decider=decider, config=config)


# ---------------------------------------------------------------------------
# Request / Response models (Zero personal data collected)
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    message: str


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
    is_simulated: bool = False


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


@app.get("/api/status")
async def get_status():
    """Get RouteRight system status, health, and configuration."""
    health_info = decider.check_health() if hasattr(decider, "check_health") else {"status": "ok"}
    return {
        "status": "online",
        "is_simulated": bool(config.mock_mode),
        "decision_only": bool(config.decision_only),
        "architecture": "Strands Decider 2B + Amazon Bedrock",
        "decider_model": config.decider_model_id,
        "decider_device": config.decider_device,
        "decider_health": health_info,
        "last_decision_latency_ms": getattr(decider, "last_latency_ms", 0.0),
        "license": "MIT",
        "host": config.host,
        "port": config.port,
        "decider_url": config.decider_url,
    }


# ---------------------------------------------------------------------------
# Cost Safety Guards: Rate Limiting & Daily USD Cap
# ---------------------------------------------------------------------------

from fastapi import Request

REQUEST_HISTORY: dict[str, list[float]] = {}
RATE_LIMIT_PER_MINUTE = 60


def is_rate_limited(client_ip: str) -> bool:
    """Check per-IP sliding window rate limit."""
    now = time.time()
    history = REQUEST_HISTORY.setdefault(client_ip, [])
    REQUEST_HISTORY[client_ip] = [t for t in history if now - t < 60]
    if len(REQUEST_HISTORY[client_ip]) >= RATE_LIMIT_PER_MINUTE:
        return True
    REQUEST_HISTORY[client_ip].append(now)
    return False


@app.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest, request: Request):
    """Process a chat message through the router with strict cost safety."""
    client_ip = request.client.host if request.client else "127.0.0.1"
    if is_rate_limited(client_ip):
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded: maximum 60 requests per minute per IP.",
        )

    start = time.perf_counter()

    # Route the decision via Decider 2B
    model_id, decider_result = router.route(req.message)

    # Check daily USD cap to protect user budget
    current_spend = router.get_savings_summary().get("actual_cost_usd", 0.0)
    cap_reached = current_spend >= config.daily_usd_cap

    # Run inference: either simulated, decision-only, or real Bedrock
    if config.mock_mode:
        inference = bedrock.invoke(model_id, req.message, config.max_tokens)
        response_text = inference.text
        tokens_in = inference.tokens_in
        tokens_out = inference.tokens_out
    elif config.decision_only:
        response_text = (
            f"[Decision-Only Mode] RouteRight routed this prompt to '{decider_result.choice}' "
            f"({model_id}) with {decider_result.confidence * 100:.1f}% confidence in "
            f"{decider_result.latency_ms:.1f}ms. No Bedrock API call made ($0.00 spent)."
        )
        tokens_in = len(req.message) // 4
        tokens_out = 35
    elif cap_reached:
        logger.warning("ROUTERIGHT_DAILY_USD_CAP ($%.2f) reached; disabling Bedrock calls.", config.daily_usd_cap)
        response_text = (
            f"[Daily Budget Cap Reached: ${config.daily_usd_cap:.2f}] Bedrock API calls paused to protect your budget. "
            f"RouteRight routed this prompt to '{decider_result.choice}' ({model_id}) with "
            f"{decider_result.confidence * 100:.1f}% confidence in {decider_result.latency_ms:.1f}ms."
        )
        tokens_in = len(req.message) // 4
        tokens_out = 35
    else:
        # Check if AWS Bedrock credentials exist or run in decision-only mode
        try:
            import boto3
            client = boto3.client("bedrock-runtime", region_name=config.aws_region)
            b_start = time.perf_counter()
            resp = client.converse(
                modelId=model_id,
                messages=[{"role": "user", "content": [{"text": req.message}]}],
                inferenceConfig={"maxTokens": config.max_tokens},
            )
            b_elapsed = (time.perf_counter() - b_start) * 1000
            response_text = resp["output"]["message"]["content"][0]["text"]
            usage = resp.get("usage", {})
            tokens_in = usage.get("inputTokens", len(req.message) // 4)
            tokens_out = usage.get("outputTokens", len(response_text) // 4)
        except Exception as exc:
            logger.info("Bedrock inference skipped (%s); running in decision-only mode.", exc)
            response_text = (
                f"[Decision-Only Mode] RouteRight routed this prompt to '{decider_result.choice}' "
                f"({model_id}) with {decider_result.confidence * 100:.1f}% confidence in "
                f"{decider_result.latency_ms:.1f}ms. No Bedrock API call made."
            )
            tokens_in = len(req.message) // 4
            tokens_out = 40

    total_ms = (time.perf_counter() - start) * 1000

    # Record the decision in memory
    router.record_decision(
        user_message=req.message,
        model_id=model_id,
        decider_result=decider_result,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        total_latency_ms=total_ms,
        response_text=response_text,
    )

    cost_usd = router.estimate_cost(model_id, tokens_in, tokens_out)

    return ChatResponse(
        response=response_text,
        route=decider_result.choice,
        confidence=decider_result.confidence,
        decision_latency_ms=decider_result.latency_ms,
        model_used=model_id,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        estimated_cost_usd=cost_usd,
        total_latency_ms=round(total_ms, 2),
        probabilities=decider_result.probabilities,
        question=req.message,
        is_simulated=bool(config.mock_mode),
    )


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
        from routeright.decider import DeciderResult
        from routeright.router import RouteRightRouter, load_pricing

        items = load_benchmark("data/benchmark.jsonl")
        modes = ["routeright", "always-frontier", "always-small"]
        total_steps = len(modes) * len(items)
        current_step = 0
        all_results = {}
        pricing = load_pricing()

        # If in mock mode, use fake client; otherwise use configured decider
        if config.mock_mode:
            from tests.fakes.decider import MockDeciderClient
            from tests.fakes.bedrock import MockBedrockClient
            bench_decider = MockDeciderClient(randomize=True, seed=42)
            bench_bedrock = MockBedrockClient(seed=123)
        else:
            bench_decider = decider
            bench_bedrock = None

        bench_router = RouteRightRouter(decider=bench_decider, config=config)

        for mode in modes:
            results = []
            decision_latencies = []
            total_latencies = []
            total_cost = 0.0
            correct = 0
            misrouted = []

            for i, item in enumerate(items):
                current_step += 1
                question = item["question"]
                label = item["label"]

                if mode == "routeright":
                    model_id, decider_res = bench_router.route(question)
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

                if bench_bedrock is not None:
                    inf = bench_bedrock.invoke(model_id, question, config.max_tokens)
                    tokens_in = inf.tokens_in
                    tokens_out = inf.tokens_out
                    inf_lat = inf.latency_ms
                else:
                    # Decision-only or token approximation for benchmark display
                    tokens_in = len(question) // 4 + 10
                    tokens_out = 35 if model_id == config.small_model_id else 65
                    inf_lat = 45.0 if model_id == config.small_model_id else 180.0

                total_ms = decider_res.latency_ms + inf_lat
                total_latencies.append(round(total_ms, 2))

                m_pricing = pricing.get(model_id, {})
                cost = (
                    m_pricing.get("input_per_1k", 0.0) * (tokens_in / 1000)
                    + m_pricing.get("output_per_1k", 0.0) * (tokens_out / 1000)
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
                    "inference_latency_ms": inf_lat,
                    "total_latency_ms": round(total_ms, 2),
                    "tokens_in": tokens_in,
                    "tokens_out": tokens_out,
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
                await asyncio.sleep(0.01)

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

        # IMPORTANT: If ROUTERIGHT_MOCK_MODE=true is set, NEVER write to results/
        if not config.mock_mode:
            results_path = Path("results/results.json")
            summary_path = Path("results/summary.md")
            results_path.parent.mkdir(exist_ok=True)
            with open(results_path, "w") as f:
                json.dump(all_results, f, indent=2)
            summary_md = generate_summary_md(all_results)
            with open(summary_path, "w") as f:
                f.write(summary_md)
        else:
            logger.info("Mock mode active: skipping write to results/ directory.")

        complete_msg = {
            "type": "complete",
            "results": all_results,
            "is_simulated": bool(config.mock_mode),
        }
        yield f"data: {json.dumps(complete_msg)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.post("/api/benchmark")
async def run_benchmark_endpoint():
    """Run the benchmark and return results (synchronous cached fallback)."""
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
