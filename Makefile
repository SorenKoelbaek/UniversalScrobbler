# Variables
UI_DIR=ui
API_DIR=api

# Commands
.PHONY: dev build test run

# Start both frontend (React) and backend (FastAPI) in development mode
dev:
	docker compose up -d redis
	npx concurrently "cd api && poetry run uvicorn main:app --reload" "cd ui && npm start"

# Build the React frontend application
build:
	cd $(UI_DIR) && npm run build

# Run tests for the backend using pytest
test:
	cd $(API_DIR) && pytest

# Run the FastAPI backend
run:
	cd $(API_DIR) && uvicorn main:app --reload
