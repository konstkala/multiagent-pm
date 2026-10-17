# 0017. Assignment scoring: lazy profile embeddings, anonymous facts to the LLM, every pick recorded

Status: accepted, 2026-10-17. Details ADR 0013.

## Context
ADR 0013 decided that code ranks candidates, the LLM only explains, and the manager picks. Building it raised three questions: how to compare a ticket with a person, what the model may see about people, and how to know whether the suggestions help.

## Decision
- **Score** (weights 45 / 35 / 20): skill fit (ticket vs profile embedding, plus ticket labels that match a named skill, by level), similar finished tickets in the project (capped at 3), and availability (open points across the workspace vs the team average, minus overdue). With no finished work in the project yet, history's weight moves to the other two.
- **Profile embeddings are lazy.** Saving a profile clears its vector; the next suggestion embeds it locally. The CV and profile paths stay unchanged, and an unused profile is never embedded.
- **The model sees letters and facts only:** no names, emails or profile text. It can't be biased by a name and can't leak one, and the reasons can only repeat what code computed.
- **Ranking is synchronous, reasons are a job.** The POST returns the top 3 at once (about 50 ms); one Haiku call fills the reasons about 2 s later. If that call fails, the ranking and facts still stand.
- **The pick is recorded on any assignment,** whether from the suggestion's button or the plain assignee select: the chosen user and their rank (1–3, or none). This gives an honest hit rate.

## Consequences
- About $0.0001 per click; embeddings cost nothing.
- Top-1 and top-3 hit rates come for free (milestone 6 dashboards, and an eval set to tune the weights).
- The weights are a first guess. Tune them against recorded picks before adding LLM reranking (option C in the brainstorm).
- History favours people who already did similar work. The cap and the availability weight limit this; watch it in the hit-rate data.
