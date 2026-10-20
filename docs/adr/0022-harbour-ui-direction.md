# 0022. UI direction: the "Harbour" shell replaces "C · Paper"

Status: accepted, 2026-10-20. Supersedes the look chosen on 2026-10-18 (`docs/plans/2026-10-18-ui-redesign.md`: sharp corners, GitHub-like, edge-to-edge white).

## Context
After the Paper redesign the app still felt plain next to polished product sites, and it is meant to be shown in interviews. The owner pointed at media-harbour.com (an Awwwards nominee) as the feel to aim for and chose: floating rounded navigation on a tinted canvas, pill buttons and one cinematic hero; navy hero surfaces with green actions; and the wow moment on the sign-in, sign-up and a new public landing page, with only light polish inside the app.

## Decision
- **Tokens only.** Colours, radii and shadows live in `globals.css`. A tinted canvas (`--background`) holds white sheets (`--surface`); radii are 8/12/16/24 px; buttons and badges are pills; the green `--accent` stays. The navy hero is two tokens plus a CSS gradient, the same in light and dark.
- **Shell.** The sidebar is a floating rounded card and `<main>` is a white rounded sheet, so every existing page keeps its content and only gains the frame. Agent ("bot") entries in the ticket timeline are unchanged.
- **Landing page at `/`**, static. `proxy.ts` sends a signed-in visitor on to `/projects`; everyone else sees the page. It shows a real screenshot of the app (WebP, about 95 KB) and claims only what the code does.
- **Motion is CSS only**: a drifting SVG hero, and scroll-reveal through `animation-timeline: view()` inside `@supports`. Nothing is hidden by default, and all of it is off under `prefers-reduced-motion`. No animation library.
- **Public pages are now in the accessibility scan** (light and dark), because the hero puts text over gradients.

## Consequences
- No new dependencies and no backend change; $0 LLM.
- Rounder corners reach dense screens too (board cards, tables). That is intended; the board and ticket list were reviewed.
- The first public-page scan caught a pre-existing problem (an in-sentence link distinguished only by colour on `/sign-up`), now underlined. The scan keeps public pages honest from here on.
- The scroll-reveal means a full-page screenshot taken without scrolling shows the lower sections transparent. Real scrolling reveals them, and the scan runs with reduced motion so text is measurable.
- Next's image optimizer caches by URL (four hours by default): a replaced screenshot needs a new file name.
- The landing screenshot is a snapshot of the UI and will drift as the UI changes. The production version is a scripted capture in CI.
