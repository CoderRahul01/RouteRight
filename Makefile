# RouteRight - Makefile for one-command execution and verification

.PHONY: run check test benchmark clean help docker-up docker-down

help:
	@echo "RouteRight Makefile Targets:"
	@echo "  make run        - One-command start: check setup, start Decider & Web UI, open browser"
	@echo "  make check      - Run pre-flight diagnostics (Decider, AWS credentials, Bedrock models)"
	@echo "  make test       - Run test suite with pytest"
	@echo "  make benchmark  - Run empirical 50-question benchmark"
	@echo "  make docker-up  - Launch isolated Docker containers for Decider (8001) and Web UI (8000)"
	@echo "  make docker-down- Stop Docker containers"
	@echo "  make clean      - Clean temporary cache and pycache files"

run:
	@python -m routeright.cli start

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
