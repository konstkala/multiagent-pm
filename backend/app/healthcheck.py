"""Worker liveness: `python -m app.healthcheck` exits 0 while the worker's loop is turning.

A worker serves no HTTP, so it proves it's alive by touching a file on every loop
(app/worker.py). Docker's health check, and later a Kubernetes liveness probe, run this.
Kept free of app imports: it runs every few seconds.
"""

import sys
import tempfile
import time
from pathlib import Path

HEARTBEAT = Path(tempfile.gettempdir()) / "worker-heartbeat"
# Longer than the slowest job (one LLM call, retries included): a busy worker isn't a dead one.
MAX_AGE_SECONDS = 120


def worker_is_healthy(heartbeat: Path = HEARTBEAT, max_age: float = MAX_AGE_SECONDS) -> bool:
    try:
        return time.time() - heartbeat.stat().st_mtime < max_age
    except FileNotFoundError:
        return False


if __name__ == "__main__":
    sys.exit(0 if worker_is_healthy() else 1)
