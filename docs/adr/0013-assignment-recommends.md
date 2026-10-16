# 0013. The assignment agent recommends; the manager decides

Status: accepted, 2026-10-16

## Context
Choosing who does a ticket affects people's workload and fairness. A model can be wrong or biased, and nobody should be assigned by a model without a person looking.

## Decision
On request, the agent returns the top 3 candidates with reasons. Scoring is code (skill match by embeddings, open story points, overdue tickets, similar past tickets); the LLM only writes the explanation. The manager picks.

## Consequences
- Cheap (~$0.001 per click), testable and explainable.
- Slower than auto-assign by one click. Auto-assign can be added later behind a setting if data shows the recommendations are reliable.
