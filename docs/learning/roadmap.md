# Learning roadmap: DevOps + AI engineering

Every skill is practiced on this project, not in a tutorial. Tick a box when you've done it here.
Phases refer to [the triage v1 plan](../plans/2026-10-16-ticket-triage-v1.md).

## DevOps

| ✓ | Skill | What you do in this project | When |
|---|---|---|---|
| [ ] | Reproducible environments | `uv` lockfile, `.env` config (12-factor), Docker Compose for Postgres | Phase 0 |
| [ ] | Database migrations | Alembic: versioned, reviewable schema changes; never edit applied ones | Phase 0+ |
| [ ] | Health checks | Liveness (`/health`) vs readiness (`/health/db`), used by Docker/cloud probes | Phase 0 |
| [ ] | Git workflow | Branches, small PRs, protected `main`, conventional commits, code review | Phase 0.5 |
| [ ] | CI | GitHub Actions: lint, typecheck, tests against a Postgres service container, caching | Phase 0.5 |
| [ ] | Quality gates | pre-commit hooks (ruff, gitleaks), required checks before merge | Phase 0.5 |
| [ ] | Containers | Full track: [containers → Kubernetes](containers-kubernetes.md), modules 1–9 | Phase 0 → 7 |
| [ ] | Secrets | `.env` locally, GitHub Secrets in CI, cloud secret manager in prod; secret scanning | Phase 1+ |
| [ ] | CD | Build → push to GHCR → deploy; migrations in the pipeline; staging and prod; rollback | Phase 7 |
| [ ] | Infrastructure as Code | Terraform for cloud resources; remote state; `plan` output in the PR | Phase 7 |
| [ ] | Observability | Structured logs, metrics, OpenTelemetry traces, dashboards, alerts | Phase 1+ |
| [ ] | SLOs | p95 ≤ 10s interactive, error-rate targets, alerts on burn rate | Phase 7 |
| [ ] | Reliability | Graceful shutdown, retries with backoff, load tests (k6), backup + restore drill | Phase 7 |
| [ ] | Security | Dependabot, SAST, least-privilege credentials, HTTPS, OWASP Top 10 | Ongoing |
| [x] | Authentication | Password hashing, sessions, CSRF/CORS, rate limits, email tokens, Google OIDC with PKCE | Milestone 1 |
| [ ] | Reverse proxies | Next.js proxies /api; X-Forwarded-For and trusted proxies (dev done; production edge proxy later) | Milestone 1, 7 |
| [ ] | Cost (FinOps) | Cloud cost next to LLM cost; budgets and alerts | Phase 7 |
| [ ] | Kubernetes | [Track](containers-kubernetes.md) modules 10–12: kind, Deployments, probes, Helm, rollouts, GitOps | Phase 8 |

## AI engineering

| ✓ | Skill | What you do in this project | When |
|---|---|---|---|
| [ ] | LLM API fundamentals | Tokens, context, pricing, effort, thinking, streaming, stop reasons | Phase 1 |
| [x] | LLM gateway | `core/llm`: routing, retries, refusals, cost logging, budget guard (first real call passed 2026-10-16) | Phase 1 |
| [ ] | LLM observability | Langfuse traces: tokens, $ and latency per run | Phase 1 |
| [x] | Embeddings + retrieval | Local embeddings, pgvector HNSW, similarity thresholds | Phase 3 |
| [ ] | Structured output | PydanticAI typed outputs, validation, retries on bad output | Phase 4 |
| [ ] | Prompt engineering + caching | Prompt files, stable prefix first, cache hit rate | Phase 4 |
| [ ] | Workflows vs agents | LangGraph state, nodes, checkpoints; why triage is a workflow | Phase 4 |
| [ ] | Human-in-the-loop | LangGraph interrupts, approval API, resume | Phase 4–5 |
| [ ] | Background jobs | Postgres queue with `SKIP LOCKED`, worker process | Phase 4 |
| [ ] | Evals | Labelled set, per-field accuracy, $/run, p95; eval in CI | Phase 5 |
| [ ] | LLM security | Prompt injection, untrusted input, tool permissions, OWASP LLM Top 10 | Phase 4+ |
| [ ] | Cost optimization | Model cascade (Haiku → Sonnet), Batch API, effort tuning | Later |
| [ ] | Agentic tool loops | A real agent where open-ended exploration pays off | Later |
| [ ] | Multi-agent | Orchestrator + workers for parallel work; measure the ~15× token cost | Later |
| [ ] | LLMOps | Prompt versioning, model A/B tests, gradual rollout | Later |
