# Bug Fixes — HNG Stage 2 DevOps

This document records every issue found in the starter repository, organised by file.
Each entry states the file, the affected line(s), what was wrong, and exactly what was changed.

---

## Fix 1 — `api/main.py`, Line 8: Hardcoded Redis host

**Problem:** The Redis client was initialised with `host="localhost"`. Inside a Docker network, services are addressed by their service name, not `localhost`. This caused the API container to fail to connect to Redis at runtime.

**Change:**
```python
# Before
r = redis.Redis(host="localhost", port=6379)

# After
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, ...)
```

---

## Fix 2 — `api/main.py`, Line 8: Redis password ignored

**Problem:** The `.env` file committed in the repository defined `REDIS_PASSWORD=supersecretpassword123`, but the Redis client in `main.py` never read or used it. Any Redis instance launched with `--requirepass` would reject all connections from the API.

**Change:**
```python
# Before
r = redis.Redis(host="localhost", port=6379)

# After
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", None)
r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, password=REDIS_PASSWORD, ...)
```

---

## Fix 3 — `api/main.py`: No `/health` endpoint

**Problem:** There was no health check route. Docker's `HEALTHCHECK` instruction and `docker-compose.yml`'s `depends_on: condition: service_healthy` both require an HTTP endpoint to probe. Without one, health checks can never pass.

**Change:** Added:
```python
@app.get("/health")
def health():
    try:
        r.ping()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Redis unreachable: {e}")
    return {"status": "ok"}
```

---

## Fix 4 — `api/main.py`, Line 13: Ambiguous queue key name

**Problem:** The API pushed jobs onto a Redis list called `"job"` (singular) with `r.lpush("job", job_id)`. The name `"job"` conflicts with the hash keys `job:{id}` used to store job status. Renamed to `"jobs"` for clarity and to eliminate the naming ambiguity.

**Change:**
```python
# Before
r.lpush("job", job_id)

# After
r.lpush("jobs", job_id)
```

---

## Fix 5 — `api/main.py`, Line 21: Silent 404 instead of HTTP error

**Problem:** When a job ID was not found, the handler returned `{"error": "not found"}` with HTTP 200. Clients (including the integration test) cannot distinguish a successful response from a not-found error without parsing the body.

**Change:**
```python
# Before
return {"error": "not found"}

# After
raise HTTPException(status_code=404, detail="Job not found")
```

---

## Fix 6 — `api/requirements.txt`, Lines 1–3: No version pins

**Problem:** All three dependencies (`fastapi`, `uvicorn`, `redis`) were unpinned. This means `pip install` resolves to whatever is latest at build time, making images non-reproducible and vulnerable to breaking changes.

**Change:**
```
# Before
fastapi
uvicorn
redis

# After
fastapi==0.111.0
uvicorn[standard]==0.29.0
redis==5.0.4
python-dotenv==1.0.1
httpx==0.27.0
```

---

## Fix 7 — `worker/worker.py`, Line 6: Hardcoded Redis host

**Problem:** Same as Fix 1 — `host="localhost"` prevents the worker from connecting to Redis when running inside a Docker network.

**Change:**
```python
# Before
r = redis.Redis(host="localhost", port=6379)

# After
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, ...)
```

---

## Fix 8 — `worker/worker.py`, Line 6: Redis password ignored

**Problem:** Same as Fix 2 — the worker never used `REDIS_PASSWORD`, so it would fail to authenticate against a password-protected Redis.

**Change:**
```python
# Before
r = redis.Redis(host="localhost", port=6379)

# After
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", None)
r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, password=REDIS_PASSWORD, ...)
```

---

## Fix 9 — `worker/worker.py`, Lines 4 & 14–18: `signal` imported but never used

**Problem:** `import signal` was present at the top of the file, but no signal handlers were ever registered. This means `docker stop` (which sends `SIGTERM`) would immediately kill the worker process mid-job, corrupting any in-flight job and leaving it permanently stuck in `queued` status.

**Change:** Added proper SIGTERM and SIGINT handlers with a clean shutdown loop:
```python
shutdown = False

def handle_sigterm(signum, frame):
    global shutdown
    logger.info("Received SIGTERM — finishing current job then exiting.")
    shutdown = True

signal.signal(signal.SIGTERM, handle_sigterm)
signal.signal(signal.SIGINT, handle_sigterm)

while not shutdown:
    job = r.brpop("jobs", timeout=5)
    ...
```
The worker now finishes its current job and then exits cleanly.

---

## Fix 10 — `worker/worker.py`, Line 15: Queue name mismatch (paired with Fix 4)

**Problem:** Worker consumed from `"job"` — renamed to `"jobs"` to match the API.

**Change:**
```python
# Before
job = r.brpop("job", timeout=5)

# After
job = r.brpop("jobs", timeout=5)
```

---

## Fix 11 — `worker/worker.py`, Line 53: Missing trailing newline (W292)

**Problem:** The file ended without a trailing newline. This caused `flake8` to report `W292 no newline at end of file`, which would fail the lint stage of the CI pipeline.

**Change:** Added a trailing newline at the end of `worker.py`.

---

## Fix 12 — `worker/requirements.txt`, Line 1: No version pin

**Problem:** `redis` was unpinned, resulting in non-deterministic builds.

**Change:**
```
# Before
redis

# After
redis==5.0.4
python-dotenv==1.0.1
```

---

## Fix 13 — `frontend/app.js`, Line 6: Hardcoded API URL

**Problem:** `const API_URL = "http://localhost:8000"` hardcodes the API address. When the frontend runs in a container, it cannot reach `localhost:8000`; it must use the Docker service name `api`.

**Change:**
```javascript
// Before
const API_URL = "http://localhost:8000";

// After
const API_URL = process.env.API_URL || 'http://api:8000';
```

---

## Fix 14 — `frontend/app.js`: No `/health` endpoint

**Problem:** No health route existed, so Docker's `HEALTHCHECK` for the frontend had nothing to probe.

**Change:** Added:
```javascript
app.get('/health', (req, res) => {
  res.json({ status: 'ok' });
});
```

---

## Fix 15 — `api/.env`: Real credentials committed at wrong location

**Problem (credential exposure):** The file `api/.env` was tracked in version control and contained a real Redis password (`REDIS_PASSWORD=supersecretpassword123`). Secrets must never be committed to version control.

**Problem (wrong location):** Even if the credentials were safe, `api/.env` is the wrong place for this file. `docker compose` automatically loads variables only from a `.env` file at the **project root** (the same directory as `docker-compose.yml`). A `.env` inside `api/` is not loaded by Compose, and `api/main.py` does not call `load_dotenv()`, so the file had zero effect at runtime.

**Changes:**
- Added `.env` (and `*.env`) to `.gitignore` at the repo root to prevent re-committing
- Removed `api/.env` from git tracking: `git rm --cached api/.env`
- Deleted the `api/.env` file from disk entirely
- Created `.env` at the **project root** (from `.env.example`) — this is where Docker Compose reads it
- Created `.env.example` at the project root with placeholder values documenting all required variables

---

## Fix 16 — `frontend/package.json`: No `package-lock.json`

**Problem:** Without a lockfile, `npm install` resolves dependency trees at build time, producing non-reproducible images and potential version drift. The frontend `Dockerfile` uses `npm ci`, which requires a `package-lock.json` — without one, the Docker build would fail.

**Change:** Generated `package-lock.json` by running `npm install` once locally and committed it. The Dockerfile now uses `npm ci --omit=dev` to enforce the lockfile on every build.

---

## Fix 17 — `api/tests/test_main.py`: Incorrect mock strategy for Redis

**Problem:** The original test file patched `redis.Redis` (the class constructor) using `patch("redis.Redis")`. However, `main.py` creates the Redis client `r` at **module import time** as a module-level variable. By the time the patch was applied, `r` had already been assigned the real client object. As a result, endpoint functions called the real (unpatched) `r`, causing 5 of 7 tests to fail.

**Change:** Changed the mock strategy to patch `main.r` directly — replacing the already-created module-level instance with a `MagicMock`:
```python
# Before (did not intercept calls to the already-created r)
with patch("redis.Redis") as mock_cls:
    mock_instance = MagicMock()
    mock_cls.return_value = mock_instance

# After (replaces the live instance on the module itself)
mock = MagicMock()
with patch.object(main, "r", mock):
    yield mock
```
All 7 tests now pass with 100% code coverage.

---

## Fix 18 — `worker/Dockerfile` & `docker-compose.yml`: Worker healthcheck timing out

**Problem:** The worker HEALTHCHECK command (`python -c "import redis; r=redis.Redis(...); r.ping()"`) was given only 5 seconds to complete. On the first run, Python must initialise the interpreter, import the redis module, and open a TCP connection — this consistently exceeded the 5s timeout, causing `ExitCode: -1` and `Health check exceeded timeout (5s)`. The `start_period` of 15s was also too short for images that need to be pulled from scratch.

**Change:**

In `worker/Dockerfile`:
```dockerfile
# Before
HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "...redis.Redis(...); r.ping()"

# After
HEALTHCHECK --interval=15s --timeout=10s --start-period=20s --retries=3 \
    CMD python -c "...redis.Redis(..., socket_connect_timeout=3, socket_timeout=3); r.ping()"
```

In `docker-compose.yml` (api and worker healthchecks):
- Timeout increased from `5s` → `10s`
- `start_period` increased from `15s` → `30s`
- Added `socket_connect_timeout=3, socket_timeout=3` to the Redis call so the health check fails fast and predictably within the timeout window instead of hanging

---

## Fix 19 — `api/requirements.txt`: CRITICAL CVE in `h11` transitive dependency (CVE-2025-43859)

**Problem:** Trivy security scan (`vuln-type: library`) detected **CVE-2025-43859** (CRITICAL) — an HTTP request smuggling vulnerability in `h11 < 0.16.0`. The `h11` package is a transitive dependency pulled in by `uvicorn[standard]`. The pinned version `uvicorn==0.29.0` resolved to `h11==0.14.x`, which is vulnerable.

**CVE details:**
- **CVE-2025-43859** — HTTP/1.1 request smuggling via malformed `Content-Length` headers in `h11`
- Severity: **CRITICAL**
- Fixed in: `h11 >= 0.16.0`

**Change:**
```
# Before
fastapi==0.111.0
uvicorn[standard]==0.29.0   # pulls in h11==0.14.x (VULNERABLE)
httpx==0.27.0

# After
fastapi==0.115.12
uvicorn[standard]==0.34.2   # pulls in h11>=0.16.0 (PATCHED)
httpx==0.28.1
```

All 7 unit tests verified passing with the updated versions.

---

## Fix 20 — `.github/workflows/ci.yml`, Stage `security-scan`: Trivy scans were brittle and hard to debug

**Problem:** The security-scan job rebuilt images with `localhost:5000/...` tags and scanned them by image reference in a fresh GitHub Actions runner. That is brittle because the job-local registry is empty unless those rebuilt images are explicitly pushed into it, and a failing first scan also prevented useful diagnostic output for the remaining images. The workflow also tracked Trivy on `@master`, which is not reproducible.

**Changes:**
- Pinned the action version from `aquasecurity/trivy-action@master` to `aquasecurity/trivy-action@0.28.0`
- Reworked the security-scan job to export each rebuilt image as a tarball (`docker save`) and scan the tarballs directly with Trivy
- Split the scan into two passes:
  - SARIF generation with `exit-code: "0"` so reports are always produced
  - Enforcement pass with `format: table` and `exit-code: "1"` so the pipeline still fails on CRITICAL findings
- Uploaded both the SARIF files and the human-readable `.txt` scan outputs as artifacts
- Added explicit Trivy DB mirror environment variables for more reliable database downloads in CI

This keeps the stage compliant with the task requirement to fail on CRITICAL findings while making failures actionable instead of opaque.
