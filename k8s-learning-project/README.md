# k8s-learning-project

Production-like full-stack Python system for learning Docker, Kubernetes, CI/CD, and monitoring.  
Domain: **Order Management SaaS-style backend** with JWT authentication, CRUD APIs, background jobs, caching, persistent storage, and observability.

## Architecture Diagram (ASCII)

```text
                              +----------------------+
                              |      Developers      |
                              +----------+-----------+
                                         |
                                         v
                                +------------------+
                                |  CI/CD Pipeline  |
                                | GH Actions/GitLab|
                                +--------+---------+
                                         |
                                         v
+------------------+          +--------------------------+          +-------------------+
|  Browser Client  |  HTTP    | NGINX Frontend Container |  /api    | FastAPI Backend   |
| (HTML/JS UI)     +--------->+ (Static + Reverse Proxy) +--------->+ JWT + CRUD + /metrics
+------------------+          +------------+-------------+          +----+--------+-----+
                                            |                           |        |
                                            |                           |        |
                                            v                           v        v
                                      +------------+              +-----------+  +------------+
                                      | Ingress    |              | PostgreSQL|  | Redis      |
                                      | (K8s NGINX)|              | StatefulSet| | Cache/Broker|
                                      +------------+              +-----------+  +------+------+
                                                                                       |
                                                                                       v
                                                                                +--------------+
                                                                                | Celery Worker|
                                                                                | Background   |
                                                                                | Order Jobs   |
                                                                                +--------------+

Monitoring:
  FastAPI /metrics --> Prometheus --> Grafana Dashboards
Structured logs:
  JSON logs with Loki labels for easy log shipping integration
```

## Core Features

- JWT authentication (`/api/auth/register`, `/api/auth/login`)
- User APIs (`/api/users/me`, `/api/users`)
- Order CRUD APIs with ownership checks (`/api/orders/*`)
- Redis order list cache invalidation on writes
- Celery worker processing orders asynchronously
- PostgreSQL persistence with Alembic migration
- Seed data script for dev/test environments
- Health endpoints (`/health/live`, `/health/ready`) and Prometheus metrics (`/metrics`)
- JSON structured logging with Loki-ready labels

## Local Run (Without Docker)

1. Start PostgreSQL and Redis locally.
2. From `backend/`, create and activate Python virtual environment.
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Set environment variables (or copy `.env.example` to `.env` and adjust).
5. Run migrations and seed:
   ```bash
   ../scripts/migrate.sh
   ../scripts/init_db.sh
   ```
6. Start API:
   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```
7. Start worker in a second terminal:
   ```bash
   celery -A app.workers.celery_app.celery_app worker --loglevel=info
   ```
8. Serve frontend:
   - Open `frontend/src/index.html` directly for quick checks, or run through Nginx with Docker (recommended).

## Docker Run Steps

From repository root (`k8s-learning-project/`):

```bash
docker compose up --build -d
```

Access:
- Frontend: `http://localhost:8080`
- Backend OpenAPI: `http://localhost:8000/api/docs`
- Backend metrics: `http://localhost:8000/metrics`

Stop:

```bash
docker compose down -v
```

## Kubernetes Deployment Steps

1. Ensure cluster + NGINX ingress controller are available.
2. Apply manifests:
   ```bash
   kubectl apply -f k8s/namespaces/namespace.yaml
   kubectl apply -f k8s/rbac/backend-rbac.yaml
   kubectl apply -f k8s/backend/configmap.yaml
   kubectl apply -f k8s/backend/secret.yaml
   kubectl apply -f k8s/postgres/pvc.yaml
   kubectl apply -f k8s/postgres/service.yaml
   kubectl apply -f k8s/postgres/statefulset.yaml
   kubectl apply -f k8s/redis/service.yaml
   kubectl apply -f k8s/redis/deployment.yaml
   kubectl apply -f k8s/backend/deployment.yaml
   kubectl apply -f k8s/backend/worker-deployment.yaml
   kubectl apply -f k8s/backend/service.yaml
   kubectl apply -f k8s/backend/hpa.yaml
   kubectl apply -f k8s/frontend/deployment.yaml
   kubectl apply -f k8s/frontend/service.yaml
   kubectl apply -f k8s/monitoring/prometheus.yaml
   kubectl apply -f k8s/monitoring/grafana.yaml
   kubectl apply -f k8s/ingress/ingress.yaml
   ```
3. Add host mapping for ingress:
   - `app.local` -> your ingress controller IP
4. Open:
   - `http://app.local`

## CI/CD Explanation

### GitHub Actions (`cicd/github-actions.yaml`)

- `lint-test` job:
  - installs backend dependencies
  - runs `ruff` lint
  - runs `pytest`
- `build-and-push` job:
  - builds backend and frontend Docker images
  - tags with `${{ github.sha }}` and `latest`
  - pushes to container registry
- `deploy` job:
  - applies Kubernetes manifests
  - sets deployment images to versioned tags
  - waits for rollout completion

Required secrets:
- `REGISTRY_USERNAME`
- `REGISTRY_PASSWORD`
- `KUBE_CONFIG_DATA` (base64 kubeconfig)

### GitLab CI (`cicd/gitlab-ci.yaml`)

- Separate `lint`, `test`, `build`, `deploy` stages
- Docker-in-Docker image builds and pushes
- Deploys on `main` branch using `kubectl`

Required CI variables/secrets:
- `CI_REGISTRY_USER`
- `CI_REGISTRY_PASSWORD`
- `KUBE_CONFIG_DATA`

## Monitoring Access Steps

After Kubernetes deployment:

- Prometheus: `http://<node-ip>:30900`
- Grafana: `http://<node-ip>:30300`
  - username: `admin`
  - password: `admin12345` (change for real environments)
- Backend metrics target:
  - `backend-service.k8s-learning.svc.cluster.local:80/metrics`

## Common kubectl Commands

```bash
kubectl get pods -n k8s-learning
kubectl get svc -n k8s-learning
kubectl get ingress -n k8s-learning
kubectl get hpa -n k8s-learning
kubectl describe pod <pod-name> -n k8s-learning
kubectl logs deployment/backend-api -n k8s-learning --tail=200
kubectl logs deployment/backend-worker -n k8s-learning --tail=200
kubectl exec -it statefulset/postgres -n k8s-learning -- psql -U app_user -d app_db
kubectl rollout restart deployment/backend-api -n k8s-learning
kubectl rollout status deployment/backend-api -n k8s-learning
```

## Debugging Guide

1. Backend readiness probe failing:
   - Check DB and Redis connectivity:
     ```bash
     kubectl logs deployment/backend-api -n k8s-learning
     kubectl get pods -n k8s-learning
     ```
2. Worker not processing jobs:
   - Check Redis and worker logs:
     ```bash
     kubectl logs deployment/backend-worker -n k8s-learning
     kubectl logs deployment/redis -n k8s-learning
     ```
3. Database issues:
   - Confirm migration ran in initContainer:
     ```bash
     kubectl describe pod -l app=backend-api -n k8s-learning
     ```
4. Ingress routing issues:
   - Validate ingress rules and controller class:
     ```bash
     kubectl describe ingress platform-ingress -n k8s-learning
     ```
5. Metrics missing in Prometheus:
   - Verify scrape target:
     ```bash
     kubectl port-forward svc/prometheus 9090:9090 -n k8s-learning
     ```
   - Open `/targets` in Prometheus UI.

