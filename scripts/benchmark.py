"""Benchmark script for RouteRight.

Runs three modes:
1. routeright - Decider 2B routes each question
2. always-frontier - every question goes to the frontier model
3. always-small - every question goes to the small model

Reports routing accuracy, latency percentiles, estimated cost, and misrouted questions.
Uses mock mode by default. Set ROUTERIGHT_MOCK_MODE=false for real Bedrock calls.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import statistics
import sys
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from routeright.config import RouterConfig
from routeright.decider import MockDeciderClient, DeciderResult
from routeright.mock_bedrock import MockBedrockClient
from routeright.router import RouteRightRouter


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------

CACHE_DIR = Path("cache")


def cache_key(question: str, model_id: str) -> str:
    h = hashlib.sha256(f"{model_id}::{question}".encode()).hexdigest()[:16]
    return h


def get_cached(question: str, model_id: str) -> dict | None:
    path = CACHE_DIR / f"{cache_key(question, model_id)}.json"
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return None


def set_cache(question: str, model_id: str, data: dict) -> None:
    CACHE_DIR.mkdir(exist_ok=True)
    path = CACHE_DIR / f"{cache_key(question, model_id)}.json"
    with open(path, "w") as f:
        json.dump(data, f)


# ---------------------------------------------------------------------------
# Benchmark runner
# ---------------------------------------------------------------------------

def load_benchmark(path: str = "data/benchmark.jsonl") -> list[dict]:
    items = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                items.append(json.loads(line))
    return items


def run_mock_inference(
    question: str,
    model_id: str,
    mock_bedrock: MockBedrockClient,
    max_tokens: int = 1024,
) -> dict:
    """Run inference via mock Bedrock (or cache)."""
    cached = get_cached(question, model_id)
    if cached:
        return cached

    resp = mock_bedrock.invoke(model_id, question, max_tokens)
    result = {
        "response": resp.text,
        "model_id": resp.model_id,
        "tokens_in": resp.tokens_in,
        "tokens_out": resp.tokens_out,
        "latency_ms": resp.latency_ms,
    }
    set_cache(question, model_id, result)
    return result


def percentile(values: list[float], p: int) -> float:
    if not values:
        return 0.0
    sorted_v = sorted(values)
    idx = int(len(sorted_v) * p / 100)
    idx = min(idx, len(sorted_v) - 1)
    return round(sorted_v[idx], 2)


def run_benchmark(
    items: list[dict],
    mode: str,
    config: RouterConfig,
    max_calls: int | None = None,
    progress_callback=None,
) -> dict:
    """Run benchmark in one of three modes: routeright, always-frontier, always-small."""

    mock_bedrock = MockBedrockClient(seed=123)
    results = []
    decision_latencies = []
    total_latencies = []
    total_cost = 0.0
    correct = 0
    misrouted = []

    if mode == "routeright":
        decider = MockDeciderClient(randomize=True, seed=42)
        router = RouteRightRouter(decider=decider, config=config)

    items_to_run = items[:max_calls] if max_calls else items

    for i, item in enumerate(items_to_run):
        question = item["question"]
        label = item["label"]

        start = time.perf_counter()

        if mode == "routeright":
            model_id, decider_result = router.route(question)
            decision_latencies.append(decider_result.latency_ms)
        elif mode == "always-frontier":
            model_id = config.frontier_model_id
            decider_result = DeciderResult(
                choice="frontier", confidence=1.0,
                probabilities={"frontier": 1.0, "small": 0.0},
                latency_ms=0.0,
            )
        else:  # always-small
            model_id = config.small_model_id
            decider_result = DeciderResult(
                choice="small", confidence=1.0,
                probabilities={"frontier": 0.0, "small": 1.0},
                latency_ms=0.0,
            )

        # Run inference
        inference = run_mock_inference(question, model_id, mock_bedrock, config.max_tokens)

        # End-to-end latency: decider decision time + model inference time
        total_ms = decider_result.latency_ms + inference["latency_ms"]
        total_latencies.append(round(total_ms, 2))

        # Cost estimation
        cost = router.estimate_cost(model_id, inference["tokens_in"], inference["tokens_out"]) \
            if mode == "routeright" else 0.0

        if mode != "routeright":
            from routeright.router import load_pricing
            pricing = load_pricing()
            model_pricing = pricing.get(model_id, {})
            cost = (
                model_pricing.get("input_per_1k", 0.0) * (inference["tokens_in"] / 1000)
                + model_pricing.get("output_per_1k", 0.0) * (inference["tokens_out"] / 1000)
            )

        total_cost += cost

        # Check accuracy
        routed_tier = "small" if model_id == config.small_model_id else "frontier"
        is_correct = routed_tier == label
        if is_correct:
            correct += 1
        else:
            misrouted.append({
                "id": item.get("id", i),
                "question": question,
                "label": label,
                "routed_to": routed_tier,
                "confidence": decider_result.confidence,
            })

        result_entry = {
            "id": item.get("id", i),
            "question": question,
            "label": label,
            "routed_to": routed_tier,
            "model_used": model_id,
            "confidence": decider_result.confidence,
            "decision_latency_ms": decider_result.latency_ms,
            "inference_latency_ms": inference["latency_ms"],
            "total_latency_ms": round(total_ms, 2),
            "tokens_in": inference["tokens_in"],
            "tokens_out": inference["tokens_out"],
            "cost_usd": round(cost, 6),
            "correct": is_correct,
        }
        results.append(result_entry)

        if progress_callback:
            progress_callback(i + 1, len(items_to_run), result_entry)

    # Summary stats
    n = len(items_to_run)
    routed_small_count = sum(1 for r in results if r["routed_to"] == "small")

    summary = {
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
        summary["p50_decision_latency_ms"] = percentile(decision_latencies, 50)
        summary["p95_decision_latency_ms"] = percentile(decision_latencies, 95)

    return {
        "summary": summary,
        "results": results,
    }


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def generate_summary_md(all_results: dict) -> str:
    lines = [
        "# RouteRight Benchmark Results\n",
        "## Mode Comparison\n",
        "| Metric | RouteRight | Always Frontier | Always Small |",
        "|--------|-----------|----------------|-------------|",
    ]

    modes = ["routeright", "always-frontier", "always-small"]
    summaries = {m: all_results[m]["summary"] for m in modes}

    metrics = [
        ("Accuracy (%)", "accuracy"),
        ("Routed Small (%)", "percent_small"),
        ("Total Cost (USD)", "total_cost_usd"),
        ("P50 Total Latency (ms)", "p50_total_latency_ms"),
        ("P95 Total Latency (ms)", "p95_total_latency_ms"),
    ]

    for label, key in metrics:
        row = f"| {label} |"
        for m in modes:
            val = summaries[m].get(key, "N/A")
            if isinstance(val, float):
                if "cost" in key.lower():
                    row += f" ${val:.6f} |"
                else:
                    row += f" {val} |"
            else:
                row += f" {val} |"
        lines.append(row)

    # Savings
    rr_cost = summaries["routeright"]["total_cost_usd"]
    frontier_cost = summaries["always-frontier"]["total_cost_usd"]
    if frontier_cost > 0:
        pct_saved = round((1 - rr_cost / frontier_cost) * 100, 1)
        cost_saved = round(frontier_cost - rr_cost, 6)
    else:
        pct_saved = 0
        cost_saved = 0

    lines.extend([
        "",
        "## Cost Savings vs Always-Frontier",
        f"- Cost saved: ${cost_saved:.6f} ({pct_saved}%)",
        f"- RouteRight cost: ${rr_cost:.6f}",
        f"- Always-frontier cost: ${frontier_cost:.6f}",
        "",
    ])

    # Decision latency (RouteRight only)
    rr = summaries["routeright"]
    if "p50_decision_latency_ms" in rr:
        lines.extend([
            "## Decision Latency (RouteRight - Decider 2B)",
            f"- P50: {rr['p50_decision_latency_ms']} ms",
            f"- P95: {rr['p95_decision_latency_ms']} ms",
            "",
        ])

    # Misrouted questions
    for mode in modes:
        misrouted = summaries[mode].get("misrouted", [])
        if misrouted:
            lines.extend([
                f"## Misrouted Questions - {mode}",
                "",
            ])
            for m in misrouted:
                lines.extend([
                    f"- **Q{m['id']}**: \"{m['question']}\"",
                    f"  - Label: {m['label']}, Routed to: {m['routed_to']}, Confidence: {m['confidence']:.3f}",
                    "",
                ])

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="RouteRight Benchmark")
    parser.add_argument("--max-calls", type=int, default=None, help="Max questions per mode")
    parser.add_argument("--data", default="data/benchmark.jsonl", help="Benchmark data file")
    parser.add_argument("--output-dir", default="results", help="Output directory")
    args = parser.parse_args()

    print("Loading benchmark data...")
    items = load_benchmark(args.data)
    print(f"Loaded {len(items)} questions")

    config = RouterConfig(mock_mode=True)

    all_results = {}
    for mode in ["routeright", "always-frontier", "always-small"]:
        print(f"\n{'='*60}")
        print(f"Running mode: {mode}")
        print(f"{'='*60}")

        def progress(current, total, entry):
            status = "correct" if entry["correct"] else "MISROUTED"
            print(
                f"  [{current}/{total}] {status} | "
                f"routed={entry['routed_to']} conf={entry['confidence']:.3f} | "
                f"Q: {entry['question'][:60]}..."
            )

        result = run_benchmark(
            items, mode, config,
            max_calls=args.max_calls,
            progress_callback=progress,
        )
        all_results[mode] = result

        s = result["summary"]
        print(f"\n  Accuracy: {s['accuracy']}%")
        print(f"  Routed small: {s['percent_small']}%")
        print(f"  Total cost: ${s['total_cost_usd']:.6f}")

    # Save results
    output_dir = Path(args.output_dir)
    output_dir.mkdir(exist_ok=True)

    with open(output_dir / "results.json", "w") as f:
        json.dump(all_results, f, indent=2)
    print(f"\nResults saved to {output_dir / 'results.json'}")

    summary_md = generate_summary_md(all_results)
    with open(output_dir / "summary.md", "w") as f:
        f.write(summary_md)
    print(f"Summary saved to {output_dir / 'summary.md'}")


if __name__ == "__main__":
    main()
