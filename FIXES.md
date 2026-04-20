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

## Fix 4 — `api/main.py`, Line 13/15: Inconsistent queue key name

**Problem:** The API pushed jobs onto a Redis list called `"job"` (singular) with `r.lpush("job", job_id)`. The worker consumed from a list called `"job"` (via `r.brpop("job", ...)`). While they happened to match, the name `"job"` is ambiguous and collides with the hash keys `job:{id}`. Renamed to `"jobs"` for clarity and to eliminate the naming conflict.

**Change:**
```python
# Before
r.lpush("job", job_id)

# After
r.lpush("jobs", job_id)
```

---

## Fix 5 — `api/main.py`, Line 21: Silent 404 instead of HTTP error

**Problem:** When a job ID was not found, the handler returned `{"error": "not found"}` with HTTP 200. Clients (including the integration test) cannot distinguish a successful response from an error without parsing the body.

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

**Problem:** `import signal` was present at the top of the file, but no signal handlers were ever registered. This means `docker stop` (which sends `SIGTERM`) would immediately kill the worker process mid-job, corrupting any job in-flight and leaving it permanently in `queued` status.

**Change:** Added proper SIGTERM and SIGINT handlers:
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

**Problem:** Worker consumed from `"job"` — renamed to `"jobs"` to match the API fix.

**Change:**
```python
# Before
job = r.brpop("job", timeout=5)

# After
job = r.brpop("jobs", timeout=5)
```

---

## Fix 11 — `worker/requirements.txt`, Line 1: No version pin

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

## Fix 12 — `frontend/app.js`, Line 6: Hardcoded API URL

**Problem:** `const API_URL = "http://localhost:8000"` hardcodes the API address. When the frontend runs in a container, it cannot reach `localhost:8000`; it must use the Docker service name `api`.

**Change:**
```javascript
// Before
const API_URL = "http://localhost:8000";

// After
const API_URL = process.env.API_URL || 'http://api:8000';
```

---

## Fix 13 — `frontend/app.js`: No `/health` endpoint

**Problem:** No health route existed, so Docker's `HEALTHCHECK` for the frontend had nothing to probe.

**Change:** Added:
```javascript
app.get('/health', (req, res) => {
  res.json({ status: 'ok' });
});
```

---

## Fix 14 — `api/.env`: Real credentials committed to the repository

**Problem:** The file `api/.env` was present in the repository containing `REDIS_PASSWORD=supersecretpassword123`. Secrets must never be committed to version control — this is an immediate disqualifying violation in production.

**Change:**
- Added `.env` to `.gitignore` at the repo root
- Removed `api/.env` from tracking (`git rm --cached api/.env`)
- Created `.env.example` with placeholder values documenting all required variables

---

## Fix 15 — `frontend/package.json`: No `package-lock.json`

**Problem:** Without a lockfile, `npm install` resolves dependency trees at build time, producing non-reproducible images and potential version drift.

**Change:** Added `package-lock.json` generated by running `npm install` once locally. Dockerfiles use `npm ci` (instead of `npm install`) to enforce the lockfile.
