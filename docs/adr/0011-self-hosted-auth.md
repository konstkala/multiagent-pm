# 0011. Self-hosted authentication

Status: accepted, 2026-10-16

## Context
Users sign in with Google or with email and password, and can verify their email and reset a forgotten password. A managed provider (Clerk, Auth0, Supabase) would do this with less code; building it teaches security engineering, which is a goal of this project.

## Decision
The backend owns users and sessions, using vetted libraries only: argon2id for passwords, Python's `secrets` for tokens, and for Google OpenID Connect the authorization-code flow with PKCE, state and nonce, using httpx for the token exchange and PyJWT (with Google's published keys) to verify ID tokens. (Amended 2026-10-17: PyJWT instead of Authlib, which would have needed signed-cookie session middleware for a flow we can keep in the database.) Sessions are opaque random tokens in `httpOnly` cookies, stored hashed. Email via SMTP (Mailpit locally). We follow the OWASP authentication, session-management and forgot-password cheat sheets.

## Consequences
- No vendor, no per-user cost, full control and full learning.
- We carry the security risk: every auth change gets tests for enumeration, token reuse, expiry and rate limits.
- Adding passkeys or SSO later is our work, not a provider setting.
