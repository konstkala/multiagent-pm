# What's left (as of 2026-10-19)

A handover: everything below is open. Done work is in [CHANGELOG.md](../../CHANGELOG.md). The
original plan is in [product-v1](2026-10-16-product-v1.md); the roadmap with learning goals is in
[docs/learning/roadmap.md](../learning/roadmap.md).

**State:** milestones 1–7a are done, CI is green, the repo is public
(https://github.com/konstkala/multiagent-pm). The UI redesign ("C · Paper", mockups at
https://claude.ai/artifact/3jyxBC1WQxHqey8ER8CYg8) is mostly done.

## To do by you (nobody else can)
- [ ] GitHub → Settings → Emails: tick "Keep my email addresses private" and "Block command line
  pushes that expose my email".
- [ ] Decide the 6 Dependabot pull requests. Advice: merge Mailpit, SeaweedFS and ESLint; close Node
  25, `@types/node` 26 and TypeScript 7 (fails CI).
- [ ] Optional: delete the private repo `multiagent-pm-private-old` in its GitHub settings.
- [ ] Optional: add an `ANTHROPIC_API_KEY` repository secret (with a spend limit) to run the E2E
  workflow in Actions. Never paste it in a chat.
- [ ] Optional: Google sign-in is built but off until you add a Google OAuth client to
  `backend/.env`.

## Frontend: finish the redesign (small)
- [ ] A deliberate pass over the screens not reviewed yet: sign-up, forgot/reset password, invite,
  verify email, the profile editor and the CV review screen (light, dark, phone).
- [ ] shadcn/ui was planned but not needed yet. Add it where a screen needs real dialogs or menus
  (for example confirming "remove member").
- [ ] Empty states and loading placeholders; small confirmations ("saved") instead of silent success.
- [ ] A Content-Security-Policy header (a known gap since milestone 1).
- [ ] Keyboard shortcuts and a command palette (⌘K).
- [ ] README: screenshots (light and dark, from `docs/screenshots/`), then ADR 0021 (tokens,
  next-themes, why shadcn was deferred), glossary entries (Playwright, axe, MCP, design tokens),
  roadmap tick for browser tests.
- [ ] Priority stays "Not set" on most tickets because triage only suggests it. Decide whether the
  list should show the suggested value.

## AI engineering
- [ ] **Evaluation set** from the recorded manager decisions (triage kept/edited/dropped, assignment
  hit rate): per-field accuracy, cost and p95, run in CI on a schedule. This is the main missing
  AI-engineering piece.
- [ ] Langfuse traces (tokens, cost and latency per run) in a dashboard.
- [ ] Check prompt caching hit rates; Batch API for a weekly project digest (about $0.0005 per
  project per week).
- [ ] Revisit LangGraph only when an agent needs branching or tool loops (ADR 0016).

## DevOps
- [ ] **M8 Kubernetes** at $0: a local cluster (kind) running the GHCR images, Helm chart, probes
  (the worker's `python -m app.healthcheck` is the liveness probe), rollouts and rollback.
  Guide: [containers-kubernetes](../learning/containers-kubernetes.md).
- [ ] **M7b cloud**: Terraform, staging then production, keyless login from Actions (OIDC), billing
  alert, Neon for Postgres, R2/S3 for files. Postponed on purpose; see ADR 0020.
- [ ] Observability in production: uptime check, alerts, log dashboards, SLOs (p95 ≤ 10 s
  interactive), a backup and restore drill, a k6 load test.
- [ ] A pull-request flow with required checks and review (today the owner pushes to `main`).
- [ ] Base images pinned by digest, with Dependabot moving them (ADR 0020 consequence).

## Product ideas (not committed to)
- Email notifications (assigned to you, a question from the agent, due soon).
- Real-time updates instead of polling, and agent progress streaming.
- Ticket templates, bulk edit, saved filters, an activity feed per project.
- Time off for employees, so assignment skips people who are away.
- Reassign when someone leaves; export; audit-log screen.

## Known gaps (from the plans)
- Production proxy settings: rate limits trust `X-Forwarded-For` from anyone in development; an
  edge proxy must set it in production.
- Dashboards are computed on request; precompute daily rollups only when slow (rule: p95 over 300 ms).
- History before 17 Oct is approximate (rebuilt from ticket state).

## How to start the next session
1. `docker compose up -d --build --wait`, then `cd backend && uv run python -m scripts.seed_demo`.
2. Read this file and CHANGELOG.md. Say which block to take; features start in plan mode
   (plans go to `docs/plans/`, decisions to `docs/adr/`).
3. Before saying done: ruff, pyright, pytest, `npm run check`, `npx playwright test`, and the
   `/smoke` skill for anything touching the backend flows.
