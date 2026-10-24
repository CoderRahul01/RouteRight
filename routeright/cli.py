"""RouteRight Command Line Interface.

One-command runner:
    routeright start       Start Decider server (port 8001) and Web UI (port 8000)
    routeright check       Run system diagnostics (Decider, AWS, Bedrock, pricing)
    routeright benchmark   Run 50-question empirical evaluation
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
import webbrowser
from pathlib import Path


def is_port_in_use(port: int) -> bool:
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) == 0


def cmd_check():
    from scripts.check_setup import main as check_main
    check_main()


def cmd_benchmark(args):
    from scripts.benchmark import main as bench_main
    sys.argv = ["benchmark.py"]
    if args.mock:
        sys.argv.append("--mock")
    if args.max_calls:
        sys.argv.extend(["--max-calls", str(args.max_calls)])
    bench_main()


def cmd_start(args):
    print("=" * 60)
    print(" RouteRight System Startup")
    print("=" * 60)

    # 1. Run diagnostic pre-flight
    if getattr(args, "decision_only", False):
        os.environ["ROUTERIGHT_DECISION_ONLY"] = "true"
        print("Mode: Decision-Only (100% free, zero AWS Bedrock charges).")

    from scripts.check_setup import check_decider, check_pricing_file
    from routeright.config import RouterConfig

    config = RouterConfig()
    decider_running = is_port_in_use(8001)

    # 2. Start Decider 2B server if not running and not in mock mode
    decider_proc = None
    if not decider_running and not config.mock_mode:
        print("\nStarting local Strands Decider 2B server on port 8001...")
        cmd = [
            sys.executable, "-m", "strands_decider", "serve",
            config.decider_model_id,
            "--port", "8001",
            "--host", "127.0.0.1",
        ]
        try:
            decider_proc = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            print("Decider server process spawned (PID: %d). Waiting for port 8001..." % decider_proc.pid)
            for _ in range(15):
                if is_port_in_use(8001):
                    print("Decider server is active and responding!")
                    break
                time.sleep(1.0)
        except Exception as exc:
            print(f"Could not automatically spawn strands-decider: {exc}")
            print("You can start it manually in a separate window:")
            print(f"  strands-decider serve {config.decider_model_id} --port 8001")
    elif decider_running:
        print("Strands Decider 2B already active on port 8001.")
    else:
        print("Running in simulated mode (ROUTERIGHT_MOCK_MODE=true).")

    # 3. Open browser after short delay
    url = f"http://{config.host}:{config.port}"
    if not args.no_browser:
        def open_browser():
            time.sleep(1.2)
            print(f"Opening browser at {url}...")
            webbrowser.open(url)

        import threading
        threading.Thread(target=open_browser, daemon=True).start()

    # 4. Start RouteRight FastAPI server on port 8000
    print(f"\nLaunching RouteRight Web Dashboard on {url}")
    print("Press Ctrl+C to stop.\n")

    try:
        import uvicorn
        uvicorn.run("routeright.server:app", host=config.host, port=config.port, log_level="info")
    finally:
        if decider_proc:
            print("\nShutting down Decider server...")
            decider_proc.terminate()


def main():
    parser = argparse.ArgumentParser(description="RouteRight CLI")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # start
    start_parser = subparsers.add_parser("start", help="Start Decider and RouteRight Web Console")
    start_parser.add_argument("--no-browser", action="store_true", help="Do not open browser automatically")
    start_parser.add_argument("--decision-only", action="store_true", help="Run 100% free Decision-Only mode without Bedrock calls")

    # check
    subparsers.add_parser("check", help="Run diagnostic health checks")

    # benchmark
    bench_parser = subparsers.add_parser("benchmark", help="Run 50-question benchmark")
    bench_parser.add_argument("--mock", action="store_true", help="Force mock mode")
    bench_parser.add_argument("--max-calls", type=int, help="Limit number of queries")

    args = parser.parse_args()

    if args.command == "start":
        cmd_start(args)
    elif args.command == "check":
        cmd_check()
    elif args.command == "benchmark":
        cmd_benchmark(args)
    else:
        # Default action: start
        cmd_start(argparse.Namespace(no_browser=False, decision_only=False))


if __name__ == "__main__":
    main()
