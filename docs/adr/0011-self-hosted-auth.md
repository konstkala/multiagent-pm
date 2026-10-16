# 0011. Self-hosted authentication

Status: accepted, 2026-10-16

## Context
Users sign in with Google or with email and password, and can verify their email and reset a forgotten password. A managed provider (Clerk, Auth0, Supabase) would do this with less code; building it teaches security engineering, which is a goal of this project.

## Decision
The backend owns users and sessions, using vetted libraries only: argon2id for passwords, Authlib for Google OpenID Connect, Python's `secrets` for tokens. Sessions are opaque random tokens in `httpOnly` cookies, stored hashed. Email via SMTP (Mailpit locally). We follow the OWASP authentication, session-management and forgot-password cheat sheets.

## Consequences
- No vendor, no per-user cost, full control and full learning.
- We carry the security risk: every auth change gets tests for enumeration, token reuse, expiry and rate limits.
- Adding passkeys or SSO later is our work, not a provider setting.
