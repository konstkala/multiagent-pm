# Milestone 7a: publish safely + CI/CD on GitHub (cloud postponed)

## Context
M1–M6 are done and verified locally. M7 was "deploy": the user postponed the cloud and wants **$0**, a **public** repo, the GitHub **noreply** email in history, and an **MIT** license. So this milestone builds everything a team needs *before* a cloud: safe publication, CI on every push, versioned and scanned images in a registry, supply-chain hygiene, and a local "release" stack that runs exactly what CI built. The cloud deploy (Terraform, staging/prod, monitoring) becomes **M7b** later and plugs into this pipeline.

Facts found: `origin` = `github.com/konstkala/multiagent-pm`, **private, holding only the first 2 of 31 commits**. `gh` is logged in; plain `git` over HTTPS hangs on a credential prompt. The Gmail address appears **only in commit metadata** (0 matches in file contents across history). No `.env` or key files are tracked (265 files). GitHub id 103424025 → noreply `103424025+konstkala@users.noreply.github.com`. Cost: public-repo Actions and GHCR are free; **no LLM calls in CI** (`llm` tests stay excluded) → $0.

Plan saved to `docs/plans/2026-10-17-milestone-7a-ci-cd.md` once approved; ADR `docs/adr/0020-ci-cd-github-actions.md`.

## Steps (commit after each; nothing goes public until CI is green)

### 1. Publish safely (local first)
- Backup: `git bundle create ../multiagent-pm-backup.bundle --all` (outside the repo).
- Rewrite author + committer email on all commits to the noreply address (`git filter-branch --env-filter`, then delete `refs/original`); set `git config user.email` (repo-local) to the noreply address. Commit ids change; Co-Authored-By trailers stay.
- **Secret scan of the full history** with gitleaks (Docker image, exact version), plus a check that no `.env`, keys or tokens are tracked. Stop and report if anything is found.
- Add `LICENSE` (MIT, © 2026 konstkala); README: badges (CI, license) and a short "How it's built and checked" section.
- `gh auth setup-git` (git uses the gh login), then **force-push** the rewritten `main` to the still-private repo (replaces the 2 old commits; only the user has them).

### 2. CI workflow (`.github/workflows/ci.yml`, on push to main and on PRs)
Least-privilege `permissions: contents: read`, `concurrency` cancels superseded runs, every third-party action **pinned to a commit SHA** (resolved with `gh api` at implementation time), caches for uv, npm and Docker layers.
- **backend**: `uv sync --locked`; ruff check + format check; pyright; pytest against a `pgvector/pgvector:pg17` service container (user/db `pm`, matches the defaults in `backend/app/core/config.py`; `tests/conftest.py` builds `pm_test` from migrations); `alembic check` for model/migration drift.
- **frontend**: `npm ci`; `npm run check` (lint, typecheck, build).
- **api-contract**: regenerate `frontend/src/lib/api/openapi.json` + `schema.d.ts` (`npm run gen:api`) and fail on `git diff` — catches a forgotten regeneration (rule in `.claude/rules/api.md`).
- **secrets**: gitleaks on the pushed commits.
- **images**: build both Dockerfiles (no push on PRs).

### 3. Images to GHCR (`.github/workflows/images.yml`, on push to main and on tags `v*`)
- Build and push `ghcr.io/konstkala/multiagent-pm-backend` and `-web`, tags `sha-<short>` and `main` (and `vX.Y.Z` on tags); `permissions: packages: write` only here, using the built-in `GITHUB_TOKEN` (no stored secrets).
- **Trivy** scan: fail on CRITICAL with a fix available, upload SARIF to GitHub code scanning.
- **SBOM** and **build provenance** attestations (`actions/attest-build-provenance`).
- On a `v*` tag: GitHub Release with generated notes.
- `compose.release.yml` (override file): runs the published images by tag instead of building (`TAG=sha-abc1234 docker compose -f docker-compose.yml -f compose.release.yml up -d`) — local CD: deploy the exact artifact CI tested.

### 4. Supply chain and guard rails
- **CodeQL** (`codeql.yml`) for Python and TypeScript: free on public repos.
- **Dependabot** (`.github/dependabot.yml`): uv, npm, Docker, GitHub Actions; weekly, grouped minor/patch.
- **pre-commit** (`.pre-commit-config.yaml`): ruff, ruff-format, gitleaks, end-of-file/large-file checks; documented in README; the user runs `pre-commit install` once.
- **GitHub ruleset on main**: block force-push and deletion (after step 1's one-time force-push). No required PRs yet (user works on main); named as the production version.
- **Claude Code hook** (`.claude/settings.json` PreToolUse on Bash): block `git push --force`, `terraform apply|destroy` and `gh repo delete` unless the user runs them; ready for M7b.

### 5. Go public
- After the first green CI run on the private repo: switch visibility to **public** (`gh repo edit --visibility public --accept-visibility-change-consequences`), enable secret scanning + push protection, and remind the user to tick "Block command line pushes that expose my email" in GitHub settings (only they can).

### 6. Smoke tests in the repo (no CI cost by default)
- Move the scratchpad smoke scripts into `backend/scripts/smoke/` with one shared helper module (accounts, Mailpit tokens, rate-limit reset for the **dev** DB only), unique emails per run.
- `/smoke` skill (`.claude/skills/smoke/SKILL.md`): rebuild, wait healthy, run M2–M6 smokes, report.
- `e2e.yml` on manual dispatch only: compose stack in Actions + smokes, needs an `ANTHROPIC_API_KEY` repository secret the user adds in GitHub (never in chat). ~$0.003 per run; not run on PRs (secrets never reach forks).

### Docs
ADR 0020 (GitHub Actions + GHCR, SHA-pinned actions, keyless deploy later via OIDC); README CI section and badges; roadmap ticks: Git workflow (partly), CI, Quality gates, Secrets (CI part), Security (Dependabot, CodeQL, Trivy); glossary (CI, GHCR, SBOM, provenance, SHA pinning, SARIF, Dependabot, pre-commit, rulesets); CLAUDE.md commands (pre-commit, release compose).

## Verification
1. Before any push: gitleaks history scan clean; `git log --format='%ae' | sort -u` shows only the noreply address (and Anthropic's in trailers only).
2. Push to the private repo → all CI jobs green (`gh run watch`); a deliberately broken branch (e.g. stale openapi) fails the api-contract job, then is deleted.
3. Images appear in GHCR with SBOM/provenance; Trivy results in code scanning; `compose.release.yml` runs the pulled `sha-` images and the M6 smoke passes against them.
4. After going public: README badges green, CodeQL and Dependabot active, ruleset blocks a force-push.
5. Local checks unchanged: `uv run ruff check . && uv run pyright && uv run pytest`, `npm run check`.

## Result (2026-10-18)
Done. Public at https://github.com/konstkala/multiagent-pm. Every workflow is green, and the cost is $0 (CI makes no LLM calls).
- **Publishing:** gitleaks found nothing in 31 commits. Every commit now has the noreply author email.
- **A fresh repo instead of flipping visibility:** the old private repo still held the 2 force-replaced commits with the Gmail address, reachable by SHA. It was renamed to `multiagent-pm-private-old` and kept private. The public repo only ever had clean history.
- **CI caught real problems on its first runs:**
  - `frontend/public` was empty locally, so it was never in git, and a clean checkout couldn't build the web image. It now holds a `robots.txt`.
  - Trivy found 3 fixable CRITICAL CVEs in `perl-base` in the Debian 12 base of the web image. Both runtime stages now install security updates.
  - Trivy's secret scanner flagged a docstring inside the Anthropic SDK as a GCP key (a false positive). Image scans now cover vulnerabilities only; gitleaks covers secrets.
- **The CI proof PR** (an API change without a regenerated client) failed the api-contract job as designed. It was closed and deleted.
- **Provenance verified** with `gh attestation verify`: built by `images.yml` on `main` from the exact commit.
- **Local CD:** the stack ran from the GHCR images (`compose.release.yml`), and the M6 smoke passed 16/16 against them.
- **Smoke suites** moved into `backend/scripts/smoke/`: 80/80 checks across M2–M6 (`uv run python -m scripts.smoke`, or the `/smoke` skill).
- **The guard hook blocked its own author twice:**
  - First on a real force-push string in a test command, which proved it works.
  - Then on a commit message mentioning terraform. That was a false positive, fixed by ignoring heredoc text (17 cases tested).
- **Changes from the plan:**
  - A fresh public repo instead of a visibility flip.
  - The workflows that need a public repo (Trivy SARIF upload, CodeQL) were pushed after going public.
  - The smoke suites run locally and on demand, not on every push.
