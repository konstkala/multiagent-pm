# Ticket triage: brainstorm outcome

Input for plan mode. Not a plan yet.

## Decision
Approach B: a fixed LangGraph workflow, one Haiku 5.5 call per ticket. Not an open-ended agent: the steps are known.

Flow: new ticket → embed → top-k similar tickets (pgvector) → Haiku: type, priority, component, labels, duplicate-of, suggested assignee, `confidence`, `reason` → apply labels/type → approval interrupt for assignee + priority → apply.

## Choices
- Source: our own `tickets` table. No external sync in v1.
- Autonomy: labels and type apply automatically; assignee and priority need human approval.
- Embeddings: local model (e.g. fastembed), $0 per call.
- Escalation (later): low confidence → Sonnet 5.5.

## Cost & latency estimate
- ~5K tokens in / ~600 out on Haiku 5.5 ($0.10 / $0.50 per MTok): ~$0.001–0.002 per run, ~$1–2 per 1,000 tickets.
- 2–4s. Runs in the background on ticket creation.
- Rejected: Sonnet agent with tools, ~$0.03–0.06 per run (at the $0.05 cap), 8–20s.

## For planning
- Sonnet 5.5 rejects forced `tool_choice` (`any` / `tool`). Check that PydanticAI uses native structured output, not a forced tool call.
- Set Haiku effort explicitly (default `medium`; try `low` for classification).
- Haiku has no server-side refusal fallback: handle `stop_reason: "refusal"`.
- Build an eval of ~30 hand-labelled tickets before tuning the prompt.
- ADR candidates: local embeddings; workflow-not-agent for triage.
