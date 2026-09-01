# Security Posture

**TRINETRA is not certified secure, and this document does not claim it is.**
It states what is implemented, what is deliberately not, and what a real
deployment handling operational police data would still need.

---

## Implemented

### Authentication
- Passwords hashed with **scrypt** (n=2¹⁵, r=8, p=1, 16-byte per-user salt,
  32-byte derived key) from the Python standard library. No plaintext password
  is stored, logged, or returned by any endpoint.
- Verification is constant-time (`hmac.compare_digest`) and never raises on
  malformed stored values.
- Seed-time passwords are generated with `secrets` (16 characters, guaranteed
  character variety, ambiguous glyphs excluded) and written only to a
  gitignored file.
- Self-set passwords must pass a policy check: 12+ characters with upper, lower,
  digit and symbol.

### Sessions
- JWT access tokens (15 min default) and refresh tokens (8 h, or 7 days with
  "keep me signed in") in an httpOnly, SameSite=Lax cookie scoped to
  `/api/v1/auth`, marked Secure in production.
- **Refresh rotation**: the presented refresh token is revoked as the new one is
  issued, so a captured token has a single use.
- Server-side revocation list (`session_tokens.revoked`). Logout revokes every
  active token for the user; changing a password does the same.
- The client refreshes silently on 401 and replays the request once.

### Account protection
- Lockout after 5 consecutive failures for 15 minutes, tracked per account.
- Uniform failure messaging: a wrong Service ID and a wrong password return the
  same message, so the endpoint cannot be used to enumerate valid accounts.
- Rate limiting on `/auth/*` (20/min per IP) and on the API generally (300/min).

### Authorisation
- Five roles with granular, distinct permission sets.
- `require_permission(...)` is a FastAPI dependency on **every** protected
  route. Hiding a control in the UI is a usability affordance, never the
  boundary — the test suite asserts a lower-privileged role receives HTTP 403
  from the server.
- Permission denials are written to the audit log.

### Input handling
- Pydantic models validate and bound every request body; field errors are
  returned in a structured envelope.
- All database access is through SQLAlchemy with bound parameters. There is no
  string-built SQL anywhere in the codebase.
- Uploads are checked for extension, content type, size and row schema; CSV
  formula characters (`= + - @ tab CR`) are neutralised on ingest so an exported
  file cannot execute in a spreadsheet.
- Filenames are reduced to their basename before use.

### Output handling
- One error envelope for the whole API. Stack traces are logged server-side
  with a request ID and never returned to the client.
- Security headers on every response: `X-Content-Type-Options: nosniff`,
  `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, a restrictive
  `Permissions-Policy`, and a per-request `X-Request-ID`.
- CORS restricted to a configured allowlist.

### Auditability
- Append-only audit log covering sign-in success and failure, lockout, token
  refresh, logout, password change, searches, entity and evidence views,
  relationship validation and rejection, entity-resolution decisions, case
  changes, uploads, report generation, exports, SOS and alert transitions, and
  permission denials.
- Each entry records actor, role, action, resource, case, result, timestamp and
  IP. The actor name is denormalised so the trail stays readable even if the
  user record is later removed.

### Secrets
- No secret is committed. `SECRET_KEY` has no usable default in production and
  the application refuses to start without it.
- `.env`, `CREDENTIALS.md` and `*.db` are gitignored.
- In development an ephemeral key is generated per process and a startup
  warning is logged.

---

## Deliberately not implemented

These are absent by choice, and their absence is stated rather than hidden.

- **Multi-factor authentication.** Essential for a real law-enforcement
  deployment. Not present.
- **Encryption at rest.** The SQLite file is unencrypted. Operational data would
  require full-disk or database-level encryption.
- **TLS.** The development server runs plain HTTP on localhost. A deployment
  must terminate TLS at a reverse proxy and set `Secure` on all cookies.
- **Distributed rate limiting.** The limiter is in-process, so it is per-worker.
  Multiple workers need a shared store (Redis or similar).
- **Content Security Policy.** Not set. The client loads only same-origin
  vendored scripts, but a CSP header should be added at the proxy.
- **Signed or externally-anchored audit log.** The log is append-only by
  convention; nothing cryptographically prevents an operator with database
  access from altering it.
- **Field-level encryption** for sensitive identifiers.
- **Formal key rotation, secret management, or an HSM.**
- **Penetration testing and independent security review.** Neither has been
  performed.

---

## Before any deployment with real data

1. Independent security review and penetration test.
2. TLS everywhere, with HSTS and Secure cookies.
3. Multi-factor authentication.
4. PostgreSQL with encryption at rest, restricted network access, and backups.
5. Multi-factor-protected, externally-anchored audit storage.
6. A lawful basis and authorisation record for every data source ingested.
7. Data-retention and deletion policy consistent with applicable law.
8. Logging and alerting on authentication anomalies.
9. A documented incident-response process.

Until those are in place, this platform should be run only with synthetic data.
