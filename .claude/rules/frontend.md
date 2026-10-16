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
- Next.js 16 differs from older versions (proxy.ts replaces middleware, Cache Components). Read the matching guide in `frontend/node_modules/next/dist/docs/` before using a Next API.
- Client components that read the URL (`useSearchParams`, `useParams`) render inside `<Suspense>`, or the build fails.
- API calls go through `call()` / `send()` in `src/lib/api/client.ts` and TanStack Query; query keys live in `src/lib/queries.ts`.
- Backend API changed: run `npm run gen:api` and commit the regenerated files.
