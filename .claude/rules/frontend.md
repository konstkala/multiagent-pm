---
paths:
  - "frontend/**"
---
# Frontend

- Talk to the backend only through the generated API client. No hand-written fetch calls or duplicated API types.
- Never edit generated client files; regenerate them.
- Server Components by default. Add `"use client"` only where interactivity needs it.
- Agent runs stream: always show progress, never block the UI waiting for a run.
- Every approval prompt shows what the agent wants to do and with which inputs, plus approve / reject.
- Render ticket, user, and LLM text as text. No `dangerouslySetInnerHTML`.
- Show cost and latency per run where the API provides them.
- Strict TypeScript. No `any`.
