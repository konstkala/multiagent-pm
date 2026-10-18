# 0020. CI/CD on GitHub Actions; images built once, scanned, signed, deployed by tag

Status: accepted, 2026-10-18. The cloud deployment is postponed (milestone 7b).

## Context
The project went public on GitHub, and the cloud is postponed, with a $0 budget. We still want what a team expects before any cloud: every change checked, release artifacts we can trust, and dependencies kept current.

## Decision
- **CI:** GitHub Actions on every push and pull request.
  - Backend: lint, strict types, migration drift, and tests against a pgvector service container.
  - Frontend: lint, types and build.
  - Also: an API-contract diff, a gitleaks scan of the whole history, and image builds on pull requests.
  - No real LLM calls (tests use a fake Claude), so CI costs $0.
- **Hardening:**
  - Least-privilege `permissions` on every job.
  - Every third-party action pinned to a commit SHA of a release at least 14 days old. Dependabot updates the pins with a 14-day cooldown.
- **Images:** built once per commit on `main` and pushed to GHCR (`sha-<commit>`, `main`, semver on `v*` tags) with the built-in `GITHUB_TOKEN`.
  - Each image gets an SBOM and a build provenance signed through GitHub's OIDC identity.
  - Trivy reports HIGH and CRITICAL findings to code scanning and fails on a fixable CRITICAL, scanning vulnerabilities only.
- **Deploy by tag:** `compose.release.yml` runs the published images instead of building. The future cloud deploy (7b) uses the same tags, never a rebuild.
- **Repo safety:**
  - CodeQL, Dependabot, and secret scanning with push protection.
  - A ruleset on `main` (no force push, no deletion).
  - pre-commit hooks locally.
  - A Claude Code hook that blocks irreversible commands for the AI assistant.

## Consequences
- What runs is exactly what was tested, and anyone can verify where an image came from.
- The base-image patch step (`apt-get upgrade`) makes builds less reproducible. The production version pins base images by digest and lets Dependabot move them.
- There is no PR-required flow yet (the owner works on `main`). The production version: pull requests with required status checks and code review.
- For 7b: the cloud login from Actions uses OIDC workload identity (no stored cloud keys), and Terraform plans run in pull requests.
