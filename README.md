# Job Processor — HNG Stage 2 DevOps

A containerised job-processing system built with:

- **Frontend** — Node.js / Express (port 3000)
- **API** — Python / FastAPI (port 8000)
- **Worker** — Python background processor
- **Queue** — Redis (internal only, not exposed)

---

## Prerequisites

| Tool | Minimum version | Install |
|------|----------------|---------|
| Docker | 24.x | https://docs.docker.com/get-docker/ |
| Docker Compose | v2.x (`docker compose`) | Bundled with Docker Desktop |
| Git | any | https://git-scm.com |

> **Windows users:** Use Docker Desktop with WSL 2 backend.

---

## Quick Start

### 1. Clone the repository

```bash
git clone https://github.com/ukemeikot/hng14-stage2-devops.git
cd hng14-stage2-devops
```

### 2. Configure environment variables

```bash
cp .env.example .env
```

Open `.env` and set your values:

```env
REDIS_PASSWORD=change_me_to_a_strong_password
API_URL=http://api:8000
```

> ⚠️ **Never commit `.env` to version control.** It is listed in `.gitignore`.

### 3. Bring the stack up

```bash
docker compose up --build -d
```

This builds all three images from scratch and starts them in detached mode.

### 4. Verify all services are healthy

```bash
docker compose ps
```

Expected output (all services show `healthy`):

```
NAME          IMAGE                    STATUS
api           hng-stage2-api           Up (healthy)
frontend      hng-stage2-frontend      Up (healthy)
worker        hng-stage2-worker        Up (healthy)
redis         redis:7-alpine           Up (healthy)
```

### 5. Open the dashboard

Navigate to **http://localhost:3000** in your browser.

Click **"Submit New Job"** — the job will appear as `queued`, then transition to `completed` within a few seconds.

---

## Service Architecture

```
Browser
  │
  ▼
Frontend :3000  ──POST /jobs──►  API :8000  ──lpush jobs──►  Redis
                ◄─job_id──────                               │
                                                             │
                                              Worker ◄──brpop jobs──┘
                                              Worker ──hset completed──► Redis
```

All services communicate over the internal Docker network `app-net`. Redis is never exposed on the host machine.

---

## Environment Variables

| Variable | Service | Default | Description |
|----------|---------|---------|-------------|
| `REDIS_HOST` | api, worker | `redis` | Redis service hostname |
| `REDIS_PORT` | api, worker | `6379` | Redis port |
| `REDIS_PASSWORD` | api, worker, redis | *(required)* | Redis auth password |
| `API_URL` | frontend | `http://api:8000` | Internal API base URL |

---

## Useful Commands

```bash
# Bring the stack down (removes containers, keeps images)
docker compose down

# Bring the stack down and remove all volumes
docker compose down -v

# Tail logs from all services
docker compose logs -f

# Tail logs from a single service
docker compose logs -f api

# Rebuild a single service without restarting others
docker compose up --build -d api

# Run API unit tests
docker compose run --rm api pytest tests/ -v --cov=main --cov-report=term-missing
```

---

## CI/CD Pipeline

The GitHub Actions pipeline runs on every push and pull request:

| Stage | What it does |
|-------|-------------|
| `lint` | flake8 (Python), eslint (JavaScript), hadolint (Dockerfiles) |
| `test` | pytest with Redis mocked; uploads coverage report artifact |
| `build` | Builds all 3 images, tags with git SHA + `latest`, pushes to registry |
| `security-scan` | Trivy scans all images; fails on CRITICAL findings; uploads SARIF |
| `integration-test` | Full stack starts inside runner; submits a job; asserts `completed` |
| `deploy` | Runs on `main` only — rolling update to EC2 (zero downtime) |

---

## Rolling Deploy to EC2

The deploy stage performs a scripted rolling update:

1. SSH into EC2
2. Pull new image
3. Start new container; wait up to 60 s for its health check to pass
4. If healthy: stop old container
5. If not healthy within 60 s: abort; old container remains running

### Required GitHub Secrets

| Secret | Value |
|--------|-------|
| `EC2_HOST` | Public IP or hostname of your EC2 instance |
| `EC2_USER` | SSH username (e.g. `ubuntu`) |
| `EC2_SSH_KEY` | Private key corresponding to the instance's key pair |
| `REDIS_PASSWORD` | Production Redis password |

---

## Project Structure

```
.
├── api/
│   ├── main.py              # FastAPI application
│   ├── requirements.txt     # Pinned Python dependencies
│   ├── Dockerfile
│   └── tests/
│       └── test_main.py     # pytest unit tests
├── worker/
│   ├── worker.py            # Background job processor
│   ├── requirements.txt     # Pinned Python dependencies
│   └── Dockerfile
├── frontend/
│   ├── app.js               # Express server
│   ├── package.json
│   ├── package-lock.json
│   ├── Dockerfile
│   └── views/
│       └── index.html
├── docker-compose.yml
├── .env.example             # Template — copy to .env and fill in values
├── .gitignore
├── FIXES.md                 # All bugs found and fixed
└── README.md
```

---

## What a Successful Startup Looks Like

```
✔ Container redis     Healthy
✔ Container api       Healthy
✔ Container worker    Healthy
✔ Container frontend  Healthy
```

Logs:

```
api_1      | INFO:     Application startup complete.
api_1      | INFO:     Uvicorn running on http://0.0.0.0:8000
worker_1   | 2026-04-20 [INFO] Worker started. Waiting for jobs...
frontend_1 | Frontend running on port 3000
```

Browser at http://localhost:3000 shows the Job Processor Dashboard. Submitting a job prints `Submitted: <uuid>` then updates to `completed` within ~2 seconds.
