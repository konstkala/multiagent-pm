# Milestone 5: the assignment agent

## Context
Managers need help choosing who takes a ticket. ADR 0013 already decided the shape: the agent recommends the **top 3 with reasons, the manager picks**; scoring is code, the LLM only writes the explanation. Brainstorm answers (2026-10-17): candidates = **project members** (managers too), runs **on click**, reasons by **one Haiku call**, workload = **open points vs team average** with an overdue penalty. Outcome: a "Suggest assignee" button on the ticket that shows 3 ranked people instantly, reasons ~2 s later, one click to assign, and every manager choice recorded so we can measure the agent's hit rate (future eval + M6 KPI).

Saved to `docs/plans/2026-10-17-milestone-5-assignment.md` once approved; new ADR `docs/adr/0017-assignment-scoring.md` (lazy profile embeddings, anonymised candidates to the LLM, choice recorded via the assignee change).

## Design

### Scoring (pure code, $0, `backend/app/agents/assignment/scoring.py`)
All components in 0..1, pure functions over plain dataclasses (unit-testable without DB):
- **Skill fit (45%)** = 0.7 × semantic + 0.3 × label match.
  - semantic: cosine(ticket embedding, profile embedding), rescaled `clamp((sim − 0.5) / 0.4)` because bge similarities sit in 0.5–0.9.
  - label match: highest level / 5 among the person's skills whose name equals a ticket label (case-insensitive).
  - No profile → 0, fact "no profile yet".
- **Similar work done (35%)**: the person's `done` tickets in the project with similarity ≥ 0.7 to this ticket, capped at 3 → `n / 3`. Cap keeps the "rich get richer" effect bounded.
- **Availability (20%)** = `1 / (1 + open / max(team_avg, 1))` − 0.15 per overdue ticket, floor 0. Open = todo/in_progress/in_review; an unpointed open ticket counts as 3 points.
- **Cold start**: if the project has no done tickets with embeddings, the history weight is spread over the other two. A ticket without an embedding uses label match only.
- Ties: fewer open points, then display name. Return top 3 with score, components and **facts** (matched skills with levels, similar done count, open points, team avg, overdue count).

### Profile embeddings (lazy, local)
- Migration `0012`: `employee_profiles.embedding vector(384)`, `embedding_model`.
- `profiles.save_profile` sets `embedding = NULL` in its upsert values (profile changed → vector stale). Nothing else in the CV/people paths changes.
- The assignment service embeds profiles that have no fresh vector (`embedding IS NULL` or another model) with `get_embedder()`, text = headline + summary + skill names, and saves them. Reuses the best-effort pattern of `tickets._set_embedding` (`backend/app/services/tickets.py:323`).

### Data model (migration `0012`)
`assignment_runs`: id, ticket_id, requested_by, status (`explaining` → `ready` | `explain_failed`), candidates JSONB (user_id, rank, score, components, facts, reason|null), chosen_user_id, chosen_rank (1–3, or null = picked someone outside the top 3), decided_at, model, llm_calls, cost_usd, latency_ms, error_code, created_at (clock_timestamp), finished_at. Mirrors `TriageRun` (`backend/app/db/models/triage.py`).

### The LLM step (`backend/app/agents/assignment/agent.py` + `prompt.md`)
- Input: ticket key, title, category, labels (in a tag the text can't close) + candidates as **A/B/C with facts only**: no names, emails or CV summaries go to the model (privacy, and no name-based bias).
- Output `AssignmentReasons`: `[{candidate: "A"|"B"|"C", reason ≤ 25 words}]`. `clean()`: map by letter, drop unknown letters, trim; a missing reason falls back to a sentence built from the facts.
- Haiku 5.5, `Tier.WORKER`, effort `low`, max_tokens 600, `RunBudget` $0.05, via `complete_structured` (`backend/app/core/llm/client.py`).
- Move triage's `_tag` helper to `core/llm/content.py` as public `tag()` and use it in both agents.
- **Cost: ~600 tokens in / 120 out → ~$0.0001 per click** (triage measured $0.0001 for a larger prompt). Embeddings $0. The system prompt is under Haiku's cache minimum, so no prompt caching (noted in the plan).

### Flow and API (`backend/app/api/assignment.py`, `backend/app/services/assignment.py`)
- `POST /tickets/{id}/assignment-suggestions` (project managers): gathers data, scores (~50 ms), stores the run with candidates, enqueues job `assignment_reasons`, **returns 202 with the ranked candidates immediately** (reasons null).
- `GET /tickets/{id}/assignment-suggestions` (managers): latest run or null. Employees 403 (it reveals others' workload and profiles); outsiders 404.
- Worker handler `assignment_reasons` (`backend/app/worker.py`): fills reasons → `ready`. LLM refusal, budget or errors after 3 attempts → `explain_failed`, candidates and facts stay usable (graceful degradation).
- **Picking = the existing `PATCH /tickets/{id}` with `assignee_id`.** In `tickets.update_ticket`, when the assignee changes, `assignment.record_choice()` marks the latest undecided run: chosen user + rank (null if outside the top 3). Same path for the panel's Assign button and the sidebar select, so the hit rate is honest.
- Logs: `audit.assignment.requested`, `assignment.scored` (run id, candidate count, ms), `llm.call` (automatic), `assignment.explained`, `audit.assignment.chosen` (rank). Ids and numbers only; no names, skills or ticket text.

### UI (`frontend/.../tickets/[ticketId]/assignment-panel.tsx`)
Managers only, right column under the sidebar card: "Suggest assignee" → 3 rows: name, score %, fact chips (e.g. `payments 4/5 · 2 similar done · 5 open pts (avg 8)`), the reason or "Writing reasons…", an **Assign** button (uses `useUpdateTicket`), cost line, "Refresh". Polls every 2 s while `explaining` (same as `useTriage` in `frontend/src/lib/queries.ts`). Plain styling until the UI session. `npm run gen:api` after the API change.

## Steps (commit after each)
- **5a** Migration 0012, scoring + unit tests, profile embeddings, agent + prompt, service, API, worker job, choice recording, API tests (FakeEmbedder + FakeClaude), one live run.
- **5b** Assignment panel, regenerate client, Docker rebuild, end-to-end smoke (`smoke_m5.py`), docs (plan result, README, roadmap, glossary, ADR 0017).

## Tests
- Unit (`tests/test_assignment_scoring.py`): label match by level, semantic rescale, availability curve + overdue penalty, cold-start reweighting, tie order, top 3 cut.
- API (`tests/api/test_assignment.py`, db): ranking follows skills (FakeEmbedder word overlap) and history; heavier workload drops a person; no profiles → availability only; employee 403, outsider 404; 202 returns candidates before reasons; the job fills reasons; LLM failure → `explain_failed` with facts kept; prompt has letters, no names or emails, and the title can't close its tag; PATCH assignee records rank (1–3 or null); profile save clears the embedding; logs carry no names, skills or ticket text.
- Live (`@pytest.mark.llm`): one real call, reasons for 3 letters, cost < $0.01.

## Verification
1. `uv run ruff check --fix . && uv run ruff format . && uv run pyright && uv run pytest` (backend), `npm run check` (frontend).
2. `uv run pytest -m llm tests/test_assignment_agent.py` → real cost and reason quality.
3. `docker compose up -d --build`, then `smoke_m5.py` through the web proxy: manager + 3 employees with profiles (payments expert, frontend dev, overloaded payments dev), past done tickets → suggestion for a payments bug ranks the expert first and the overloaded dev lower; reasons arrive; assigning records rank 1; employee gets 403; logs contain no names or skills.
4. Report $/click and latency (score ms + reasons s).
