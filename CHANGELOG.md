# Changelog

What changed, in plain words, newest first. Each entry is a milestone or a step of one; the plan and
the measured results of each live in [docs/plans/](docs/plans/), the reasons in [docs/adr/](docs/adr/).
Add a new entry at the top whenever a milestone or a notable change lands, and keep the numbers
(cost, latency, test counts) that the work measured.

Dates are 2026. The project isn't versioned yet: the first tagged release (`v0.1.0`) will turn the
section below into its release notes and publish the images with that tag.

## Unreleased

### UI redesign: "C · Paper" (18–19 Oct)
- **New look:** white and text-first (GitHub-like greys, green primary buttons), sharp 4 px corners,
  Public Sans and JetBrains Mono, lighter hairlines and more white space. Light, dark and
  "follow the system", switchable in the sidebar, with no flash on load.
- **Left sidebar** with My work, Calendar, projects, People, and the account. On phones it sits
  behind a Menu button.
- **Ticket page:** one activity timeline (description, status and assignee changes, comments), with
  the two agents as tinted "bot" entries and the comment box at the end. New
  `GET /tickets/{id}/events`.
- **Phones:** ticket list as cards, calendar as an agenda, board cards dragged by a handle (so a
  finger can still scroll).
- **Browser tests (Playwright), 11 in CI:** sign-up through email confirmation, ticket editing,
  board drag, dashboard, calendar, employee permissions, and an accessibility scan (axe) of eight
  pages in light and dark. The scan found and we fixed four real problems.
- **Fixed:** a screenshot that is not really an image made Claude reject the whole triage request.
  Triage now retries without the images (one billed call, $0.00012 measured).
- **Fixed:** the worker had no health check, which broke `docker compose up --wait` in CI. It now
  proves it is alive with a heartbeat file.
- **Demo data:** `uv run python -m scripts.seed_demo` creates a manager, three teammates with
  profiles and twelve tickets with history.
- **Claude Code can see the app:** a Playwright MCP is configured in `.mcp.json`.

### Milestone 7a: CI/CD without a cloud (17–18 Oct)
- **Public repository** under the MIT license, with the author email replaced by GitHub's noreply
  address in every commit and a secret scan over the whole history (clean).
- **CI on every push and pull request, $0:** lint, strict types, migration drift, about 200 tests
  against a real Postgres + pgvector, frontend build, an API-contract check, a gitleaks scan.
  Actions are pinned to commit hashes.
- **Images** are built once per commit and published to GHCR with an SBOM, signed build provenance
  and a Trivy scan (the first run caught three fixable CVEs in a base image). `compose.release.yml`
  runs exactly those images.
- **Security and guard rails:** CodeQL, Dependabot (waits 14 days after each release), secret
  scanning with push protection, a rule on `main` against force pushes, pre-commit hooks, and a
  Claude Code hook that blocks irreversible commands.
- **Smoke suites** (80 checks across milestones 2–6) moved into the repo (`/smoke` skill, manual
  E2E workflow). ADR 0020.

### Milestone 6: dashboards, AI metrics, my work, calendar (17 Oct)
- A **ticket history** table (status and assignee changes, with who and when) and a project
  **dashboard**: created and done per week, cycle and lead time (median and p90), open work by
  status and age, overdue, workload. p95 of 22 ms through the web proxy.
- **AI agents panel** for managers: per triage field, how often the suggestion was kept, edited or
  dropped; assignment hit rate (first pick and top 3); cost and latency per agent.
- **My work** and a month **calendar** of due dates. ADR 0019. No new LLM calls: $0.

### Milestone 5: the assignment agent (17 Oct)
- "Suggest assignee": code ranks the project's members by skills, similar finished work and current
  workload; Haiku then writes one reason each from facts only (never names). The manager picks, and
  every pick is recorded for a hit rate. **$0.00012 per click**, reasons in about 4 s.
- Job priority: a person waiting beats background jobs (a click had waited 14 s behind triage). ADRs
  0017, 0018.

### Milestone 4: the triage agent (17 Oct)
- A new ticket is classified (category, labels, priority, story points, duplicate), using similar
  tickets and screenshots. Category and labels apply themselves only when confident and the field is
  empty; everything else waits for a manager to accept, edit or dismiss. It asks one question if the
  ticket is too vague. **$0.0001 and about 2 s per ticket.** ADR 0016.
- Found on the way: the job queue mixed two clocks, which made a test flaky; fixed at the root.

### Milestone 3: team (17 Oct)
- Project invitations by email, employee profiles, a Postgres job queue with a worker, and the **CV
  agent** (Haiku reads a PDF CV; a manager reviews the draft). About $0.0007 per CV. ADR 0010.

### Milestone 2: tickets (17 Oct)
- Statuses, sub-tasks, links, comments and attachments (S3-compatible storage), with a Jira-like
  list, board and ticket page. ADR 0015.

### Milestone 1: accounts and structure (16–17 Oct)
- Email/password and Google sign-in, forgot/reset password, workspaces, projects and per-project
  roles (manager or employee). The Next.js app and its generated API client. ADRs 0011, 0012.

### Foundations (16 Oct)
- FastAPI backend with structured JSON logs, Postgres + pgvector with migrations, the `core/llm`
  gateway (model routing, cost and budget on every call), local embeddings and similar-ticket
  search, Docker Compose for the whole stack.
