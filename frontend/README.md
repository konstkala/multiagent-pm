# Frontend

Next.js 16 (React 19, TypeScript, Tailwind CSS 4, TanStack Query).

```sh
npm install
npm run dev        # http://localhost:3000, proxies /api to http://localhost:8000
npm run check      # lint + typecheck + production build
npm run gen:api    # regenerate the typed API client after backend changes
```

- The browser only talks to this origin. `next.config.ts` proxies `/api/*` to FastAPI, so the session cookie stays first-party and no CORS is needed. `API_URL` sets the backend address at build time.
- `src/lib/api/schema.d.ts` and `openapi.json` are generated from the backend. Don't edit them.
- Pages are static shells; signed-in data loads in the browser with TanStack Query. The API is the only authority on who may see what. `src/proxy.ts` only skips pages that would bounce a signed-out visitor.
