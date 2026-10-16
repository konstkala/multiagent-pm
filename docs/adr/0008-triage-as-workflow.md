# 0008. Ticket triage is a fixed workflow, not an agent

Status: accepted, 2026-10-16

## Context
Triage always follows the same steps: look up similar tickets, classify, apply, wait for approval. The model never needs to choose what to do next.

## Decision
Build triage as a LangGraph graph with one LLM call and no tools. The model returns a typed proposal; code validates it and applies it.

## Consequences
- About 1/30th of the cost of a tool-using Sonnet agent, and 2-4 s instead of 8-20 s.
- A prompt injection in ticket text can at worst produce a bad proposal; it cannot call tools. A person approves consequential fields.
- Real tool-using agents come later, where open-ended exploration pays off.
