.PHONY: help install install-dev test test-integration test-security test-performance lint format type-check security-scan clean docker-build docker-up docker-down benchmark

help:  ## Show this help message
	@echo "Available targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

install:  ## Install production dependencies
	pip install -e .

install-dev:  ## Install all dependencies (including dev)
	pip install -e ".[dev]"

test:  ## Run all tests
	pytest

test-integration:  ## Run integration tests only (60% of test effort)
	pytest integration-tests/ -v

test-security:  ## Run security tests
	pytest integration-tests/security/ -v

test-performance:  ## Run performance benchmarks
	pytest integration-tests/test_performance.py -v --benchmark-only

lint:  ## Run linting (ruff)
	ruff check shared/ layers/

format:  ## Format code (black)
	black shared/ layers/ integration-tests/

type-check:  ## Run type checking (mypy)
	mypy shared/ layers/

security-scan:  ## Run security scans
	bandit -r shared/ layers/ -ll
	safety check

clean:  ## Clean build artifacts and cache
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	rm -rf htmlcov/ .coverage

docker-build:  ## Build Docker images
	docker-compose -f deployment/docker-compose.yml build

docker-up:  ## Start services with Docker Compose
	docker-compose -f deployment/docker-compose.yml up -d

docker-down:  ## Stop Docker services
	docker-compose -f deployment/docker-compose.yml down

docker-logs:  ## View Docker logs
	docker-compose -f deployment/docker-compose.yml logs -f

benchmark:  ## Run performance benchmarks
	python benchmarks/preprocessing_bench.py
	python benchmarks/sentiment_bench.py

ci:  ## Run full CI pipeline locally
	make lint
	make type-check
	make security-scan
	make test

dev:  ## Start development environment
	@echo "Starting development environment..."
	@echo "1. Install dependencies: make install-dev"
	@echo "2. Run tests: make test"
	@echo "3. Start Docker: make docker-up"
