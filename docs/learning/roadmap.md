# Learning roadmap: DevOps + AI engineering

Every skill is practiced on this project, not in a tutorial. Tick a box when you've done it here.
Phases refer to [the triage v1 plan](../plans/2026-10-16-ticket-triage-v1.md).

## DevOps

| ✓ | Skill | What you do in this project | When |
|---|---|---|---|
| [ ] | Reproducible environments | `uv` lockfile, `.env` config (12-factor), Docker Compose for Postgres | Phase 0 |
| [ ] | Database migrations | Alembic: versioned, reviewable schema changes; never edit applied ones | Phase 0+ |
| [ ] | Health checks | Liveness (`/health`) vs readiness (`/health/db`), used by Docker/cloud probes | Phase 0 |
| [ ] | Git workflow | Branches, small PRs, protected `main`, conventional commits, code review (done: `main` ruleset, history rewrite, a PR for the CI proof; to do: a PR-based flow) | Phase 0.5 |
| [x] | CI | GitHub Actions: lint, typecheck, tests against a Postgres service container, caching, API contract, SHA-pinned actions | Milestone 7a |
| [x] | Quality gates | pre-commit hooks (ruff, gitleaks), Trivy gate on images, Claude Code guard hook (required checks wait for a PR flow) | Milestone 7a |
| [ ] | Containers | Full track: [containers → Kubernetes](containers-kubernetes.md), modules 1–9 | Phase 0 → 7 |
| [ ] | Secrets | `.env` locally, GitHub Secrets in CI, cloud secret manager in prod; secret scanning | Phase 1+ |
| [ ] | CD | Build → push to GHCR → deploy; migrations in the pipeline; staging and prod; rollback (done: build once, push with SBOM + provenance, run by tag locally; to do: the cloud deploy in 7b) | Phase 7 |
| [ ] | Infrastructure as Code | Terraform for cloud resources; remote state; `plan` output in the PR | Phase 7 |
| [ ] | Observability | Structured logs, metrics, OpenTelemetry traces, dashboards, alerts | Phase 1+ |
| [ ] | SLOs | p95 ≤ 10s interactive, error-rate targets, alerts on burn rate | Phase 7 |
| [ ] | Reliability | Graceful shutdown, retries with backoff, load tests (k6), backup + restore drill | Phase 7 |
| [ ] | Security | Dependabot, SAST, least-privilege credentials, HTTPS, OWASP Top 10 (done: Dependabot, CodeQL, Trivy, secret scanning, least-privilege CI tokens) | Ongoing |
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
| [x] | Structured output | Gateway `complete_structured()` (SDK `messages.parse`), validated Pydantic output, limits enforced in code | Milestone 3 |
| [ ] | Prompt engineering + caching | Prompt files, stable prefix first, cache hit rate | Phase 4 |
| [x] | Workflows vs agents | Triage is a workflow: fixed steps, one call. Job + DB states over LangGraph until branching pays (ADR 0016) | Milestone 4 |
| [x] | Human-in-the-loop | Run states as the pause (`needs_answer`, `proposed`), approval API with edits, resume via a new job; LangGraph interrupts later | Milestone 3–4 |
| [x] | Background jobs | Postgres queue with `SKIP LOCKED`, worker process, retries with backoff, graceful shutdown | Milestone 3 |
| [ ] | Evals | Labelled set, per-field accuracy, $/run, p95; eval in CI | Phase 5 |
| [ ] | LLM security | Prompt injection, untrusted input, tool permissions, OWASP LLM Top 10 | Phase 4+ |
| [ ] | Cost optimization | Model cascade (Haiku → Sonnet), Batch API, effort tuning | Later |
| [ ] | Agentic tool loops | A real agent where open-ended exploration pays off | Later |
| [ ] | Multi-agent | Orchestrator + workers for parallel work; measure the ~15× token cost | Later |
| [ ] | LLMOps | Prompt versioning, model A/B tests, gradual rollout | Later |
