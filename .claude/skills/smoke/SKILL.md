---
name: smoke
description: Rebuild the Docker Compose stack and run the end-to-end smoke tests (milestones 2-6) through the web proxy. Use after finishing a milestone or a risky change, before saying done. Costs about $0.003 in real Haiku calls per full run.
---

# Smoke test the running app

1. From the repo root: `docker compose up -d --build --wait` (rebuilds what changed, waits until every service is healthy). If a container isn't healthy, show `docker compose logs <service> --tail 50` and stop.
2. From `backend/`: `uv run python -m scripts.smoke` runs every suite; `uv run python -m scripts.smoke m4 m5` runs only those. Each suite clears the dev database's sign-up rate limits first (10 sign-ups per hour per IP would stop the next one). Development stack only.
3. Report per suite: passed/total, any FAIL lines with a likely cause, and the measured numbers the suites print (agent cost and latency, dashboard p95).
4. If something fails, look at `docker compose logs api worker --since 5m` before changing code: find the root cause first.

To smoke the images CI published instead of local builds:
`TAG=sha-<commit> docker compose -f docker-compose.yml -f compose.release.yml up -d --wait`, then step 2.
