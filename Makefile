.PHONY: help bootstrap backend-up frontend-up frontend-restart down logs restart build \
        test test-cov test-db shell psql redis migrate admin

help:  ## Show this help
	@awk 'BEGIN {FS = ":.*##"} /^[a-zA-Z_-]+:.*##/ {printf "  %-12s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

bootstrap:  ## First-run setup: copy compose + .env, generate RSA keys
	@test -f docker-compose.yml || cp docker-compose.example.yml docker-compose.yml
	@test -f .env || cp .env.example .env
	@python scripts/init_dev_env.py
	@echo "Bootstrap done. Run: make backend-up"

backend-up:  ## Start backend stack (hot reload)
	docker compose up -d --build

frontend-up:  ## Start dev-client (Vite on :5173)
	docker compose --profile frontend up -d

frontend-restart:  ## Restart dev-client (use after editing vite.config or adding deps)
	docker compose --profile frontend restart dev-client

down:  ## Stop and remove all containers (backend + frontend)
	docker compose --profile frontend down

logs:  ## Tail app logs (dev codes print here)
	docker compose logs -f app

restart:  ## Restart app service
	docker compose restart app

build:  ## Rebuild app image without starting
	docker compose build app

test-db:  ## Create the test database (idempotent)
	@docker compose exec -T postgres createdb -U postgres fastapiapp_test 2>/dev/null || true

test: test-db  ## Run pytest in container
	docker compose exec app pytest tests/ -v

test-cov: test-db  ## Run pytest with coverage
	docker compose exec app pytest tests/ -v --cov=app

shell:  ## Shell into app container
	docker compose exec app sh

psql:  ## psql into postgres container
	docker compose exec postgres psql -U postgres

redis:  ## redis-cli into redis container
	docker compose exec redis redis-cli

migrate:  ## Run alembic upgrade head
	docker compose exec app alembic upgrade head

admin:  ## Promote a user to admin (usage: make admin EMAIL=foo@bar.com)
	@test -n "$(EMAIL)" || (echo "Usage: make admin EMAIL=foo@bar.com" && exit 1)
	docker compose exec app python -m scripts.promote_admin $(EMAIL)
