.PHONY: setup dev scan test logs stop clean

setup: ## Install all dependencies and run migrations
	@echo "Setting up NADIR..."
	cp -n .env.example .env 2>/dev/null || true
	cd backend && pip install -r requirements.txt
	cd frontend && npm install
	docker compose up -d postgres redis
	@sleep 3
	cd backend && alembic upgrade head
	@echo "Setup complete! Run 'make dev' to start."

dev: ## Start all services in development mode
	docker compose up -d postgres redis
	@sleep 2
	cd backend && alembic upgrade head
	@echo "Starting backend..."
	cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 &
	@echo "Starting Celery worker..."
	cd backend && celery -A app.core.celery_app worker --loglevel=info --concurrency=2 &
	@echo "Starting Celery beat..."
	cd backend && celery -A app.core.celery_app beat --loglevel=info &
	@echo "Starting frontend..."
	cd frontend && npm run dev

docker-dev: ## Start everything via Docker Compose
	docker compose up --build

scan: ## Trigger manual full universe scan
	curl -s -X POST http://localhost:8000/api/signals/refresh/AAPL | python -m json.tool 2>/dev/null || echo "Backend not running"

test: ## Run the test suite
	cd backend && python -m pytest tests/ -v --tb=short

logs: ## Tail all Docker service logs
	docker compose logs -f --tail=100

stop: ## Stop all services
	docker compose down
	@-pkill -f "uvicorn app.main" 2>/dev/null || true
	@-pkill -f "celery -A app.core" 2>/dev/null || true

clean: ## Stop and remove all data
	docker compose down -v
	@-pkill -f "uvicorn app.main" 2>/dev/null || true
	@-pkill -f "celery -A app.core" 2>/dev/null || true
