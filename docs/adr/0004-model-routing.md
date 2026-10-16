# 0004. Model routing: Haiku workers, Sonnet orchestrator

Status: accepted, 2026-10-16

## Context
Most calls are classify / summarize / extract. Few need planning or long tool loops. Haiku 5.5 is $0.10 / $0.50 per MTok; Sonnet 5.5 is $2 / $10.

## Decision
`claude-haiku-5-5` for worker calls, `claude-sonnet-5-5` for orchestration, planning and agentic tool loops. Routing lives in `core/llm`. Effort is set per agent.

## Consequences
- Worker calls cost ~20× less than they would on Sonnet.
- Some tasks may need escalation to Sonnet on low confidence; measure before adding.
