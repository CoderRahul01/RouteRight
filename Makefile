# RouteRight - Makefile for one-command execution and verification

.PHONY: run run-free check test benchmark clean help docker-up docker-down

help:
	@echo "RouteRight Makefile Targets:"
	@echo "  make run        - One-command start: check setup, start Decider & Web UI, open browser"
	@echo "  make run-free   - 100% free Decision-Only mode: zero AWS money, Decider 2B routing only"
	@echo "  make check      - Run pre-flight diagnostics (Decider, AWS credentials, Bedrock models)"
	@echo "  make test       - Run test suite with pytest"
	@echo "  make benchmark  - Run empirical 50-question benchmark"
	@echo "  make docker-up  - Launch isolated Docker containers for Decider (8001) and Web UI (8000)"
	@echo "  make docker-down- Stop Docker containers"
	@echo "  make clean      - Clean temporary cache and pycache files"

run:
	@python -m routeright.cli start

run-free:
	@ROUTERIGHT_DECISION_ONLY=true python -m routeright.cli start --decision-only

check:
	@python scripts/check_setup.py

test:
	@pytest tests/

benchmark:
	@python scripts/benchmark.py

docker-up:
	@docker compose up -d

docker-down:
	@docker compose down

clean:
	@rm -rf __pycache__ */__pycache__ */*/__pycache__ .pytest_cache cache/*.json
