# App Engine Deployment

This document is for your `deploy/app-engine` branch and includes:

1. Backend deployment to Google App Engine Flexible.
2. Frontend deployment to Google Cloud Run.
3. Exact configuration points to change later if Cloud SQL/Redis provider changes.
4. Ubuntu VM deployment with separate containers (no docker-compose), plus real end-to-end testing.

## 1) Recommended branch structure

- `deploy/app-engine` (backend App Engine + frontend Cloud Run)
- `deploy/ubuntu-vm-separate-containers`
- `deploy/docker-compose`
- `deploy/kubernetes-gke`

Keep this file in `deploy/app-engine` and duplicate/adapt it for each deployment branch.

## 2) Backend deployment to App Engine Flexible

### 2.1 Preconditions

- GCP project is selected and billing enabled.
- App Engine app exists.
- Cloud SQL instance exists and is reachable.
- Redis instance exists and is reachable from App Engine runtime.

### 2.2 Files that matter

- `backend/app.yaml`
- `backend/Dockerfile`
- `backend/alembic/env.py`

### 2.3 Config checklist before deploy

1. `backend/app.yaml`
- `runtime: custom`
- `env: flex`
- `beta_settings.cloud_sql_instances` must exactly match your Cloud SQL connection name.
- `env_variables.DATABASE_URL` must use Unix socket format:
  - `postgresql+psycopg2://<user>:<encoded_pass>@/<db>?host=/cloudsql/<PROJECT:REGION:INSTANCE>`
- URL-encode password special chars (`@` -> `%40`, `#` -> `%23`, `%` -> `%25`).
- Set `CORS_ORIGINS` to your frontend URL(s).

2. `backend/alembic/env.py`
- Keep this fix so Alembic accepts encoded passwords:
  - `config.set_main_option("sqlalchemy.url", settings.DATABASE_URL.replace("%", "%%"))`

3. `backend/Dockerfile`
- Startup command already runs: migrations -> seed -> API.
- Healthcheck uses `${PORT}` fallback, compatible with App Engine.

### 2.4 Deploy backend

```bash
cd k8s-learning-project/backend
gcloud config set project alfahadh-practice
gcloud app deploy app.yaml
```

### 2.5 Backend verification

```bash
gcloud app logs tail -s default
```

Check:

- `https://alfahadh-practice.el.r.appspot.com/health/live`
- `https://alfahadh-practice.el.r.appspot.com/health/ready`
- `https://alfahadh-practice.el.r.appspot.com/api/docs`

## 3) Frontend deployment to Cloud Run

Frontend image supports runtime backend target through `API_UPSTREAM`.

### 3.1 Build and push frontend image

```bash
cd k8s-learning-project
gcloud config set project alfahadh-practice

gcloud artifacts repositories create web \
  --repository-format=docker \
  --location=asia-south1 || true

gcloud auth configure-docker asia-south1-docker.pkg.dev

gcloud builds submit ./frontend \
  --tag asia-south1-docker.pkg.dev/alfahadh-practice/web/frontend:latest
```

### 3.2 Deploy frontend service

```bash
gcloud run deploy frontend-web \
  --image asia-south1-docker.pkg.dev/alfahadh-practice/web/frontend:latest \
  --platform managed \
  --region asia-south1 \
  --allow-unauthenticated \
  --port 80 \
  --set-env-vars API_UPSTREAM=https://alfahadh-practice.el.r.appspot.com
```

### 3.3 Frontend verification

1. Open the Cloud Run URL from deploy output.
2. Confirm UI loads.
3. Confirm API proxy works:
- `<CLOUD_RUN_URL>/api/docs`
- `<CLOUD_RUN_URL>/api/health/live` (if routed by nginx config, otherwise use backend URL directly)

## 4) Real-time E2E test (App Engine + Cloud Run)

Use the frontend URL for API calls so you validate the proxy path too.

```bash
FRONTEND_URL="https://<your-cloud-run-url>"
BASE_URL="$FRONTEND_URL/api"
EMAIL="appengine$(date +%Y%m%d%H%M%S)@example.com"
PASS="TestPass123!"

curl -sS -X POST "$BASE_URL/auth/register" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASS\",\"full_name\":\"AppEngine User\"}"

TOKEN=$(curl -sS -X POST "$BASE_URL/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=$EMAIL&password=$PASS" | python3 -c 'import json,sys; print(json.load(sys.stdin)["access_token"])')

ORDER_ID=$(curl -sS -X POST "$BASE_URL/orders/" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"title":"Cloud order","description":"gae test","total_amount":99.99,"priority":4}' \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])')

curl -sS "$BASE_URL/orders/$ORDER_ID" -H "Authorization: Bearer $TOKEN"
curl -sS "$BASE_URL/orders/" -H "Authorization: Bearer $TOKEN"
```

Watch logs in parallel while testing:

```bash
gcloud app logs tail -s default
gcloud run services logs tail frontend-web --region asia-south1
```

Expected:

- Register/login success.
- Order create/read success.
- No `500` in App Engine logs.

## 5) Future service change map (Cloud SQL/Redis swaps)

### 5.1 If Cloud SQL is replaced with AWS RDS (PostgreSQL)

Required changes:

1. `backend/app.yaml`
- Change `DATABASE_URL` from socket form to TCP form:
  - `postgresql+psycopg2://<user>:<encoded_pass>@<rds-endpoint>:5432/<db>`

2. `backend/app.yaml`
- Remove `beta_settings.cloud_sql_instances` (Cloud SQL specific).

3. Network path
- Ensure App Engine can reach RDS (private connectivity strongly recommended):
  - Serverless VPC Access + VPN/Interconnect/peering design.

4. TLS
- Add RDS-required SSL options in URL/query params if enforced.

### 5.2 If Redis provider changes

Update all Redis-related URLs in `backend/app.yaml`:

- `REDIS_URL`
- `CELERY_BROKER_URL`
- `CELERY_RESULT_BACKEND`

Rules:

- Use `redis://` or `rediss://` as required by provider.
- URL-encode password special chars.
- Keep DB suffix (`/0`, `/1`, `/2`) only if provider supports it.

### 5.3 Other files to update in non-App-Engine branches

- `backend/.env.example`
- `docker-compose.yml`
- `k8s/backend/secret.yaml`

If CI/CD is used, also update corresponding secret variables in pipeline settings.

## 6) Ubuntu VM deployment (separate containers, no compose)

This section is for your `deploy/ubuntu-vm-separate-containers` branch.

### 6.1 Install Docker on Ubuntu VM

```bash
sudo apt update
sudo apt install -y ca-certificates curl gnupg
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo \"$VERSION_CODENAME\") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo usermod -aG docker $USER
newgrp docker
```

### 6.2 Build images

```bash
git clone <YOUR_REPO_URL>
cd k8s-learning-project

docker build -t k8s-backend ./backend
docker build -t k8s-frontend ./frontend
```

### 6.3 Create network and volumes

```bash
docker network create k8s-net
docker volume create pg_data
docker volume create redis_data
```

### 6.4 Start Postgres and Redis

```bash
docker run -d --name postgres \
  --restart unless-stopped \
  --network k8s-net \
  -e POSTGRES_DB=app_db \
  -e POSTGRES_USER=app_user \
  -e POSTGRES_PASSWORD=app_password \
  -v pg_data:/var/lib/postgresql/data \
  postgres:16-alpine

docker run -d --name redis \
  --restart unless-stopped \
  --network k8s-net \
  -v redis_data:/data \
  redis:7-alpine redis-server --appendonly yes
```

### 6.5 Start backend API

```bash
docker run -d --name backend \
  --restart unless-stopped \
  --network k8s-net \
  -p 8000:8000 \
  -e ENVIRONMENT=vm \
  -e SECRET_KEY=change-me-before-prod \
  -e ACCESS_TOKEN_EXPIRE_MINUTES=60 \
  -e API_PREFIX=/api \
  -e CORS_ORIGINS=http://<VM_PUBLIC_IP>:8080 \
  -e DATABASE_URL=postgresql+psycopg2://app_user:app_password@postgres:5432/app_db \
  -e REDIS_URL=redis://redis:6379/0 \
  -e CELERY_BROKER_URL=redis://redis:6379/0 \
  -e CELERY_RESULT_BACKEND=redis://redis:6379/0 \
  k8s-backend
```

### 6.6 Start worker

```bash
docker run -d --name worker \
  --restart unless-stopped \
  --network k8s-net \
  -e ENVIRONMENT=vm \
  -e SECRET_KEY=change-me-before-prod \
  -e API_PREFIX=/api \
  -e DATABASE_URL=postgresql+psycopg2://app_user:app_password@postgres:5432/app_db \
  -e REDIS_URL=redis://redis:6379/0 \
  -e CELERY_BROKER_URL=redis://redis:6379/0 \
  -e CELERY_RESULT_BACKEND=redis://redis:6379/0 \
  k8s-backend \
  celery -A app.workers.celery_app.celery_app worker --loglevel=info
```

### 6.7 Start frontend

```bash
docker run -d --name frontend \
  --restart unless-stopped \
  --network k8s-net \
  -p 8080:80 \
  -e API_UPSTREAM=http://backend:8000 \
  k8s-frontend
```

Open:

- `http://<VM_PUBLIC_IP>:8080`

## 7) Real-time testing on Ubuntu VM

### 7.1 Service status and logs

```bash
docker ps
docker logs -f backend
docker logs -f worker
```

### 7.2 Health and readiness

```bash
curl http://<VM_PUBLIC_IP>:8000/health/live
curl http://<VM_PUBLIC_IP>:8000/health/ready
curl http://<VM_PUBLIC_IP>:8080/api/health/live
```

### 7.3 Functional API test through frontend

```bash
BASE_URL="http://<VM_PUBLIC_IP>:8080/api"
EMAIL="vm$(date +%Y%m%d%H%M%S)@example.com"
PASS="TestPass123!"

curl -sS -X POST "$BASE_URL/auth/register" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASS\",\"full_name\":\"VM User\"}"

TOKEN=$(curl -sS -X POST "$BASE_URL/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=$EMAIL&password=$PASS" | python3 -c 'import json,sys; print(json.load(sys.stdin)["access_token"])')

ORDER_ID=$(curl -sS -X POST "$BASE_URL/orders/" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"title":"VM order","description":"test","total_amount":49.99,"priority":3}' \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])')

curl -sS "$BASE_URL/orders/$ORDER_ID" -H "Authorization: Bearer $TOKEN"
curl -sS "$BASE_URL/orders/" -H "Authorization: Bearer $TOKEN"
```

### 7.4 Worker validation

1. Keep `docker logs -f worker` open.
2. Create an order from UI or API.
3. Confirm worker receives and processes task logs.

## 8) Before pushing each branch

1. Remove hardcoded secrets and use environment/secret manager values.
2. Keep only deployment-specific config for that branch.
3. Validate end-to-end once after every change:
- health/live
- register/login
- create/list order
- worker logs
