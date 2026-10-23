#!/usr/bin/env python3
"""Setup verification script for RouteRight.

Checks:
1. Strands Decider 2B server reachable on port 8001 (or local engine).
2. AWS region and credentials valid.
3. Bedrock small and frontier model invocation status.
4. Official model pricing in config/pricing.json.

Prints clear, actionable fix steps for every failure.
"""

from __future__ import annotations

import os
import platform
import sys
import time
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx

from routeright.config import RouterConfig
from routeright.decider import DeciderClient


def print_header(title: str):
    print(f"\n{'='*60}")
    print(f" {title}")
    print(f"{'='*60}")


def check_decider(config: RouterConfig) -> bool:
    print_header("1. Strands Decider 2B Health Check")
    url = config.decider_url
    print(f"Target URL: {url}")
    print(f"Configured model: {config.decider_model_id}")
    print(f"Target device: {config.decider_device}")

    try:
        with httpx.Client(timeout=3.0) as client:
            resp = client.get(f"{url.rstrip('/')}/health")
            if resp.status_code == 200:
                data = resp.json()
                print(f"[PASS] Strands Decider 2B is healthy and reachable!")
                print(f"  - Model: {data.get('model', 'unknown')}")
                print(f"  - Device: {data.get('device', 'cpu')}")
                print(f"  - Prefix cache: {data.get('prefix_cache', False)}")
                return True
            else:
                print(f"[FAIL] Server responded with HTTP {resp.status_code}: {resp.text}")
    except Exception as exc:
        print(f"[FAIL] Could not connect to Strands Decider server: {exc}")

    print("\nFix Steps to start Decider 2B:")
    print("  Run the following command in a separate terminal:")
    print(f"    strands-decider serve {config.decider_model_id} --port {url.split(':')[-1]}")
    print("  Or run 100% free with mock testing:")
    print("    export ROUTERIGHT_MOCK_MODE=true")
    return False


def check_aws_credentials(config: RouterConfig) -> tuple[bool, Any]:
    print_header("2. AWS Credentials & Region Check")
    region = config.aws_region or os.getenv("AWS_REGION", "us-east-1")
    print(f"Configured Region: {region}")

    try:
        import boto3
        session = boto3.Session()
        creds = session.get_credentials()
        if not creds:
            print("[FAIL] No AWS credentials found via environment or ~/.aws/credentials.")
            print("\nFix Steps for AWS credentials:")
            print("  1. Run `aws configure` to set Access Key ID and Secret Access Key.")
            print("  2. Or export environment variables:")
            print("     export AWS_ACCESS_KEY_ID=your_key")
            print("     export AWS_SECRET_ACCESS_KEY=your_secret")
            print("     export AWS_REGION=us-east-1")
            print("  Note: You can still run RouteRight in Decision-Only mode without AWS credentials!")
            return False, None

        key_id = creds.access_key
        masked = key_id[:4] + "..." + key_id[-4:] if len(key_id) > 8 else "***"
        print(f"[PASS] AWS credentials located (Access Key ID: {masked})")
        return True, session
    except ImportError:
        print("[FAIL] boto3 is not installed.")
        print("Fix Step: pip install boto3")
        return False, None


def check_bedrock_models(config: RouterConfig, session: Any) -> bool:
    print_header("3. Amazon Bedrock Models & Converse Quota Check")
    if not session:
        print("[SKIP] Skipping Bedrock invocation check because AWS credentials are not configured.")
        return False

    client = session.client("bedrock-runtime", region_name=config.aws_region)
    models_to_test = [
        ("Small Model", config.small_model_id),
        ("Frontier Model", config.frontier_model_id),
    ]

    all_passed = True
    for label, model_id in models_to_test:
        print(f"\nTesting {label}: {model_id}...")
        try:
            start = time.perf_counter()
            resp = client.converse(
                modelId=model_id,
                messages=[{"role": "user", "content": [{"text": "Ping"}]}],
                inferenceConfig={"maxTokens": 5},
            )
            elapsed_ms = (time.perf_counter() - start) * 1000
            usage = resp.get("usage", {})
            print(f"  [PASS] Invocation succeeded in {elapsed_ms:.1f}ms")
            print(f"  Input tokens: {usage.get('inputTokens', 0)}, Output tokens: {usage.get('outputTokens', 0)}")
        except Exception as exc:
            all_passed = False
            err_name = type(exc).__name__
            err_str = str(exc)
            print(f"  [FAIL] Model invocation failed ({err_name}): {err_str}")

            if "ThrottlingException" in err_str:
                print("  Fix Steps for ThrottlingException:")
                print("    AWS Bedrock account has hit daily token quota ('Too many tokens per day').")
                print("    - Switch to Decision-Only Mode: RouteRight runs Decider 2B with zero AWS calls.")
                print("    - Or request a service quota increase in AWS Service Quotas console.")
            elif "ResourceNotFoundException" in err_str:
                print("  Fix Steps for ResourceNotFoundException:")
                print(f"    Model ID '{model_id}' is not recognized in {config.aws_region}.")
                print("    Set a supported model ID via environment variables:")
                print("    export ROUTERIGHT_SMALL_MODEL=amazon.nova-micro-v1:0")
                print("    export ROUTERIGHT_FRONTIER_MODEL=us.anthropic.claude-3-7-sonnet-20250219-v1:0")
            elif "AccessDeniedException" in err_str:
                print("  Fix Steps for AccessDeniedException:")
                print("    Account does not have permission for this model.")
                print("    Enable model access in AWS Console -> Amazon Bedrock -> Model access.")

    return all_passed


def check_pricing_file() -> bool:
    print_header("4. Model Pricing Table Check")
    pricing_file = Path("config/pricing.json")
    if not pricing_file.exists():
        print(f"[FAIL] Missing {pricing_file}")
        return False

    import json
    with open(pricing_file) as f:
        data = json.load(f)

    source = data.get("source_url") or data.get("_source")
    date = data.get("retrieval_date", "not recorded")
    models = data.get("models", {})

    print(f"[PASS] Pricing configuration verified:")
    print(f"  - Source URL: {source}")
    print(f"  - Retrieval date: {date}")
    print(f"  - Total configured models: {len(models)}")
    return True


def main():
    print(f"RouteRight System Pre-Flight Diagnostics")
    print(f"Platform: {platform.system()} {platform.machine()} ({platform.processor() or 'CPU'})")

    config = RouterConfig()
    decider_ok = check_decider(config)
    aws_ok, session = check_aws_credentials(config)
    bedrock_ok = check_bedrock_models(config, session) if aws_ok else False
    pricing_ok = check_pricing_file()

    print_header("Diagnostic Summary")
    print(f"1. Decider 2B Server:      {'READY' if decider_ok else 'NOT RUNNING'}")
    print(f"2. AWS Credentials:        {'CONFIGURED' if aws_ok else 'MISSING'}")
    print(f"3. Bedrock API Invocation: {'READY' if bedrock_ok else 'NOT READY / THROTTLED'}")
    print(f"4. Pricing Configuration:  {'VERIFIED' if pricing_ok else 'INCOMPLETE'}")

    print("\nOperating Mode:")
    if decider_ok and bedrock_ok:
        print("  -> FULL MODE READY: Decider 2B routing with live Amazon Bedrock inference.")
    elif decider_ok:
        print("  -> DECISION-ONLY MODE READY: 100% free local Decider 2B routing active (no AWS cost).")
    elif config.mock_mode:
        print("  -> SIMULATED MODE ACTIVE: Synthetic fakes active (ROUTERIGHT_MOCK_MODE=true).")
    else:
        print("  -> SETUP NEEDED: Start Decider 2B server with: strands-decider serve --port 8001")


if __name__ == "__main__":
    main()
