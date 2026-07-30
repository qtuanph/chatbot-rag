.PHONY: dev lint test build up down clean help

# Default target
.DEFAULT_GOAL := help

help:
	@echo "======================================================================"
	@echo " Chatbot-RAG Enterprise Platform - Management Commands"
	@echo "======================================================================"
	@echo "  make dev      - Run local dev servers (Backend & Frontend)"
	@echo "  make lint     - Run Black, Flake8, and TypeScript type checks"
	@echo "  make test     - Run backend Pytest test suite"
	@echo "  make up       - Start all Docker Compose containers (-d)"
	@echo "  make build    - Rebuild and start Docker Compose stack"
	@echo "  make down     - Stop all running Docker containers"
	@echo "  make clean    - Remove build artifacts, pycache, and temp logs"
	@echo "======================================================================"

dev:
	@echo "Starting FastAPI backend & Next.js webapp in dev mode..."
	cd chatbot-api && docker compose up -d

lint:
	@echo "Checking Python backend formatting & types..."
	python -m black app --check --line-length=120
	python -m flake8 app --select=F,E1,E2,E4,E9,W --ignore=E203,E501,W293,W292,W391,W503,W504
	@echo "Checking Frontend TypeScript types..."
	cd chatbot-webapp && npx tsc --noEmit

test:
	@echo "Running backend Pytest suite..."
	cd chatbot-api && pytest tests/

up:
	@echo "Starting Docker Compose stack..."
	cd chatbot-api && docker compose up -d

build:
	@echo "Rebuilding and starting Docker Compose stack..."
	cd chatbot-api && docker compose up -d --build

down:
	@echo "Stopping Docker Compose stack..."
	cd chatbot-api && docker compose down

clean:
	@echo "Cleaning cache files..."
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".next" -exec rm -rf {} +
	rm -rf .coverage htmlcov
