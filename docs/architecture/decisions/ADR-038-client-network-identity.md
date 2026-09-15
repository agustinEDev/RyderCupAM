# ADR-038: Client Network Identity Is Never Derived From Client-Controlled Headers

**Status:** Accepted
**Date:** September 7, 2026
**Version:** documents behaviour in place since v1.13.0 → v2.0.4
**Context:** Security - OWASP A04, A07, A09
**Author:** Agustín Estévez

---

## Context

Production runs behind **two** proxies: Cloudflare in front of a Render web service.
Verified against the live API:

```
server: cloudflare
cf-ray: a3771fed0fbfd8ff-MAD
x-render-origin-server: uvicorn
```

Because of that chain, `request.client.host` inside uvicorn is the address of the last
hop — Render's internal load balancer — and **not** the user's address. Recovering the
user's address means trusting a forwarding header, and every one of those headers is
written by whoever sends the request.

This has already gone wrong twice, in both directions:

1. **Trusting the proxy's own address broke device identification.** In v1.13.0 the
   device fingerprint was `SHA256(device_name + user_agent + ip_address)`. Behind Render
   every user resolved to a `10.x.x.x` load balancer address, so devices collapsed and
   duplicated against each other (`43df5ca`, PR #54).
2. **Trusting the real address broke sessions.** Once `CF-Connecting-IP` was honoured,
   the fingerprint started following the user's *actual* address — which rotates inside
   the same ISP. The result was **automatic logout roughly every five minutes**, traced
   to a single user's address moving from `92.176.11.158` to `92.176.11.205` (`9b2ecc5`,
   v2.0.3). Normalising to /24 and /64 reduced it but did not close it.

The resolution was not a better header. It was to stop deriving identity from the
network at all: v2.0.4 moved device identification to a persistent httpOnly `device_id`
cookie, and demoted the IP address to an audit-only field (see
[ADR-030](ADR-030-device-fingerprinting.md), Key Design Decision #2).

A parallel decision had already been taken for rate limiting. In `41f4ad1` the
rate-limit key was changed so that **no header can select it in production**:

```diff
-    En producción: Usa la IP real del cliente.
+    En producción: Usa SOLO la IP real del cliente (ignora headers para evitar bypass).
```

And [ADR-027](ADR-027-account-lockout-brute-force-protection.md) had explicitly rejected
per-IP rate limiting as the primary brute-force defence, for exactly this reason —
*"IP-based Rate Limiting only: Bypassable with proxies"* — choosing temporary account
lockout instead, which keys on the account and never looks at the network.

Those decisions were made separately, months apart, and none of them is written down as
a policy. That is what this ADR fixes: the reasoning was reconstructed from git history
in September 2026, after the conclusion had already been lost once and nearly reverted.

---

## Decision

**A client's network identity is never derived from a header the client can write.**

Concretely, and all of this is the state of the system today:

1. **Rate limiting keys on `request.client.host`** via `get_remote_address`
   (`src/config/rate_limit.py`). In production the `X-Test-Client-ID` escape hatch is
   disabled; it exists only for `development` and `testing`.
2. **`FORWARDED_ALLOW_IPS` is deliberately not set** on the Render service. uvicorn
   ships with `proxy_headers=True` but resolves `forwarded_allow_ips` to `127.0.0.1`, so
   it never rewrites `scope["client"]` in production. Setting it to `*` would make
   uvicorn take `X-Forwarded-For[0]` — the leftmost entry, which is the one the client
   supplies, because Cloudflare and Render *append* rather than overwrite.
3. **`TRUST_CLOUDFLARE_HEADERS` is `false`** on the Render service. `CF-Connecting-IP`
   is only unforgeable while the Render origin cannot be reached directly; and since
   v2.0.4 nothing depends on resolving the real address anyway.
4. **Device identity is the httpOnly `device_id` cookie**, not the address (ADR-030).
5. **The stored IP address is an audit field.** It is evidence, never an authorisation
   or identification input.

### The trade-off, stated plainly

Today every production request shares one rate-limit bucket, because every request
resolves to the same proxy address. That is **fail-closed**: in the worst case,
legitimate users are throttled more aggressively than intended.

The alternative — keying on a forwarded header — is **fail-open**: an attacker rotates
one header value per request and has *no* limit at all, while ordinary users, who send
no such header, keep theirs. It converts a rate limiter into a rate limiter that stops
exactly the people it was not built to stop.

Given that ADR-027 already places the real brute-force defence in per-account lockout,
the shared bucket costs little and the bypass would cost a lot. That asymmetry is the
whole decision.

---

## Consequences

### Positive

- No request-scoped header can widen, narrow, or evade a limit (**A04**).
- Brute-force protection does not degrade when the network view is wrong (**A07**),
  because it never depended on it.
- Sessions survive IP rotation, VPNs, and mobile network handover — the v2.0.3 logout
  loop cannot recur (**A01**).

### Negative — accepted knowingly

- **The rate limit does not distinguish users in production.** 100 req/min and 5
  logins/min are a single shared bucket. Under real tournament load this will surface as
  spurious 429s before it surfaces as anything else.
- **Audit IPs are weak evidence.** `get_trusted_client_ip()` does honour
  `X-Forwarded-For` when the peer falls inside `TRUSTED_PROXIES` (`10.0.0.0/8` in
  production), and it takes the *leftmost* entry
  (`http_context_validator.py`). A caller can therefore write the address that lands in
  `user_devices.ip_address` and in `security_logger` records. This is tolerated because
  those values are audit trail, never an access decision — but it means an IP in the
  logs is a claim, not a fact (**A09**).
- The policy lives in dashboard configuration that is not in git, since there is no
  `render.yaml`. This ADR is the only reproducible record of it.

---

## When to revisit

This decision is not permanent. Reopen it if any of these becomes true:

- **The shared bucket starts hurting real users.** The fix is not headers: it is keying
  authenticated traffic on the user id, which is server-derived and unforgeable, and
  leaving anonymous traffic on the shared bucket.
- **The Render origin is closed to everything but Cloudflare.** With direct access to
  the origin removed, `CF-Connecting-IP` becomes genuinely unforgeable and
  `TRUST_CLOUDFLARE_HEADERS=true` becomes defensible — for audit quality, not for
  limits.
- **Audit IPs are needed as evidence** rather than as context. That requires the
  previous point first.

Any change here must keep the invariant in the title. A proposal that improves address
accuracy by trusting a client-writable header is the thing this ADR exists to refuse.

---

## Alternatives Considered

- **❌ `FORWARDED_ALLOW_IPS=*`** (the standard Render recommendation): makes uvicorn read
  the leftmost `X-Forwarded-For` entry. Trivially spoofable; converts fail-closed into
  fail-open.
- **❌ `TRUST_CLOUDFLARE_HEADERS=true` today**: spoofable while the origin is directly
  reachable, and buys nothing, since no identity decision depends on the address.
- **❌ Rightmost-untrusted `X-Forwarded-For` parsing**: sound in principle, but requires
  keeping Cloudflare's published ranges in `TRUSTED_PROXIES` and re-syncing them
  forever. Cost without a consumer, while the address remains audit-only.
- **✅ Keep the network out of identity decisions**: chosen. It is what made the v2.0.3
  logout loop go away for good.

---

## References

- [ADR-027](ADR-027-account-lockout-brute-force-protection.md): Account Lockout —
  rejects per-IP rate limiting as the primary brute-force defence
- [ADR-030](ADR-030-device-fingerprinting.md): Device Fingerprinting — IP demoted to
  audit-only in v2.0.4
- [ADR-023](ADR-023-security-strategy-owasp-compliance.md): OWASP compliance strategy
- `41f4ad1` — rate-limit key stops accepting a header in production
- `43df5ca` (PR #54) — Cloudflare headers adopted for fingerprinting
- `9b2ecc5` — IP normalisation after the five-minute logout loop
- `6af7b00` — `TRUST_CLOUDFLARE_HEADERS` introduced, defaulting to `false`
- Issue #274 — closed by this ADR
- OWASP A04 Insecure Design, A07 Authentication Failures, A09 Logging Failures
