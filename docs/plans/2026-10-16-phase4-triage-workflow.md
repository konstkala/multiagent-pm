# Phase 4: triage workflow

Parent plan: [ticket triage v1](2026-10-16-ticket-triage-v1.md). Brainstorm: [brainstorm](2026-10-16-ticket-triage-brainstorm.md).

## Decisions (2026-10-16)
- Structured output through `core/llm` (SDK `messages.parse`). PydanticAI deferred: ADR 0009.
- Postgres job queue (`SKIP LOCKED`) + a separate worker container: ADR 0010.
- A fixed LangGraph workflow, not an agent: ADR 0008.
- No assignee in v1 (no users table). Approval covers `priority` and `duplicate_of`.
- Triage runs automatically when a ticket is created.

## Behaviour
1. `POST /tickets` saves the ticket, then enqueues a `triage` job.
2. Worker claims the job and starts a `triage_run`:
   `load ticket → find similar → classify (Haiku) → validate → apply safe fields → wait for approval → apply decision`
3. **Classify** returns `TriageProposal`: type, priority, component, labels (max 5), duplicate_of, confidence (0–1), reason (max 300 chars). One call, effort `low`, `max_tokens` ~600.
4. **Validate in code, not by the model:** `duplicate_of` must be one of the candidates we sent; labels are trimmed and lowercased.
5. **Auto-apply:** type, component, labels, only when confidence ≥ 0.6. Below that, nothing applies automatically.
6. **Approval:** priority and duplicate_of (and everything, when confidence < 0.6) wait in status `awaiting_approval`. `POST /triage-runs/{id}/decision` with approve / reject / edit resumes the graph.
7. Every step logs `triage.*` events with `run_id`; state changes log `audit.*`; LLM calls log `llm.call`.

## Safety
- Ticket text goes only in the user message, inside delimiters. The model has no tools: it cannot do anything except return a proposal.
- Run budget $0.05; a refusal or budget error marks the run `failed` and keeps the ticket untouched.
- A failed or rejected triage never blocks the ticket.

## Cost
~5K tokens in / ~600 out on Haiku 5.5: about $0.001–0.002 per ticket. Tests use fakes ($0). One real end-to-end run at the end: ~$0.002.

## Steps (commit after each)
- 4a. Gateway: `complete_structured()` with `messages.parse`; tests.
- 4b. Schema: `triage_runs` and `jobs` tables (migration 0004); models.
- 4c. Job queue: enqueue, claim (`SKIP LOCKED`), complete, fail with retry, stale-lock recovery; concurrency test.
- 4d. Triage graph: nodes, prompt file, LangGraph with checkpointer and interrupt; tests with a fake LLM and in-memory checkpointer.
- 4e. Worker process + compose service; enqueue on create; decision endpoint.
- 4f. Real end-to-end run with Haiku; measure cost and latency; docs.

## Risks
- LangGraph's Postgres checkpointer needs `psycopg`; its async mode needs a selector event loop on Windows. The worker runs in Docker (Linux); local tests use a selector-loop policy on Windows.
- LangGraph creates its own checkpoint tables (`saver.setup()` at worker start), outside Alembic. Documented exception to the migrations rule.
- Haiku's system prompt (~500 tokens) is below the cache minimum, so no cache hit is expected. Measure, don't assume.
