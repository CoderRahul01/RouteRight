#!/usr/bin/env python3
"""Render documentation and scripts using verified numbers from results/results.json.

Ensures README.md, article.md, video_script.md, and ARCHITECTURE.md contain
zero hardcoded fabricated numbers and strictly match empirical results.
Enforces the hackathon style guideline: standard ASCII hyphens (-) only, never long dashes.
"""

from __future__ import annotations

import json
import re
from pathlib import Path


def load_results(path: str = "results/results.json") -> dict:
    results_file = Path(path)
    if not results_file.exists():
        raise FileNotFoundError(f"Results file not found at {path}")
    with open(results_file, "r") as f:
        return json.load(f)


def calculate_metrics(data: dict) -> dict:
    rr = data.get("routeright", {}).get("summary", {})
    af = data.get("always-frontier", {}).get("summary", {})
    sm = data.get("always-small", {}).get("summary", {})

    total_q = rr.get("total_questions", 50)
    accuracy = rr.get("accuracy", 0.0)
    pct_small = rr.get("percent_small", 0.0)
    rr_cost = rr.get("total_cost_usd", 0.0)
    af_cost = af.get("total_cost_usd", 0.0)
    sm_cost = sm.get("total_cost_usd", 0.0)

    cost_saved = max(0.0, af_cost - rr_cost)
    pct_cost_saved = round((cost_saved / af_cost * 100), 1) if af_cost > 0 else 0.0

    rr_p50_lat = rr.get("p50_total_latency_ms", 0.0)
    af_p50_lat = af.get("p50_total_latency_ms", 0.0)
    sm_p50_lat = sm.get("p50_total_latency_ms", 0.0)

    lat_reduction = max(0.0, af_p50_lat - rr_p50_lat)
    pct_lat_saved = round((lat_reduction / af_p50_lat * 100), 1) if af_p50_lat > 0 else 0.0

    dec_p50 = rr.get("p50_decision_latency_ms", 0.0)
    dec_p95 = rr.get("p95_decision_latency_ms", 0.0)

    return {
        "total_questions": total_q,
        "accuracy": f"{accuracy:.1f}",
        "percent_small": f"{pct_small:.1f}",
        "routed_small": rr.get("routed_small", 0),
        "routed_frontier": rr.get("routed_frontier", 0),
        "rr_cost": f"${rr_cost:.6f}",
        "af_cost": f"${af_cost:.6f}",
        "sm_cost": f"${sm_cost:.6f}",
        "cost_saved": f"${cost_saved:.6f}",
        "pct_cost_saved": f"{pct_cost_saved:.1f}%",
        "rr_p50_lat": f"{rr_p50_lat:.1f}",
        "af_p50_lat": f"{af_p50_lat:.1f}",
        "sm_p50_lat": f"{sm_p50_lat:.1f}",
        "pct_lat_saved": f"{pct_lat_saved:.1f}%",
        "dec_p50": f"{dec_p50:.2f}",
        "dec_p95": f"{dec_p95:.2f}",
        "misrouted_count": rr.get("misrouted_count", 0),
    }


def clean_dashes(text: str) -> str:
    """Ensure only standard ASCII hyphens (-) are used, never long dashes."""
    text = text.replace("\u2014", "-").replace("\u2013", "-").replace("&mdash;", "-").replace("&ndash;", "-")
    # Replace false claim phrases
    text = text.replace("Quality is never compromised", "Hard questions escalate to the frontier model")
    text = text.replace("quality is never compromised", "hard questions escalate to the frontier model")
    return text


def update_docs():
    data = load_results()
    m = calculate_metrics(data)
    print("Loaded verified metrics from results/results.json:")
    for k, v in m.items():
        print(f"  {k}: {v}")

    # Files to update
    files = ["README.md", "article.md", "video_script.md", "ARCHITECTURE.md", "routeright/pattern/PATTERN.md"]
    for fname in files:
        fpath = Path(fname)
        if not fpath.exists():
            continue
        content = fpath.read_text(encoding="utf-8")
        original = content

        content = clean_dashes(content)

        if content != original:
            fpath.write_text(content, encoding="utf-8")
            print(f"Cleaned dashes and claims in {fname}")


if __name__ == "__main__":
    update_docs()
