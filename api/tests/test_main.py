"""
Unit tests for api/main.py

Redis is fully mocked — no real Redis required.
"""
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient


# ── Patch redis.Redis before importing the app ────────────────────────────────
@pytest.fixture(autouse=True)
def mock_redis():
    """Replace redis.Redis with a MagicMock for every test."""
    with patch("redis.Redis") as mock_cls:
        mock_instance = MagicMock()
        mock_cls.return_value = mock_instance
        yield mock_instance


@pytest.fixture()
def client(mock_redis):
    from main import app  # import after Redis is mocked
    return TestClient(app)


# ── Test 1: Health endpoint returns 200 when Redis is reachable ───────────────
def test_health_ok(client, mock_redis):
    mock_redis.ping.return_value = True
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


# ── Test 2: Health endpoint returns 503 when Redis is unreachable ─────────────
def test_health_redis_down(client, mock_redis):
    mock_redis.ping.side_effect = Exception("Connection refused")
    response = client.get("/health")
    assert response.status_code == 503
    assert "Redis unreachable" in response.json()["detail"]


# ── Test 3: POST /jobs creates a job and returns a job_id ────────────────────
def test_create_job(client, mock_redis):
    response = client.post("/jobs")
    assert response.status_code == 200
    data = response.json()
    assert "job_id" in data
    # Verify Redis calls were made
    mock_redis.lpush.assert_called_once()
    mock_redis.hset.assert_called_once()
    # The queue name must be "jobs"
    args, _ = mock_redis.lpush.call_args
    assert args[0] == "jobs"


# ── Test 4: GET /jobs/{id} returns the job status ────────────────────────────
def test_get_job_found(client, mock_redis):
    mock_redis.hget.return_value = "queued"
    response = client.get("/jobs/test-job-id")
    assert response.status_code == 200
    data = response.json()
    assert data["job_id"] == "test-job-id"
    assert data["status"] == "queued"


# ── Test 5: GET /jobs/{id} returns 404 when job does not exist ───────────────
def test_get_job_not_found(client, mock_redis):
    mock_redis.hget.return_value = None
    response = client.get("/jobs/nonexistent-id")
    assert response.status_code == 404
    assert response.json()["detail"] == "Job not found"


# ── Test 6: Created job ID is a valid UUID ────────────────────────────────────
def test_create_job_returns_uuid(client, mock_redis):
    import uuid
    response = client.post("/jobs")
    assert response.status_code == 200
    job_id = response.json()["job_id"]
    # This will raise ValueError if not a valid UUID
    uuid.UUID(job_id)


# ── Test 7: Completed job status is returned correctly ───────────────────────
def test_get_job_completed(client, mock_redis):
    mock_redis.hget.return_value = "completed"
    response = client.get("/jobs/some-finished-job")
    assert response.status_code == 200
    assert response.json()["status"] == "completed"
