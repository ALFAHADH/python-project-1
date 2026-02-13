# Kubernetes Deployment Issues Log

Date: February 13, 2026  
Project: `k8s-learning-project`  
Target: Google Kubernetes Engine (GKE)

## Summary

This document records the actual issues faced during Kubernetes deployment, with root cause and fix for each issue.

## Issue 1: Frontend pods restarted (`Error`, probes failed with `connection refused`)

- Symptom:
  - Frontend pods moved `Pending -> ContainerCreating -> Running -> Error`.
  - Events showed readiness/liveness probe failures on port 80.
- Root cause:
  - Nginx template env substitution risk with `/etc/nginx/templates/default.conf.template` can break native nginx variables.
  - Frontend was also pointed to an external backend URL that was not available.
- Fix:
  - Updated `frontend/Dockerfile` to limit env substitution to only `API_UPSTREAM`:
    - `NGINX_ENVSUBST_FILTER=^API_UPSTREAM$`
  - Set frontend deployment env to in-cluster backend when running full stack on GKE:
    - `API_UPSTREAM=http://backend-service:80`

## Issue 2: Worker pod liveness/readiness failed (`pgrep: not found`)

- Symptom:
  - Worker pod restarted repeatedly.
  - Events:
    - `Readiness probe failed: sh: 1: pgrep: not found`
    - `Liveness probe failed: sh: 1: pgrep: not found`
- Root cause:
  - `pgrep` is not installed in slim runtime image.
- Fix:
  - Updated `k8s/backend/worker-deployment.yaml` probes to:
    - `tr '\000' ' ' </proc/1/cmdline | grep -q celery`
  - Kept both probes (readiness + liveness) and set stable timings.

## Issue 3: Postgres CrashLoopBackOff (`initdb ... lost+found`)

- Symptom:
  - `postgres-0` in `CrashLoopBackOff`.
  - Logs:
    - `initdb: error: directory "/var/lib/postgresql/data" exists but is not empty`
    - `detail: It contains a lost+found directory`
- Root cause:
  - PostgreSQL data dir was mounted directly at volume root.
- Fix:
  - Set `PGDATA=/var/lib/postgresql/data/pgdata`.
  - Added pod `securityContext.fsGroup: 999`.
  - Recreated `postgres-0` pod.

## Issue 4: Backend init container failed (`alembic: not found`)

- Symptom:
  - Backend pods stuck in `Init:CrashLoopBackOff`.
  - Init logs:
    - `sh: alembic: not found`
- Root cause:
  - `alembic` executable not available in shell path in that init command.
- Fix:
  - Changed init command in `k8s/backend/deployment.yaml`:
    - from `alembic upgrade head`
    - to `python -m alembic upgrade head`

## Issue 5: Backend pods in `CreateContainerConfigError`

- Symptom:
  - Backend pods showed `CreateContainerConfigError`.
- Root cause:
  - Strict `runAsNonRoot: true` with current image/runtime user combination caused pod config validation/runtime conflict.
- Fix:
  - Removed `runAsNonRoot: true` from backend container `securityContext`.
  - Kept:
    - `allowPrivilegeEscalation: false`
    - dropped Linux capabilities.

## Issue 6: Frontend service missing (`services "frontend-service" not found`)

- Symptom:
  - `kubectl port-forward svc/frontend-service 8080:80` returned NotFound.
- Root cause:
  - Service manifest was not applied.
- Fix:
  - Applied:
    - `k8s/frontend/service.yaml`
    - `k8s/backend/service.yaml`

## Issue 7: Scheduling and autoscaling warnings

- Symptom:
  - Events:
    - `no nodes available to schedule pods`
    - `Node scale up ... failed: GCE quota exceeded`
- Root cause:
  - Temporary node capacity and/or quota pressure during scheduling.
- Fix:
  - Waited for schedulable capacity and continued after nodes became available.
  - Recommendation: increase quotas / set cluster capacity before rollout.

## Issue 8: `kubectl` not found on VM shell

- Symptom:
  - `-bash: kubectl: command not found`
- Root cause:
  - Command executed on host without kubectl installed or without correct environment.
- Fix:
  - Switched to Cloud Shell (kubectl preinstalled) and used cluster context there.

## Final Working State

At final check:
- `backend-api` pods: `Running`
- `backend-worker` pod: `Running`
- `postgres-0`: `Running`
- `redis`: `Running`
- `frontend-web`: `Running`

## Files changed during fixes

- `frontend/Dockerfile`
- `k8s/frontend/deployment.yaml`
- `k8s/frontend/service.yaml` (applied/used)
- `k8s/backend/deployment.yaml`
- `k8s/backend/worker-deployment.yaml`
- `k8s/backend/secret.yaml`
- `k8s/postgres/statefulset.yaml`

## Quick verification commands

```bash
kubectl -n k8s-learning get pods
kubectl -n k8s-learning get svc
kubectl -n k8s-learning logs deploy/backend-worker --tail=100
kubectl -n k8s-learning port-forward svc/frontend-service 8080:80
```

In another shell:

```bash
curl http://127.0.0.1:8080/api/health/live
curl http://127.0.0.1:8080/api/health/ready
```

