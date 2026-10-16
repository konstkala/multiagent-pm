# Claude Code cheat sheet

Quick reference for prompting in this project. Checked against the Claude Code docs, Oct 2026.

## 1. Our rule files

Each file loads only when Claude reads or edits a file under its path.

| File | Loads for | Covers | Example prompt |
|---|---|---|---|
| `.claude/rules/agents.md` | `backend/app/agents/**` | model + effort, prompts, tools, approvals, budget | "Add a triage agent in `agents/triage/`. Follow the agents rules and state its $/run." |
| `.claude/rules/api.md` | `backend/app/api/**` | thin routers, response models, 202 + SSE for runs | "Add `POST /tickets/{id}/triage`. It enqueues a run per the API rules." |
| `.claude/rules/db.md` | `backend/app/db/**` | migrations, constraints, queue, pgvector | "Add a `tickets` table with an embedding column. Write the migration." |
| `.claude/rules/tests.md` | `backend/tests/**` | no real LLM calls, real Postgres, guardrail tests | "Write tests for the triage agent using `TestModel`, including a prompt-injection case." |
| `.claude/rules/frontend.md` | `frontend/**` | generated client, server components, approval UI | "Build the approval panel for pending agent actions." |
| `.claude/rules/logging.md` | always | event names, correlation ids, audit + security events, no secrets | "Add audit logs to ticket updates per the logging rules." |

Rules load when Claude touches a matching file. If you want a rule applied before any file is opened, name it: "follow `.claude/rules/agents.md`".

## 2. What rules can do

| Feature | How | Example |
|---|---|---|
| Always-on rule | `.md` in `.claude/rules/` with no `paths` | `.claude/rules/security.md` |
| Path-scoped rule | `paths:` frontmatter (YAML list or comma string) | `paths: ["backend/app/api/**"]` |
| Several globs / extensions | list entries + brace expansion | `"frontend/**/*.{ts,tsx}"` |
| Subfolders | rules are found recursively | `.claude/rules/backend/api.md` |
| Personal rules, all projects | `~/.claude/rules/` | your own style preferences |
| Shared rules across projects | symlink into `.claude/rules/` (on Windows prefer `~/.claude/rules/`) | `ln -s ~/shared-rules .claude/rules/shared` |
| Skip a rule or CLAUDE.md | `claudeMdExcludes` in settings (globs on absolute paths) | exclude a noisy rule temporarily |
| Check what loaded | `/context` → *Memory files* | after editing a rule |
| Debug bad frontmatter | `claude --debug` | rule loads everywhere unexpectedly |

`paths` is the only frontmatter field rules read. Other fields are silently ignored.

## 3. CLAUDE.md and memory

| Feature | How | When to use |
|---|---|---|
| Project instructions | `CLAUDE.md` (keep < 200 lines) | facts needed in every session |
| Personal project notes | `CLAUDE.local.md` (gitignore it) | your local URLs, test data |
| Personal, all projects | `~/.claude/CLAUDE.md` | how you like to work |
| Import a file | `@path/to/file` in CLAUDE.md (max 4 hops) | organize only; it still loads every session |
| Mention a path without importing | wrap in backticks: `` `@README` `` | |
| Generate / improve CLAUDE.md | `/init` | after the scaffold, to suggest the Commands section |
| Browse and edit memory files | `/memory` | also toggles auto memory |
| Auto memory | Claude saves notes when you say "remember …" | preferences, corrections |
| Write to CLAUDE.md instead | "add this to CLAUDE.md: …" | project-wide facts |
| Find conflicting or stale instructions | `/doctor prompt-audit` | every few weeks |

## 4. "Commands" means two different things

| | CLAUDE.md `## Commands` section | Custom slash commands (skills) |
|---|---|---|
| What | shell commands Claude runs (test, lint, dev) | reusable prompts you trigger with `/name` |
| Where | `CLAUDE.md` | `.claude/skills/<name>/SKILL.md` (legacy: `.claude/commands/<name>.md`) |
| Status here | TBD until the scaffold exists | none yet |

**Skill frontmatter**

| Field | Does |
|---|---|
| `description` | when Claude should use it (the only recommended field) |
| `disable-model-invocation: true` | only you can trigger it with `/name`. Use for side effects |
| `allowed-tools` | pre-approves tools for that turn, e.g. `Bash(uv run pytest *)` |
| `argument-hint` | autocomplete hint, e.g. `[agent-name]` |
| `$ARGUMENTS`, `$0`, `$1` | text typed after `/name` |
| `model`, `effort` | model / effort while the skill runs |
| `context: fork` + `agent` | runs it in a subagent |
| `paths` | only offered for matching files |
| `` !`cmd` `` in the body | runs the command first and inserts its output |

**Skills worth making here (once the code exists)**

| Skill | Purpose |
|---|---|
| `/check` | lint + typecheck + tests, report pass/fail |
| `/new-agent <name>` | scaffold an agent folder per the agents rules |
| `/adr <title>` | write the next numbered ADR in `docs/adr/` |
| `/cost-report` | summarize tokens and $ per agent from Langfuse |

## 5. Built-in commands you'll use most

| Command | Use |
|---|---|
| Shift+Tab | cycle permission modes, including plan mode |
| `/model opusplan` | Opus plans, Sonnet implements (our default) |
| `/context` | see what fills the context window, including loaded rules |
| `/memory` | edit CLAUDE.md / memory files |
| `/compact` | shrink a long session. Root CLAUDE.md is re-read, path rules reload on demand |
| `/status` | version, settings, oversized-instruction warnings |
| `/skills` · `/skill-doctor` | list skills · see each skill's context cost and usage |
| `/permissions` | allow/deny tool rules |
| `/code-review`, `/simplify` | review the current diff for bugs / cleanups |
| `/init` | create or improve CLAUDE.md |

## 6. Prompts

Flow: brainstorm → plan (Shift+Tab into plan mode; Opus) → implement (Sonnet) → review.

| Stage | Prompt |
|---|---|
| Brainstorm | "Brainstorm `<idea>`. No code. Give 3 approaches with trade-offs (complexity, $/run, latency), recommend one, then ask the 3 questions that most change the design." |
| Brainstorm | "Interview me about `<feature>` one question at a time until you can write a spec." |
| Brainstorm | "Single agent or multi-agent for `<X>`? Estimate tokens and $/run for each." |
| Brainstorm | "What's the smallest version of `<feature>` that teaches me the most about agents?" |
| Brainstorm | "Which Claude Code features (skill, hook, subagent, rule, MCP) would help build `<X>`?" |
| Plan | "Plan `<feature>`. List files to touch, steps, tests, cost impact, open questions. Save to `docs/plans/<date>-<slug>.md`." |
| Plan | "Challenge this plan: what breaks, what's over-engineered, what can be cut?" |
| Plan | "Is this ADR-worthy? If so, draft `docs/adr/NNNN-<slug>.md`." |
| Implement | "Implement step 1 of `docs/plans/<file>.md` only. Stop and show me the diff." |
| Implement | "Write the failing tests for `<behaviour>` first, then make them pass." |
| Cost | "Where do the tokens go in `<agent>`? How much would caching, Haiku, or the Batch API save?" |
| Review | `/code-review` for bugs, `/simplify` for cleanups, then "Is the cost impact noted?" |
| Learn | "Explain how `<concept>` works using our code as the example." |
| Learn | "Why did you choose X over Y? What would make Y the better choice?" |

## 7. When to use what

| You want… | Use |
|---|---|
| a fact true in every session | CLAUDE.md |
| guidance for one folder or file type | path-scoped rule |
| a repeatable multi-step workflow | skill (`/name`) |
| something that must never happen | hook (PreToolUse) or `permissions.deny`, not a rule |
| a personal preference | `~/.claude/CLAUDE.md`, `CLAUDE.local.md` or auto memory |
