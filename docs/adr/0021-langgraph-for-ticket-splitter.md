# 0021. LangGraph for the ticket splitter

Status: accepted, 2026-10-19. Amends ADR 0016 and ADR 0009.

## Context
ADR 0016 kept LangGraph out until an agent needed branching or loops. The ticket splitter does: Haiku drafts sub-tickets, Sonnet critiques the draft, and the draft is revised until the critic is satisfied or two rounds have passed. Then a manager must approve before anything is created. That is a cycle, a conditional edge and a human pause, and the run should survive a worker restart.

## Decision
- The splitter is a LangGraph `StateGraph` (`agents/splitter/graph.py`): `draft → critique → (revise → critique)* → approve`. `approve` calls `interrupt()`; the manager's answer comes back through `Command(resume=...)`.
- Every LLM call in a node still goes through `core/llm` (cost, budget, refusals, logs). PydanticAI stays out (ADR 0009): it makes its own Claude calls and would bypass the gateway.
- **Two kinds of state.** The `split_runs` row is what the API and screens read (status, step, proposal, cost). LangGraph's checkpoint tables, keyed by the run id as `thread_id`, are what let the graph resume. The service keeps them in step; nothing else reads the checkpoint.
- The graph does only LLM work and the pause. All database writes (creating sub-tickets) happen in the service after the graph returns, in one transaction guarded by the run's status. A node that re-runs on resume can therefore never create a ticket twice.
- Checkpoint tables are created by `PostgresSaver.setup()` inside migration 0019 and are never edited by hand; Alembic autogenerate ignores them.
- Only the worker imports LangGraph and psycopg. The API only reads and writes `split_runs` and enqueues jobs.
- Triage, CV import and assignment stay plain jobs: they have no loop.

## Consequences
- A second driver: LangGraph's Postgres checkpointer needs psycopg 3 next to asyncpg. Same database, `postgresql://` instead of `postgresql+asyncpg://`.
- Windows: async psycopg cannot use the default Proactor event loop. The worker and the tests run on `SelectorEventLoop` there. Linux containers are unaffected.
- Heavier dependency tree: `langgraph` pulls in `langchain-core`, `langsmith` and others, and moved `websockets` from 17.2 to 16.1.1.
- pyright strict cannot see all of LangGraph's overloads; a few narrow, commented suppressions are the price.
- Cost, measured on the running stack (2026-10-19): $0.0027 for a split the critic accepted at once (2 calls, 8 s end to end) and $0.0073 for one that used both rounds (4 calls: draft, critique, revise, critique; 12.5 s). A critique costs about $0.0034, a draft or revision about $0.0003. Worst case stays far inside the $0.05 run cap. Each created sub-ticket adds about $0.0001 for its triage. Background job, so the 10 s interactive target doesn't apply.
- A crash mid-run resumes from the last checkpoint instead of starting over.
- Revisit if the checkpoint tables grow: nothing deletes finished threads yet. The production version is a periodic cleanup job keyed on `split_runs.finished_at`.
