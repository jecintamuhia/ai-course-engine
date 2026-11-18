# Decision Record: JWT Lifecycle

**Status:** OPEN — REQUIRES CLIENT APPROVAL
**Decision owner:** Client
**Sources:** `AGENTS.md`, `docs/client-requirements-compliance-audit.md`
(finding 6.9), `docs/production-readiness.md`, working tree.

This record recommends an option; it does not record a client decision. No
approval is claimed and no authentication code or configuration was changed for
this record.

## Context

Sign-in, registration and Google exchange issue an application JWT. The audit
records a long-lived bearer token with no refresh, revocation or server logout.
Token lifetime is a product and security decision: shortening it without
refresh handling breaks sessions, while adding refresh/revocation changes
storage, client behaviour and operational dependencies.

## Current implementation

- `create_access_token` (`backend/app/core/security.py:59`) signs `sub`, `role`,
  `iat` and `exp` with the configured algorithm; `jwt_algorithm` defaults to
  `HS256` and `jwt_access_token_expire_minutes` defaults to `720`
  (`backend/app/core/config.py:124`).
- `decode_access_token` validates signature and expiry; `get_current_user`
  (`backend/app/core/dependencies.py:105`) resolves the subject and rejects
  missing/inactive accounts, so deactivation takes effect on the next request.
- There is no refresh token, `jti`, denylist, logout endpoint or token-version
  check. Passwords use Argon2 and login is rate-limited.
- The SPA stores the access token in `localStorage`
  (`backend/frontend/src/lib/auth.ts:3`) and sends it as
  `Authorization: Bearer <token>`; it does not proactively act on expiry.
- Google sign-in returns a short-lived, single-use Redis exchange code, not a
  token in the redirect URL (`backend/app/api/v1/auth.py:175`, `:255`). This
  pattern is independent of access-token lifetime.
- No live/staging Moodle or browser session was used to test expiry behaviour.

## Options

| Option | Summary | Consequence |
| --- | --- | --- |
| A. Keep current bearer token | Retain a 720-minute default and document the risk. | No code change; stolen tokens remain usable until expiry and logout is client-side only. |
| B. Access + refresh rotation | Short access token, rotating refresh token, server-side revoke/logout, SPA refresh/expiry handling. | Preferred security posture; requires schema/Redis state, new endpoints and tests. |
| C. Server-side denylist | Keep current token shape but add `jti` and a Redis denylist consumed on every request. | Enables logout/revocation without refresh; adds a hard runtime dependency and still needs expiry handling. |

## Recommendation (not a decision)

Choose **B** before public exposure if the client requires revocation or a
short session window. Keep the existing Google exchange-code pattern and add
explicit SPA handling for `401`/expiry rather than silently retrying. Do not
change the default TTL in isolation: without refresh and logout, users would be
signed out abruptly and no server-side invalidation would be gained.

## Client decision needed

1. Accept the current long-lived bearer risk, or require revocation/logout and
   short-lived access tokens?
2. If refresh is required: access TTL, refresh TTL, rotation policy, absolute
   session limit and where refresh tokens are stored.
3. What revocation events are required (logout, password change, deactivation,
   admin action) and what should happen to in-flight browser sessions?
4. Are `localStorage` storage and the proxy-trust assumptions acceptable for
   the target deployment?

## Status

OPEN — REQUIRES CLIENT APPROVAL. Finding 6.9 remains unresolved; this document
does not close it.
