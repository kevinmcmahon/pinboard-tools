# ABOUTME: Makefile for pinboard-tools project with development tasks
# ABOUTME: Provides standard targets for testing, linting, formatting, and project management

.PHONY: help install install-dev clean test test-cov lint format format-imports typecheck check all docs docs-llm docs-clean
.DEFAULT_GOAL := help

# Variables
PYTHON_DIRS := pinboard_tools tests
UV := uv

# Unset VIRTUAL_ENV to avoid uv warnings
unexport VIRTUAL_ENV

# Help target
help: ## Show this help message
	@echo "Available targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

# Installation targets
install: ## Install project dependencies
	$(UV) sync

install-dev: ## Install project with development dependencies
	$(UV) sync --dev

# Cleaning targets
clean: ## Clean build artifacts and caches
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name ".coverage" -delete
	rm -rf .pytest_cache/
	rm -rf .mypy_cache/
	rm -rf .ruff_cache/

# Testing targets
test: ## Run all tests
	$(UV) run --with pytest pytest

test-cov: ## Run tests with coverage report
	$(UV) run --with pytest,pytest-cov pytest --cov=pinboard_tools --cov-report=term-missing

test-verbose: ## Run tests with verbose output
	$(UV) run --with pytest pytest -v

test-specific: ## Run specific test file (usage: make test-specific FILE=test_database.py)
	$(UV) run --with pytest pytest tests/$(FILE)

# Code quality targets
lint: ## Run linting checks
	$(UV) run --with ruff ruff check $(PYTHON_DIRS)

format: ## Format code using ruff and sort imports with isort
	$(UV) run --with ruff ruff format $(PYTHON_DIRS)
	$(UV) run --with isort isort $(PYTHON_DIRS)

format-imports: ## Sort imports using isort
	$(UV) run --with isort isort $(PYTHON_DIRS)

format-check: ## Check code formatting without making changes
	$(UV) run --with ruff ruff format --check $(PYTHON_DIRS)
	$(UV) run --with isort isort --check-only $(PYTHON_DIRS)

typecheck: ## Run type checking with mypy
	$(UV) run --with mypy,pytest mypy $(PYTHON_DIRS)

# Combined quality checks
check: lint typecheck format-check ## Run all code quality checks (lint, typecheck, format-check)

# Development workflow targets
fix: format lint ## Format code, sort imports, and run linting
	@echo "Code formatting, import sorting, and linting complete"

all: clean install-dev check test ## Run complete development workflow

# Build targets
build: ## Build distribution packages
	$(UV) build

# Documentation targets
docs: ## Build HTML documentation
	cd docs && $(UV) run --with sphinx sphinx-build -b html . _build/html
	@echo "Documentation built in docs/_build/html/"

docs-llm: ## Build LLM-friendly documentation formats (text and singlehtml)
	cd docs && make llm
	@echo "LLM-friendly docs built in docs/_build/text/ and docs/_build/singlehtml/"

docs-clean: ## Clean documentation build files
	rm -rf docs/_build/
	@echo "Documentation build files cleaned"

docs-deps: ## Install documentation dependencies
	$(UV) add --dev sphinx sphinx-rtd-theme

# Database targets
schema-check: ## Validate SQL schema file
	@if [ -f schema.sql ]; then \
		echo "Checking SQL schema syntax..."; \
		sqlite3 ":memory:" ".read schema.sql" ".quit" && echo "Schema syntax is valid"; \
	else \
		echo "No schema.sql file found"; \
	fi

# Development server targets
dev-setup: install-dev ## Complete development environment setup
	@echo "Development environment ready!"
	@echo "Run 'make help' to see available commands"

# Continuous integration target
ci: install-dev check test-cov ## Run CI pipeline (install, check, test with coverage)

# Show project info
info: ## Show project information
	@echo "Project: pinboard-tools"
	@echo "Python version: $(shell python3 --version)"
	@echo "UV version: $(shell $(UV) --version)"
	@echo "Project structure:"
	@find pinboard_tools -name "*.py" | head -10
	@echo "..."