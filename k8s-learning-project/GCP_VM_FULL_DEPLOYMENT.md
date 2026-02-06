# Full Deployment Guide on GCP VM (Compute Engine)

This guide is for learning and realistic deployment flow on a single GCP VM.
It includes:
- VM sizing and configuration
- Required software installation
- Redis/PostgreSQL setup options
- Application deployment steps
- Credential update points in code and configs
- Health check endpoints
- A practical learning task cheat sheet

---

## 1) VM configuration requirements

Recommended OS:
- Ubuntu 22.04 LTS

Recommended VM shape:
- Learning/dev: `e2-standard-2` (2 vCPU, 8 GB RAM, 30+ GB disk)
- Better learning/staging: `e2-standard-4` (4 vCPU, 16 GB RAM, 50+ GB disk)

Network/firewall ports:
- `22` SSH
- `80` HTTP
- `443` HTTPS (if TLS termination enabled)
- `8080` Frontend (optional if not reverse-proxied)
- `8000` FastAPI (optional, restrict to private access)
- `9090` Prometheus (optional, private IP only recommended)
- `30300` Grafana (optional, private IP only recommended)

GCP VM creation example:
```bash
gcloud compute instances create k8s-learning-vm \
  --project <GCP_PROJECT_ID> \
  --zone us-central1-a \
  --machine-type e2-standard-4 \
  --image-family ubuntu-2204-lts \
  --image-project ubuntu-os-cloud \
  --boot-disk-size 50GB \
  --tags http-server,https-server
```

---

## 2) Base installation requirements on VM

SSH into VM:
```bash
gcloud compute ssh k8s-learning-vm --zone us-central1-a
```

System tools:
```bash
sudo apt-get update
sudo apt-get upgrade -y
sudo apt-get install -y \
  git curl wget ca-certificates gnupg lsb-release \
  python3 python3-venv python3-pip \
  build-essential
```

Install Docker + Compose plugin:
```bash
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo \"$VERSION_CODENAME\") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo usermod -aG docker $USER
newgrp docker
```

Clone project:
```bash
git clone <YOUR_REPO_URL>
cd k8s-learning-project
```

---

## 3) Deployment option A (recommended): Run everything with Docker Compose

This option already includes PostgreSQL + Redis containers.

1. Configure env:
```bash
cp backend/.env.example backend/.env
```

2. Edit secret values in `backend/.env`:
- `SECRET_KEY`
- `DATABASE_URL`
- `REDIS_URL`
- `CELERY_BROKER_URL`
- `CELERY_RESULT_BACKEND`
- `DEFAULT_ADMIN_EMAIL`
- `DEFAULT_ADMIN_PASSWORD`
- `CORS_ORIGINS`

3. Start services:
```bash
docker compose up --build -d
```

4. Verify:
```bash
docker compose ps
docker compose logs -f backend
docker compose logs -f worker
```

5. Access:
- Frontend: `http://<VM_EXTERNAL_IP>:8080`
- API docs: `http://<VM_EXTERNAL_IP>:8000/api/docs`
- Metrics: `http://<VM_EXTERNAL_IP>:8000/metrics`

---

## 4) Deployment option B (native installation): Install PostgreSQL + Redis on VM host

Use this only if you want to learn service-level setup without containerized DB/cache.

### Install PostgreSQL
```bash
sudo apt-get install -y postgresql postgresql-contrib
sudo systemctl enable postgresql
sudo systemctl start postgresql
```

Create DB/user:
```bash
sudo -u postgres psql -c "CREATE DATABASE app_db;"
sudo -u postgres psql -c "CREATE USER app_user WITH ENCRYPTED PASSWORD 'change_this_password';"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE app_db TO app_user;"
```

### Install Redis
```bash
sudo apt-get install -y redis-server
sudo systemctl enable redis-server
sudo systemctl start redis-server
```

Optional Redis hardening (`/etc/redis/redis.conf`):
- set `bind 127.0.0.1`
- set `protected-mode yes`
- optionally set `requirepass <strong_password>`

Then:
```bash
sudo systemctl restart redis-server
```

### Run backend + worker against host services

1. Backend env:
```bash
cd k8s-learning-project/backend
cp .env.example .env
```

2. Edit `.env` with host-native URLs:
- `DATABASE_URL=postgresql+psycopg2://app_user:change_this_password@127.0.0.1:5432/app_db`
- `REDIS_URL=redis://127.0.0.1:6379/0`
- `CELERY_BROKER_URL=redis://127.0.0.1:6379/1`
- `CELERY_RESULT_BACKEND=redis://127.0.0.1:6379/2`
- `SECRET_KEY=<new_secret>`

3. Install Python dependencies:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

4. Migrate + seed:
```bash
alembic upgrade head
python -m app.db.seed
```

5. Start API:
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

6. Start worker (new terminal):
```bash
source .venv/bin/activate
celery -A app.workers.celery_app.celery_app worker --loglevel=info
```

7. Serve frontend with Nginx container:
```bash
cd ../frontend
docker build -t k8s-learning-frontend .
docker run -d --name frontend -p 8080:80 k8s-learning-frontend
```

---

## 5) Exactly where to change credentials in this project

### Primary places to update

1. Local env template:
- `backend/.env.example`

2. Runtime config defaults (fallback values only):
- `backend/app/core/config.py`

3. Docker compose env overrides:
- `docker-compose.yml`

4. Kubernetes secrets (if deploying to K8s):
- `k8s/backend/secret.yaml`
- `k8s/monitoring/grafana.yaml`

5. CI/CD secret references:
- `cicd/github-actions.yaml`
- `cicd/gitlab-ci.yaml`

### Important credential variables

- `SECRET_KEY`
- `DATABASE_URL`
- `REDIS_URL`
- `CELERY_BROKER_URL`
- `CELERY_RESULT_BACKEND`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `POSTGRES_DB`
- `DEFAULT_ADMIN_EMAIL`
- `DEFAULT_ADMIN_PASSWORD`

---

## 6) Health check paths and monitoring paths

FastAPI health checks:
- Liveness: `GET /health/live`
- Readiness: `GET /health/ready`

Metrics:
- `GET /metrics`

Examples:
```bash
curl http://127.0.0.1:8000/health/live
curl http://127.0.0.1:8000/health/ready
curl http://127.0.0.1:8000/metrics
```

---

## 7) Optional production-hardening checklist for VM

- Use HTTPS with Nginx + Certbot
- Restrict `8000`, `9090`, `30300` to private/internal access
- Rotate secrets and remove defaults
- Enable automated backups for PostgreSQL data
- Add log rotation and centralized logging
- Run backend/worker as `systemd` services
- Add UFW firewall rules
- Patch OS regularly

---

## 8) Learning task cheat sheet (real-time project style)

Use this sequence to learn like a real platform engineer.

Task 1: Bring up stack and validate probes
```bash
docker compose up --build -d
curl http://localhost:8000/health/live
curl http://localhost:8000/health/ready
```
Expected:
- both endpoints return success

Task 2: Validate auth flow
1. Register from frontend or `/api/auth/register`
2. Login and capture JWT from `/api/auth/login`
3. Call `/api/users/me` with `Authorization: Bearer <token>`

Task 3: Validate order lifecycle
1. Create order
2. Observe initial status `pending`
3. Watch worker logs and confirm status moves to `processing/completed`
```bash
docker compose logs -f worker
```

Task 4: Understand caching behavior
1. Call `GET /api/orders/` repeatedly
2. Create/update/delete order
3. Re-call list endpoint and see cache invalidation effects

Task 5: Break and recover dependencies
1. Stop Redis:
   ```bash
   docker compose stop redis
   ```
2. Read readiness failure:
   ```bash
   curl http://localhost:8000/health/ready
   ```
3. Start Redis and verify recovery:
   ```bash
   docker compose start redis
   ```

Task 6: Validate metrics and dashboards
1. Generate traffic via frontend/API
2. Check `/metrics`
3. If on K8s, inspect Prometheus targets and Grafana panels

Task 7: Practice DB migration workflow
1. Add model field
2. Generate migration
3. Apply migration
4. Seed data and verify API response

Task 8: Practice CI/CD failure analysis
1. Introduce a lint issue
2. Push branch and inspect failed pipeline
3. Fix issue and re-run

Task 9: Practice incident debugging drill
1. Worker queue backlog simulation
2. Inspect logs, metrics, readiness
3. Identify root cause and write short postmortem

Task 10: Practice deploy rollback
1. Deploy new image tag
2. Trigger failure (bad env var)
3. Roll back image tag and verify service restoration

