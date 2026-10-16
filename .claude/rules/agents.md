---
paths:
  - "backend/app/agents/**"
---
# Agents

- Set model and effort explicitly on every agent. Haiku for workers; Sonnet only for orchestration, planning, tool loops.
- No direct SDK imports here. Every LLM call goes through `core/llm`.
- Prompts live in `agents/<name>/prompt.md`, not inline strings. Stable text first, variable text last, so the prompt cache hits.
- Tools take and return Pydantic models. The docstring is what the model reads: say when to use the tool and when not to.
- Tool failures return a typed error result the model can act on. Never pass stack traces to the model.
- Untrusted text (tickets, comments, user input) goes in a delimited data block in the user turn, never in the system prompt.
- Side-effecting tools (write, assign, notify) pause for human approval via a LangGraph interrupt.
- Nodes are small and idempotent: resuming from a checkpoint may re-run a node.
- Tool loops have a max iteration count and check the run budget ($0.05) before each LLM call.
- New agent, new LLM call, or prompt change: state the estimated tokens and $/run in the plan.
