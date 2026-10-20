# UI redesign: the "Harbour" shell, a navy hero, and a public landing page

## Context
The app feels plain: edge-to-edge white, hairline borders, sharp 4 px corners ("C · Paper", chosen 2026-10-18). The user pointed at media-harbour.com (Awwwards nominee) and chose:
- **Direction B:** floating rounded nav, tinted canvas with inset rounded sheets, pill buttons, one cinematic hero. Boards and tables stay dense.
- **Accent:** navy hero surfaces, **green actions** (keeps the existing `--accent`).
- **Wow moment first:** sign-in, sign-up and a new public landing page. The app interior gets the lighter polish.

What I saw on the reference (screenshots in `.playwright-mcp/ref-harbour-*.png`): a floating white pill nav on a grey-blue canvas, a deep-navy rounded hero sheet with animated flowing lines, an eyebrow pill, a two-tone headline, pill buttons (one solid CTA), solid-coloured rounded service tiles, and scroll-reveal sections.

This supersedes the look in `docs/plans/2026-10-18-ui-redesign.md` (colours and corner radius). The structure (sidebar, ticket timeline with bot entries, light and dark) stays.

**Cost:** frontend only. $0 LLM, no backend change, **no new dependencies** (no animation library).

## Design
### Tokens (`frontend/src/app/globals.css`, the only place colours and radii live)
| Token | Light | Dark | Use |
|---|---|---|---|
| `--background` (canvas) | `#e8ecf3` | `#070b14` | page behind the sheets |
| `--surface` | `#ffffff` | `#0f1522` | sheets, cards, inputs |
| `--subtle` / `--border` / `--control` | `#f4f6fa` / `#e3e8ef` / `#c9d1dc` | `#131b2b` / `#1f2a3d` / `#35435c` | as today, retuned to the canvas |
| `--navy-900`, `--navy-700` (new) | `#07143a`, `#0b2a6b` | same | hero gradients |
| `--hero-accent` (new) | `#7ee2a8` | same | gradient word in hero headlines |
| `--accent` / `--accent-strong` | unchanged (green) | unchanged | actions |
| `--radius-sm/md/lg/xl` | 8 / 12 / 16 / 24 px | same | inputs and badges / controls / cards / sheets and hero. Buttons use `rounded-full`. |
| `--shadow-card`, `--shadow-float` (new) | soft two-layer shadows | none (borders carry it) | cards, floating nav |

Font stays Public Sans (variable weights, already loaded): heavier weight, tighter tracking and a bigger scale for display headings. No new font download.

### App shell (`components/app-shell.tsx`)
- Canvas wrapper with padding; the **sidebar becomes a floating rounded card** (`rounded-xl`, shadow, sticky); **`<main>` becomes the white sheet** (`rounded-xl`, shadow). All existing page content sits unchanged inside the sheet, which is why the visual shift is large and the per-page diff small.
- Active nav item: soft green pill with a dot instead of the inset bar. Theme toggle: pill segmented control. Mobile top bar: a floating pill with the Menu button.
- New `components/logo.tsx`: inline-SVG mark + wordmark, used by shell, auth and landing.

### Primitives (`components/ui.tsx`)
`Button`: `rounded-full`, slightly taller, hover lift (transform only). `TextField`/`Select`: `rounded-md`. `Card`: `rounded-lg` + `--shadow-card`; the "bot" tone keeps its tinted header. `Badge`: pill. Public API unchanged, so no call sites change.

### Auth (`app/(auth)/layout.tsx`)
Split screen on `lg+`: left, an inset navy hero card (brand, two-tone headline, one supporting line, animated lines); right, the form on white, no box. Below `lg` the hero collapses to a compact banner above the form. Form components, labels and button names are untouched (the e2e tests depend on them).

### Landing page (`app/page.tsx`, replaces the redirect)
1. Floating pill nav: logo, anchor links, "Sign in" (ghost), "Get started" (green pill).
2. Navy hero sheet: eyebrow pill, **"Agents prepare. *People decide.*"** (gradient on the second sentence), a two-line description taken from CLAUDE.md, two CTAs, and a **real screenshot of the app** in a rounded frame (the ticket page with the splitter review). Captured with the Playwright MCP from seeded data, saved as WebP (about 150 KB or less) under `frontend/public/landing/`, shown with `next/image` and `fetchPriority="high"` (Next 16 deprecates `priority`, per the bundled docs).
3. Four solid rounded tiles: triage, assignee suggestions, CV to profile, ticket splitting. One line each.
4. "Built to be trusted": three facts that exist in code: every consequential change needs a person's approval; a $0.05 cap per agent run; every action audited. No invented statistics.
5. Closing navy band with the CTA, and a minimal footer.
- `proxy.ts`: add `/` to the matcher. With a session cookie, redirect to `/projects`; without, show the page. This is the same optimistic check as today, and it keeps the landing page static.

### Motion (CSS only, no JS)
- Hero lines: an inline SVG of about 6 paths, animated with `transform`/`stroke-dashoffset` only (compositor-friendly).
- Scroll reveal: `animation-timeline: view()` inside `@supports`, so browsers without it just show the content. Nothing is hidden by default, so axe and no-JS users are fine.
- Everything sits under `@media (prefers-reduced-motion: reduce)` → static.

## Steps (each ends with screenshots; commit-sized, matching the earlier "UI redesign, step a–f" history)
1. **Tokens, primitives, shell** (`globals.css`, `ui.tsx`, `app-shell.tsx`, new `logo.tsx`). Then sweep every signed-in page for places that assumed sharp corners or a white background (board cards, tables, calendar, ticket page).
2. **Auth split hero** (`(auth)/layout.tsx`, new `components/hero-lines.tsx`).
3. **Landing page + proxy + screenshots** (`app/page.tsx`, `proxy.ts`, `public/landing/`).
4. **Light page polish:** project header, project cards and empty states (`project-header.tsx`, `projects-view.tsx`).
5. **Safety net and docs:** extend `e2e/accessibility.spec.ts` with a signed-out run over `/`, `/sign-in`, `/sign-up`, `/forgot-password` in light and dark (today it covers only signed-in pages). Add ADR 0022 (UI direction: Harbour shell supersedes Paper), save this plan to `docs/plans/2026-10-19-ui-harbour.md`, add glossary entries (design tokens, scroll-driven animations, `prefers-reduced-motion`, WCAG contrast), update the CLAUDE.md line that names the "C · Paper" mockup as the reference, and update the UI-direction memory.

## Risks and how they're handled
- **Contrast:** white and mint text over a navy gradient, and green buttons on white. The hero uses CSS gradients, not images, so axe can measure them. The step-5 scan checks both themes.
- **Global radius change** also softens dense UI (board cards, table rows). That's intended, but step 1 reviews each page.
- **Existing e2e tests** use exact labels and button names; none change. `/` was only a redirect, so the proxy change is the one behavioural edit.
- **Performance:** one optimised hero image, no new JS, animation on transform only. `npm run build` stays green.

## Verification
1. From `frontend/`: `npm run check` (lint, types, build).
2. Stack up (`docker compose up -d --build --wait`), then `npm run e2e` including the new signed-out accessibility run.
3. Playwright MCP screenshots at **1440 px and 390 px, light and dark**, of: landing, sign-in, sign-up, projects, project tickets, board, ticket with the splitter panel, dashboard, team, calendar. Compare with the reference screenshots and check nothing overflows horizontally.
4. Emulate `prefers-reduced-motion: reduce` and confirm the hero is static; resize to 390 px and confirm the hero collapses cleanly.
5. Signed in, visiting `/` goes straight to `/projects`; signed out, `/` shows the landing page and `/projects` still bounces to `/sign-in`.
