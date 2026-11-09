# ADR-047: Durable Security Log, Startup Guard and Expiring CSRF Tokens

**Status:** Accepted
**Date:** November 9, 2026
**Context:** Security - OWASP A01, A02, A05, A07, A09 (audit of 9 Nov 2026, phase 2)
**Author:** Agustín Estévez
**Amends:** ADR-028 (CSRF), ADR-038 (client network identity), ADR-043 (login brake)

---

## Context

The OWASP audit of 9 Nov 2026 found that the security audit log lived only in a local
file that Render loses on every deploy; that granting the admin role, deleting an
account or changing its email left no trace; that a stray `TESTING` or an example
`SECRET_KEY` would start in production; that `/openapi.json` was public; that some
responses (CSRF 403, CORS preflight, 500) had no security headers; and that a signed
CSRF token never expired.

## Decision

1. **Security log to stdout and Sentry.** Every event is also one JSON line on stdout
   (Render keeps it); the file stays, and if it cannot be opened stdout keeps working.
   HIGH events go to Sentry as warnings and CRITICAL ones as errors, with the user ids
   only: no IP, no email, and the request reduced to method and path. Failed logins and
   resets for an unknown email never go to Sentry. Other HIGH events: at most one per
   type every 10 minutes per process, carrying how many were skipped; CRITICAL always.
   Sentry's logging integration ignores the audit loggers.
2. **Typed emails are masked** in the log as `a***@domain` plus an HMAC-SHA256 hash
   with a key derived from `SECRET_KEY` under its own label, to correlate attempts.
3. **Admin actions are audited** as CRITICAL events (actor, target, IP): role change,
   account deletion, email change request. Rejected actions write nothing.
4. **Startup guard.** Outside `ENVIRONMENT=development` (unset or unknown counts as
   production) the app refuses to start with `TESTING=true` or a `SECRET_KEY` that is
   missing, an example value from the repository, or shorter than 32 bytes. It also
   refuses `development` when `RENDER` is set. The JWT algorithm is fixed to HS256.
5. **Test hooks need both flags.** `X-Test-Client-ID` and the CSRF skip of the
   integration tests require `TESTING=true` AND `ENVIRONMENT=development` (amends
   ADR-038 and ADR-043: the Kind alone no longer picks its network).
6. **Private OpenAPI.** `/openapi.json` asks for the same Basic credentials as `/docs`;
   the three docs routes count against 20/minute per network before the credentials
   are checked. CI still builds the schema offline with `app.openapi()`.
7. **Headers everywhere.** The security headers middleware is the outermost one, and
   API responses carry `Content-Security-Policy: default-src 'none'; frame-ancestors
   'none'`, except the `/docs` and `/redoc` pages.
8. **Expiring CSRF tokens** (amends ADR-028): `random.issued.signature`, with the issue
   time (ASCII digits) inside the HMAC. Valid for the refresh token lifetime plus one
   hour (clock skew during a deploy); more than one hour in the future is rejected.
   Tokens without an issue time are rejected: on that 403 the frontend refreshes the
   session and retries once, so nobody is logged out by the deploy.

## Consequences

- The audit trail survives deploys, and Sentry quota is spent on rare events only.
- A misconfigured deploy fails at startup instead of running unprotected.
- Right after the deploy, active users get one silent CSRF 403 and retry, and the
  frontend reports it to Sentry as a warning.
- The Kind no longer honours `X-Test-Client-ID`; only the test suite does.
