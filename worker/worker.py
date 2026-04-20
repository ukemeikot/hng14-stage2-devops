import redis
import time
import os
import signal
import sys
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", None)

r = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    password=REDIS_PASSWORD,
    decode_responses=True,
)

# Graceful shutdown flag
shutdown = False


def handle_sigterm(signum, frame):
    global shutdown
    logger.info("Received SIGTERM — finishing current job then exiting.")
    shutdown = True


signal.signal(signal.SIGTERM, handle_sigterm)
signal.signal(signal.SIGINT, handle_sigterm)


def process_job(job_id):
    logger.info(f"Processing job {job_id}")
    time.sleep(2)  # simulate work
    r.hset(f"job:{job_id}", "status", "completed")
    logger.info(f"Done: {job_id}")


while not shutdown:
    job = r.brpop("jobs", timeout=5)
    if job:
        _, job_id = job
        process_job(job_id)

logger.info("Worker exited cleanly.")
sys.exit(0)
