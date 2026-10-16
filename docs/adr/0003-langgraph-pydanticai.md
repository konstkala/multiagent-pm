# 0003. LangGraph + PydanticAI for agents

Status: accepted, 2026-10-16

## Context
Agents need durable state, resumable runs and human approval steps, plus typed inputs and outputs.

## Decision
LangGraph for orchestration (graph state, Postgres checkpoints, interrupts). PydanticAI for typed agents inside graph nodes.

## Consequences
- Human-in-the-loop and resume-after-crash come from the framework.
- Two libraries to learn. PydanticAI must use native structured output: Sonnet 5.5 rejects forced `tool_choice`.
