# K8s Learning Project: Architecture, Deployment, and Real-Time Testing Guide

## 1) Architecture, Request Flow, and Components

### 1.1 High-level architecture (runtime view)

```text
User Browser
    |
    | HTTP
    v
Frontend (Nginx, static UI + /api reverse proxy)
    |
    | /api requests
    v
Backend API (FastAPI)
    |                    \
    | SQL                \  Async job enqueue
    v                     v
PostgreSQL              Redis (broker/cache/result backend)
                          |
                          v
                     Celery Worker
```

### 1.2 Request flow (end-to-end)

1. Browser loads frontend at `/` from Nginx.
2. Frontend JS (`frontend/src/app.js`) calls `/api/...`.
3. Nginx forwards `/api` to backend API.
4. Backend handles auth (JWT), user APIs, and order CRUD.
5. On order creation, backend enqueues a Celery job.
6. Worker consumes the job from Redis and updates order status:
`pending -> processing -> completed`.
7. Backend stores persistent records in PostgreSQL.
8. Order list responses are cached in Redis (short TTL), invalidated on writes.

### 1.3 Components and use-cases

| Component | Where used | Use-case in this project |
|---|---|---|
| Nginx frontend | Docker/Compose/K8s | Serves static UI and reverse proxies `/api` |
| FastAPI backend | Docker/Compose/K8s/VM/GAE | Auth, user management, order APIs, metrics |
| PostgreSQL | Docker/Compose/K8s/VM or Cloud SQL | Durable storage for users and orders |
| Redis | Docker/Compose/K8s/VM or Memorystore | Cache, Celery broker, Celery result backend |
| Celery worker | Docker/Compose/K8s/VM | Background order processing |
| Prometheus/Grafana | K8s manifests | Metrics scraping and dashboards |
| Ingress | K8s (GKE) | External routing (`/` -> frontend, `/api` -> backend) |

---

## 2) Deployment Steps

## 2.1 Method A: Individual Docker containers (Ubuntu VM)

This keeps each service as a separate container started manually.

### Prerequisites

- Ubuntu VM with Docker Engine + Compose plugin installed.
- Open inbound ports: `8080` (frontend), optional `8000` (direct backend access).

### Step-by-step

```bash
cd k8s-learning-project

# 1) Build images
docker build -t k8s-learning-backend:latest ./backend
docker build -t k8s-learning-frontend:latest ./frontend

# 2) Create network + volumes
docker network create k8s-learning-net
docker volume create pg_data
docker volume create redis_data

# 3) Start PostgreSQL
docker run -d \
  --name postgres \
  --network k8s-learning-net \
  -e POSTGRES_DB=app_db \
  -e POSTGRES_USER=app_user \
  -e POSTGRES_PASSWORD=app_password \
  -v pg_data:/var/lib/postgresql/data \
  postgres:16-alpine

# 4) Start Redis
docker run -d \
  --name redis \
  --network k8s-learning-net \
  -v redis_data:/data \
  redis:7-alpine redis-server --appendonly yes

# 5) Run migration + seed once
docker run --rm \
  --network k8s-learning-net \
  --env-file ./backend/.env.example \
  -e ENVIRONMENT=docker \
  k8s-learning-backend:latest \
  sh -c "alembic upgrade head && python -m app.db.seed"

# 6) Start backend API
docker run -d \
  --name backend \
  --network k8s-learning-net \
  --env-file ./backend/.env.example \
  -e ENVIRONMENT=docker \
  -p 8000:8000 \
  k8s-learning-backend:latest

# 7) Start worker
docker run -d \
  --name worker \
  --network k8s-learning-net \
  --env-file ./backend/.env.example \
  -e ENVIRONMENT=docker \
  k8s-learning-backend:latest \
  celery -A app.workers.celery_app.celery_app worker --loglevel=info

# 8) Start frontend (Nginx listens on 80 inside container)
docker run -d \
  --name frontend \
  --network k8s-learning-net \
  -p 8080:80 \
  k8s-learning-frontend:latest
```

### Access points

- Frontend: `http://<VM_IP>:8080`
- Backend docs: `http://<VM_IP>:8000/api/docs`
- Backend API via frontend proxy: `http://<VM_IP>:8080/api/...`

### APIs to test quickly

- `POST /api/auth/register`
- `POST /api/auth/login`
- `GET /api/users/me` (JWT required)
- `POST /api/orders/` (JWT required)
- `GET /api/orders/` (JWT required)
- `PUT /api/orders/{id}` (JWT required)
- `DELETE /api/orders/{id}` (JWT required)

---

## 2.2 Method B: Docker Compose

```bash
cd k8s-learning-project
docker compose up --build -d
docker compose ps
```

Access:

- Frontend: `http://localhost:8080`
- Backend docs: `http://localhost:8000/api/docs`
- Metrics: `http://localhost:8000/metrics`

Stop:

```bash
docker compose down
```

---

## 2.3 Method C: Kubernetes on GKE (with external access)

### 1) Create cluster and connect

```bash
gcloud auth login
gcloud config set project <GCP_PROJECT_ID>
gcloud container clusters create k8s-learning-cluster \
  --region us-central1 \
  --num-nodes 3
gcloud container clusters get-credentials k8s-learning-cluster --region us-central1
```

### 2) Build and push images to Artifact Registry

```bash
gcloud artifacts repositories create k8s-learning \
  --repository-format=docker \
  --location=us-central1 || true

gcloud auth configure-docker us-central1-docker.pkg.dev

BACKEND_IMAGE=us-central1-docker.pkg.dev/<GCP_PROJECT_ID>/k8s-learning/k8s-learning-backend:latest
FRONTEND_IMAGE=us-central1-docker.pkg.dev/<GCP_PROJECT_ID>/k8s-learning/k8s-learning-frontend:latest

docker build -t "$BACKEND_IMAGE" ./backend
docker build -t "$FRONTEND_IMAGE" ./frontend
docker push "$BACKEND_IMAGE"
docker push "$FRONTEND_IMAGE"
```

### 3) Apply manifests

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
```

Set pushed image names:

```bash
kubectl -n k8s-learning set image deployment/backend-api backend="$BACKEND_IMAGE"
kubectl -n k8s-learning set image deployment/backend-worker worker="$BACKEND_IMAGE"
kubectl -n k8s-learning set image deployment/frontend-web frontend="$FRONTEND_IMAGE"
```

### 4) Install ingress controller (NGINX)

```bash
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/main/deploy/static/provider/cloud/deploy.yaml
kubectl wait --namespace ingress-nginx \
  --for=condition=ready pod \
  --selector=app.kubernetes.io/component=controller \
  --timeout=300s
```

### 5) External connectivity

Get LoadBalancer IP:

```bash
LB_IP=$(kubectl get svc -n ingress-nginx ingress-nginx-controller -o jsonpath='{.status.loadBalancer.ingress[0].ip}')
echo "$LB_IP"
```

Use a DNS-free host with `nip.io`:

```bash
sed "s/app.local/app.${LB_IP}.nip.io/g" k8s/ingress/ingress.yaml | kubectl apply -f -
```

Then access:

- Frontend: `http://app.<LB_IP>.nip.io`
- Backend docs: `http://app.<LB_IP>.nip.io/api/docs`

### 6) Seed data once (recommended for admin/demo users)

```bash
kubectl -n k8s-learning exec deploy/backend-api -- python -m app.db.seed
```

---

## 2.4 Method D: Direct code deployment on Ubuntu VM (no Docker for app processes)

### 1) Install dependencies

```bash
sudo apt update
sudo apt install -y python3.11 python3.11-venv python3-pip build-essential \
  libpq-dev postgresql postgresql-contrib redis-server nginx git curl
```

### 2) Prepare DB and Redis

```bash
sudo -u postgres psql -c "CREATE DATABASE app_db;"
sudo -u postgres psql -c "CREATE USER app_user WITH ENCRYPTED PASSWORD 'app_password';"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE app_db TO app_user;"
sudo systemctl enable --now postgresql redis-server
```

### 3) Backend setup

```bash
git clone <YOUR_REPO_URL>
cd k8s-learning-project/backend
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Update `backend/.env` for VM deployment with your Cloud Redis:

```dotenv
ENVIRONMENT=vm
DATABASE_URL=postgresql+psycopg2://app_user:app_password@127.0.0.1:5432/app_db
REDIS_URL=redis://default:yPsSqjxk1HCIN67kWe3DZvCdw9Vw84a6@redis-14642.c259.us-central1-2.gce.cloud.redislabs.com:14642/0
CELERY_BROKER_URL=redis://default:yPsSqjxk1HCIN67kWe3DZvCdw9Vw84a6@redis-14642.c259.us-central1-2.gce.cloud.redislabs.com:14642/0
CELERY_RESULT_BACKEND=redis://default:yPsSqjxk1HCIN67kWe3DZvCdw9Vw84a6@redis-14642.c259.us-central1-2.gce.cloud.redislabs.com:14642/0
```

Run migrations + seed:

```bash
alembic upgrade head
python -m app.db.seed
```

Start backend API:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Start worker (new terminal):

```bash
cd k8s-learning-project/backend
source .venv/bin/activate
celery -A app.workers.celery_app.celery_app worker --loglevel=info
```

### 4) Frontend on VM via Nginx

```bash
sudo mkdir -p /var/www/k8s-learning-frontend
sudo cp -r ../frontend/src/* /var/www/k8s-learning-frontend/
```

Create `/etc/nginx/sites-available/k8s-learning`:

```nginx
server {
  listen 80;
  server_name _;
  root /var/www/k8s-learning-frontend;
  index index.html;

  location / {
    try_files $uri /index.html;
  }

  location /api/ {
    proxy_pass http://127.0.0.1:8000/api/;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
  }
}
```

Enable site:

```bash
sudo ln -sf /etc/nginx/sites-available/k8s-learning /etc/nginx/sites-enabled/k8s-learning
sudo nginx -t
sudo systemctl restart nginx
```

Access:

- Frontend/API unified URL: `http://<VM_IP>`
- Backend docs direct: `http://<VM_IP>:8000/api/docs`

---

## 2.5 Google App Engine (backend service template)

This repo includes `backend/app.yaml` for App Engine Flexible.

Important:

- App Engine deploys backend API only.
- Use managed services for dependencies:
  - PostgreSQL: Cloud SQL
  - Redis: Memorystore
- Celery worker should run separately (for example on Cloud Run or GKE).

Deploy:

```bash
cd k8s-learning-project
gcloud app create --region=us-central
gcloud app deploy backend/app.yaml
gcloud app browse
```

After deployment:

- Backend docs: `https://<PROJECT_ID>.uc.r.appspot.com/api/docs`

---

## 2.6 Future reference: where Redis URL/credentials must be changed

When Redis endpoint/username/password changes, update these files:

1. `backend/.env.example`
- `REDIS_URL`
- `CELERY_BROKER_URL`
- `CELERY_RESULT_BACKEND`

2. `docker-compose.yml`
- `backend.environment.REDIS_URL`
- `backend.environment.CELERY_BROKER_URL`
- `backend.environment.CELERY_RESULT_BACKEND`
- `worker.environment.REDIS_URL`
- `worker.environment.CELERY_BROKER_URL`
- `worker.environment.CELERY_RESULT_BACKEND`

3. `k8s/backend/secret.yaml`
- base64-encoded values for:
  - `REDIS_URL`
  - `CELERY_BROKER_URL`
  - `CELERY_RESULT_BACKEND`

Encoding helper:

```bash
echo -n 'redis://default:<PASSWORD>@<HOST>:<PORT>/0' | base64
```

4. `backend/app.yaml` (App Engine)
- `env_variables.REDIS_URL`
- `env_variables.CELERY_BROKER_URL`
- `env_variables.CELERY_RESULT_BACKEND`

5. `backend/.env` (actual runtime env on VM/direct deployment)
- same 3 variables as above.

---

## 3) Real-Time Testing Steps (for all methods)

These are full functional tests, not basic health checks.

Install test tool:

```bash
sudo apt install -y jq
```

Pick `BASE_URL` based on deployment method:

- Individual Docker: `BASE_URL=http://<VM_IP>:8080/api`
- Docker Compose local: `BASE_URL=http://localhost:8080/api`
- Kubernetes (GKE ingress): `BASE_URL=http://app.<LB_IP>.nip.io/api`
- Direct code with Nginx: `BASE_URL=http://<VM_IP>/api`
- App Engine backend only: `BASE_URL=https://<PROJECT_ID>.uc.r.appspot.com/api`

### 3.1 End-to-end user and order lifecycle

```bash
BASE_URL=<set_this>
EMAIL="rt$(date +%Y%m%d%H%M%S)@example.com"
PASSWORD="TestPass123!"
FULL_NAME="Realtime Tester"

# Register
curl -sS -X POST "$BASE_URL/auth/register" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\",\"full_name\":\"$FULL_NAME\"}" | jq

# Login (OAuth2 form)
TOKEN=$(curl -sS -X POST "$BASE_URL/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=$EMAIL&password=$PASSWORD" | jq -r '.access_token')

echo "Token acquired: ${TOKEN:0:25}..."

# Create order
ORDER_ID=$(curl -sS -X POST "$BASE_URL/orders/" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"title":"Realtime order","description":"E2E realtime validation","total_amount":149.99,"priority":4}' | jq -r '.id')

echo "Created order id=$ORDER_ID"

# Poll order status in realtime (worker-driven transition)
for i in {1..10}; do
  STATUS=$(curl -sS -X GET "$BASE_URL/orders/$ORDER_ID" \
    -H "Authorization: Bearer $TOKEN" | jq -r '.status')
  echo "$(date +%H:%M:%S) status=$STATUS"
  sleep 1
done

# Update and verify
curl -sS -X PUT "$BASE_URL/orders/$ORDER_ID" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"status":"canceled"}' | jq

# Profile + list
curl -sS -X GET "$BASE_URL/users/me" -H "Authorization: Bearer $TOKEN" | jq
curl -sS -X GET "$BASE_URL/orders/?skip=0&limit=20" -H "Authorization: Bearer $TOKEN" | jq
```

Expected:

- Register and login succeed.
- Order appears and moves from `pending` to `processing/completed`.
- Profile and order list return valid JSON.

### 3.2 Worker outage and recovery test

- Stop worker.
- Create a new order.
- Confirm it stays `pending`.
- Start worker.
- Confirm status starts changing again.

Commands by method:

- Individual Docker: `docker stop worker && docker start worker`
- Compose: `docker compose stop worker && docker compose start worker`
- Kubernetes: `kubectl -n k8s-learning scale deployment/backend-worker --replicas=0` then `--replicas=2`
- Direct code: stop/start Celery process or service.

### 3.3 Redis cache behavior test

1. Call `GET /orders` twice.
2. Inspect Redis keys and TTL.
3. Create/update/delete an order.
4. Re-check keys to verify invalidation.

Redis check commands:

- With external Cloud Redis (recommended in your setup):
  - `redis-cli -u "redis://default:<PASSWORD>@redis-14642.c259.us-central1-2.gce.cloud.redislabs.com:14642/0" --scan --pattern "orders:*"`
  - `redis-cli -u "redis://default:<PASSWORD>@redis-14642.c259.us-central1-2.gce.cloud.redislabs.com:14642/0" TTL "orders:<USER_ID>:all:0:20"`
- With local Redis container (if you still use it):
  - `docker exec -it redis redis-cli --scan --pattern "orders:*"`
  - `docker exec -it redis redis-cli TTL "orders:<USER_ID>:all:0:20"`

### 3.4 Authorization behavior test

Normal user must not access admin list endpoint:

```bash
curl -i -sS "$BASE_URL/users/" -H "Authorization: Bearer $TOKEN"
```

Expected: `403`.

If seeded admin exists (`admin@k8s-learning.local / admin12345`), login as admin and verify `/users/` returns list.

### 3.5 Persistence test

1. Create order and note `ORDER_ID`.
2. Restart backend service.
3. Fetch same order again.
4. Confirm order still exists (PostgreSQL persistence).

Commands by method:

- Individual Docker: `docker restart backend`
- Compose: `docker compose restart backend`
- Kubernetes: `kubectl -n k8s-learning rollout restart deployment/backend-api`
- Direct code: restart API process/service

---

## 4) Live observability during tests

Use these while running test scenarios:

- Individual Docker:
  - `docker logs -f backend`
  - `docker logs -f worker`
- Compose:
  - `docker compose logs -f backend worker redis postgres frontend`
- Kubernetes:
  - `kubectl -n k8s-learning logs deployment/backend-api -f`
  - `kubectl -n k8s-learning logs deployment/backend-worker -f`
- Direct code:
  - run backend/worker in foreground or with `journalctl -u <service> -f`
