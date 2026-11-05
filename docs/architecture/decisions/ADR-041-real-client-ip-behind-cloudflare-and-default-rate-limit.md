# ADR-041: The Real Client IP Comes From Cloudflare Only With an Origin Secret

**Status:** Accepted
**Date:** November 5, 2026
**Context:** Security - OWASP A01, A02, A04, A05, A09
**Author:** Agustín Estévez
**Amends:** ADR-038 (client network identity)

---

## Context

ADR-038 made every anonymous request count as Render's proxy, so in production each
anonymous limit was one bucket for the whole app. That has two costs (BE #466):

- A tournament with ~2,200 players would hit 429s on login and registration.
- Thirty failed logins a minute, from anywhere, closed login for everybody.

Cloudflare already sends the real address in `CF-Connecting-IP`. ADR-038 did not trust
it, because the Render origin can be called directly with any header. The audit IP also
took the leftmost `X-Forwarded-For`, which the client can write.

Separately, `Limiter(default_limits=["100/minute"])` never applied to any route (BE #467).
slowapi only applies it from its middleware, and with FastAPI 0.162 that middleware
cannot find the handlers of included routers: 114 routes had no limit at all.

## Decision

1. **An origin secret.**
   - A Cloudflare Request Header Transform Rule on `api.rydercupfriends.com` sets
     `X-Origin-Verify: <secret>` on every request.
   - Render holds the same value in `CLOUDFLARE_ORIGIN_SECRET`.
   - `CF-Connecting-IP` is believed only when the header matches, compared with
     `hmac.compare_digest` on bytes, and only if it is a real address: not
     unspecified, loopback or with an IPv6 zone.
2. **Fail-closed, never fail-open.**
   - A missing, wrong or empty secret, or an invalid `CF-Connecting-IP`, falls back to
     ADR-038's behaviour: the peer address for limits, today's logic for audit.
   - Requests without the secret are not rejected: Render's health check calls the
     origin directly.
3. **IPv6 limits key on the /64.** Each connection gets a whole /64; keying per address
   would let a caller rotate addresses per request. Audit stores the full address.
   IPv4-mapped IPv6 is stored as IPv4.
4. **The IP is an input for limits and audit only, never for authorisation** (A01).
5. **Neither the secret nor the client IP reaches Sentry.** `send_default_pii=False`
   does not remove custom headers. `before_send` and `before_send_transaction` remove
   `X-Origin-Verify`, `CF-Connecting-IP` and `True-Client-IP`, and the Sentry user is
   only the id (it also carried the `X-Forwarded-For` IP).
   - At startup the API logs whether the secret is set, and warns if it has surrounding
     whitespace; never its value or anything computed from it.
6. **The default limit is a global FastAPI dependency.**
   - It allows 100 requests per minute **per user and per route**.
   - Without a verified user it does not count. Those routes require a session and
     answer 401, which is what makes the frontend refresh; counting by network (the
     whole app without the real IP) answered 429 to expired sessions instead.
   - A route with its own `@limiter.limit` counts only that limit.
   - An explicit list is exempt: `/`, `/health`, the docs, avatar presets and countries.
   - Quick-match hole scoring allows 300/min: the offline queue sends 4 x 18 scores at
     once when coverage returns.
   - `/auth/refresh-token` has its own limit, keyed on the user of the verified refresh
     cookie (30/min), because the access token has already expired when it is called.
     Without a valid cookie it does not count: it answers 401, and a network bucket
     could be drained by anyone.

## Rotating the secret

Change it in Cloudflare and Render together. In between, requests fall into the shared
bucket, which breaks nothing.

## Rejected alternatives

- **Authenticated Origin Pulls (mTLS):** stronger than a shared header, but Render
  terminates TLS itself and cannot verify a client certificate.
- **`SlowAPIMiddleware`:** it does not reach included routers in FastAPI 0.162.
- **Trusting `CF-Connecting-IP` with `TRUST_CLOUDFLARE_HEADERS`:** anyone calling the
  origin directly could choose their bucket.

## Consequences

- Anonymous limits apply per real network once the Cloudflare rule is live. Until then,
  and whenever it is missing, the behaviour is ADR-038's.
- Device fingerprints do not change for honest clients: `CF-Connecting-IP` equals the
  leftmost `X-Forwarded-For` that the audit IP used before.
- A new route with a session is rate limited by default. Exempting one is an explicit
  change to `EXEMPT_FROM_DEFAULT_LIMIT`, checked by `tests/unit/config/test_rate_limit_routes.py`.
  A new anonymous route still needs its own `@limiter.limit`; a test checks that every
  route a visitor can reach has one.
