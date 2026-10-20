# UI redesign: "C · Paper" across the app (with a browser-test safety net first)

> **Superseded in part, 2026-10-20 (ADR 0022):** the colours, sharp corners and edge-to-edge white are replaced by the "Harbour" look (tinted canvas, rounded sheets, pill buttons, navy hero). The structure below (sidebar, ticket timeline with bot entries, light and dark, phone layouts, browser tests) still holds.

## Context
Every screen is still the plain "functional for now" version. On 2026-10-18 the user chose direction **C · Paper** from three mockups: GitHub-like, white, text-first, agents shown as "bot" entries in the ticket timeline, **sharp 3–4 px corners**, green accent, light **and** dark mode, a left sidebar, usable on phones. The source of truth is https://claude.ai/artifact/3jyxBC1WQxHqey8ER8CYg8 (artboards "C · Paper, light" and "C · Paper, dark"; token sets in `Paper.dc.html`'s `renderVals`).

Today nothing proves a button works: smoke tests hit the API and check that pages return 200. A redesign touches all 45 files that import `@/components/ui`, so **browser tests come first**. The user also picked the **Playwright MCP**, so Claude can look at the real app instead of building blind. No LLM calls are added: **$0**.

Plan copied to `docs/plans/2026-10-18-ui-redesign.md` once approved; ADR `docs/adr/0021-ui-shadcn-and-design-tokens.md`.

## Steps (commit after each; CI green each time)

### UIa. Playwright browser tests + CI job
- `@playwright/test` (exact version, ≥ 2 weeks old) as a frontend dev dependency; `frontend/e2e/`; `playwright.config.ts` (Chromium only; `baseURL` http://localhost:3000; traces and screenshots on failure).
- Global setup signs up a manager and an employee through the real UI. The confirmation link comes from Mailpit's API; the sessions are saved as `storageState`. This stays under the 10-sign-ups-per-hour limit (unique emails per run).
- About 8 flows, using roles and labels, not CSS:
  - sign in and out
  - create a project and a ticket
  - edit a ticket (title, status, assignee)
  - comment
  - board drag to In progress
  - upload an attachment
  - dashboard shows the counts
  - calendar shows a due ticket
  - an employee can't see the manager-only panels
- AI flows: compose gets `TRIAGE_ENABLED: ${TRIAGE_ENABLED:-true}`, and the CI job sets it `false` (no API key in CI: $0). One test asserts the triage panel's "switched off / not triaged" state. The AI flows themselves stay covered by the smoke suites.
- `e2e-browser` job in `.github/workflows/ci.yml`: `docker compose up -d --build --wait`, cached Chromium, `npx playwright test`; the trace is uploaded on failure.

### UIb. Playwright MCP for Claude
- `.mcp.json` (project scope, committed): `@playwright/mcp` at an exact version. It takes effect after a session restart; the user restarts once.
- From then on, each UI step ends with screenshots at desktop and phone widths in light and dark, compared with the mockup. CLAUDE.md gets a line on this.

### UIc. Foundations: tokens, fonts, theme, shadcn/ui, app shell
- **Tokens:** `globals.css` gets light and dark sets taken from the C mockup, using the shadcn names:
  - `background`, `foreground`, `card`, `muted`, `muted-foreground`, `border`, `input`, `ring`
  - `primary` = green `#1a7f37` / `#238636`, `destructive`, `link`, plus `--radius: 4px`
- **Classes:** one codemod pass renames our classes to those tokens (`text-muted` → `text-muted-foreground`, `accent` → `primary`/`link`). Hard-coded Tailwind colours (status pills in `lib/tickets.ts`, `Alert` tones) become token-based, so dark mode works everywhere.
- **Fonts:** Public Sans + JetBrains Mono via `next/font/google`, replacing Geist in `src/app/layout.tsx`.
- **Dark mode:** `next-themes` with class strategy, default "system", and a toggle in the sidebar; no flash on load.
- **shadcn/ui:** `npx shadcn@<version> init` writes `components.json` and `lib/utils.ts` (`cn`).
  - Add only what we use: button, input, textarea, select, dialog, dropdown-menu, tabs, badge, card, tooltip, sheet (phone sidebar).
  - `src/components/ui.tsx` becomes `src/components/ui/index.ts`, re-exporting our existing API (`Button`, `Card`, `Alert`, `Badge`, `Loading`, `TextField`, `Select`) on top of the shadcn pieces. The 45 importers keep working unchanged.
- **App shell:** a left sidebar (My work, Calendar, People; Projects list; user and theme at the bottom). On phones it becomes a Sheet behind a menu button. Project header tabs: Tickets, Board, Dashboard, Team.

### UId. Ticket screen with the activity timeline
- **Backend:** `GET /tickets/{id}/events` returns the ticket's `ticket_events` with actor display names (members only). It's paginated by `limit` (default 100), with a test.
- **Frontend timeline:** merges by time:
  - the description
  - comments
  - events ("Ana moved this to In progress")
  - the triage run, as a **bot entry** with the proposal table and Accept, Edit or Dismiss for managers, plus the cost line
  - assignment suggestions as a bot entry (managers)
- **Right column:** the properties list, matching the mockup.
- **Kept as is:** existing behaviour and permissions (triage panel logic, `useUpdateTicket`, polling).

### UIe. Tickets list, board, projects, team and people
Same tokens and components, restyled only; the information on each screen stays the same. Phone layouts: the list becomes cards, and the board columns scroll sideways.

### UIf. Dashboards, my work, calendar, auth and invite pages
- Recharts colours come from CSS variables, so charts follow the theme.
- The calendar grid uses the tokens and has a phone layout (an agenda list).
- Auth pages get a centred card in the new style.

## Tests and checks per step
- Unchanged and green: `uv run ruff check . && uv run pyright && uv run pytest`, `npm run check`, `python -m scripts.smoke` (80 checks).
- `npx playwright test` locally and in CI.
- From UIb on: MCP screenshots (desktop 1440 and phone 390, light and dark), compared with the artboards and shown to the user at the end of UIc, UId and UIf.
- An accessibility pass with `@axe-core/playwright` on the main pages (no serious violations), plus a contrast check on both themes' tokens.

## Docs
ADR 0021 (shadcn/ui on Radix, design tokens, next-themes); README screenshots (light and dark) replace the text description of the UI; glossary entries (Playwright, storageState, MCP, design tokens, shadcn/ui, Radix, next-themes, axe); a roadmap tick for end-to-end browser tests; the M1 gap "no end-to-end browser tests" closed in the product plan.
