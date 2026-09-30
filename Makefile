.PHONY: help test test-fast test-ci install-backend install-frontend

help:
	@echo "MediSkye dev commands:"
	@echo "  make test             - Run all backend tests"
	@echo "  make test-fast        - Stop on first failure, show slowest"
	@echo "  make test-ci          - Simulate CI (skip integration)"
	@echo "  make install-backend  - Install backend dev deps"

install-backend:
	cd backend && pip install -r requirements-dev.txt

install-frontend:
	cd frontend && npm install

test:
	cd backend && pytest tests -v

test-fast:
	cd backend && pytest tests -x --durations=5

test-ci:
	cd backend && pytest tests -v -m "not integration"
