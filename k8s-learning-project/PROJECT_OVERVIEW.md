# Project Overview: K8s Learning Order Platform

## 1) What this project is

This is a production-like full-stack Python learning project built to practice:
- Docker image creation and runtime hardening
- Container orchestration with Kubernetes
- CI/CD pipelines (GitHub Actions and GitLab CI)
- Observability (Prometheus, Grafana, JSON logs)
- Real backend architecture patterns (auth, CRUD, queue workers, caching, migrations)

Business domain:
- Order Management SaaS-style API

Core backend stack:
- FastAPI + SQLAlchemy + PostgreSQL
- Redis for cache and Celery broker/backend
- Celery worker for async processing
- JWT authentication
- Alembic migrations

Frontend stack:
- Static HTML/CSS/JS app served via Nginx

## 2) High-level request flow

1. Frontend calls `/api/*`.
2. FastAPI validates JWT and request payload.
3. FastAPI reads/writes PostgreSQL via SQLAlchemy.
4. Order list results may be cached in Redis.
5. Order creation enqueues async task to Celery.
6. Worker consumes task from Redis and updates order status.
7. Metrics are exposed on `/metrics`.
8. Logs are emitted as structured JSON for Loki-style ingestion.

## 3) Important folders

- `backend/app/main.py`: App bootstrap, routers, CORS, probes, metrics
- `backend/app/api/`: Auth, users, orders API handlers
- `backend/app/core/`: App configuration and security helpers
- `backend/app/db/`: Session, ORM models, seed
- `backend/app/services/`: Service utilities (cache layer)
- `backend/app/workers/`: Celery app and async tasks
- `backend/alembic/`: Migration runtime + schema versions
- `frontend/src/`: Static UI implementation
- `docker-compose.yml`: Local multi-container runtime
- `k8s/`: Kubernetes manifests (app, db, cache, ingress, monitoring, rbac)
- `cicd/`: CI/CD pipeline definitions
- `scripts/`: Database migration and seeding shortcuts

## 4) API surface (core)

Auth:
- `POST /api/auth/register`
- `POST /api/auth/login`

Users:
- `GET /api/users/me`
- `PATCH /api/users/me`
- `GET /api/users` (superuser)

Orders:
- `POST /api/orders/`
- `GET /api/orders/`
- `GET /api/orders/{order_id}`
- `PUT /api/orders/{order_id}`
- `DELETE /api/orders/{order_id}`

Runtime and observability:
- `GET /health/live`
- `GET /health/ready`
- `GET /metrics`

## 5) Where credentials and environment values are controlled

Primary runtime variables:
- `backend/.env.example`
- Environment variables injected by Docker/Kubernetes/CI (recommended for real secrets)

Code defaults (used if env vars are absent):
- `backend/app/core/config.py`

Kubernetes secrets:
- `k8s/backend/secret.yaml`
- `k8s/monitoring/grafana.yaml`

Docker local runtime overrides:
- `docker-compose.yml` under `backend` and `worker` service `environment`

CI/CD secret references:
- `cicd/github-actions.yaml`
- `cicd/gitlab-ci.yaml`

## 6) Typical local dev loop

1. Start stack:
   ```bash
   docker compose up --build -d
   ```
2. Open docs:
   - `http://localhost:8000/api/docs`
3. Use frontend:
   - `http://localhost:8080`
4. Check logs:
   ```bash
   docker compose logs -f backend
   docker compose logs -f worker
   ```
5. Stop stack:
   ```bash
   docker compose down
   ```

## 7) What makes this "real-project-like"

- Separation of concerns between API, services, workers, db, config
- Auth and permission boundaries
- Background processing with retries
- Health probes and metrics endpoints
- Infrastructure-as-code for K8s resources
- CI stages for lint/test/build/deploy

