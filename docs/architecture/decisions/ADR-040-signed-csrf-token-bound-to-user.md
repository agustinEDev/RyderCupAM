# ADR-040: The CSRF Token Is Signed and Bound to the User

**Status:** Accepted
**Date:** November 5, 2026
**Context:** Security - OWASP A01 (Broken Access Control)
**Author:** Agustín Estévez
**Amends:** ADR-028 (CSRF protection)

---

## Context

ADR-028 introduced the double-submit cookie. The middleware checked only that
`X-CSRF-Token` equals the `csrf_token` cookie, and the token was
`secrets.token_urlsafe(32)` with nothing tying it to a session (BE #724).

The cookie lives on the shared parent domain, so `www` can read what `api` sets.
That makes the naive pattern weak against **cookie tossing**. Anyone who can write a
cookie on `.rydercupfriends.com` chooses both values and passes the check. That covers a
compromised or third-party subdomain, a subdomain takeover, and plain HTTP to any
subdomain. OWASP's CSRF cheat sheet discourages the naive form for this reason.

While fixing it, a second gap showed up. Exempt paths were matched by **prefix**, so
`POST /api/v1/auth/google/link` and `/google/unlink`, both authenticated actions, were
exempt because they start with `/api/v1/auth/google`. Only `SameSite=Lax` protected them.

## Decision

1. **Token shape `random.signature`.**
   - `random` is 256 bits, as before.
   - `signature` is `HMAC-SHA256(key, user_id + "!" + random)`, base64url.
   - Login, refresh, Google login and email verification issue it for their user.
2. **The key is derived, not new.** It is `HMAC-SHA256(SECRET_KEY, "rydercupfriends:csrf-token:v1")`.
   - Deploying needs no new variable in Render or the Kind (decided 4 Nov 2026).
   - The label keeps a CSRF signature from being valid for anything else.
3. **Bound to the user, not the device.**
   - The middleware takes the user from the session, in this order:
     1. the access JWT, from the cookie or the Bearer header;
     2. otherwise the refresh JWT.
   - It **verifies the JWT signature but not its expiry**. An expired access token still
     says whose session it is, and the request gets its 401 afterwards.
   - A JWT with a bad signature is ignored and the next source is tried.
4. **No session, nothing to impersonate.** Without a verifiable JWT, the header == cookie
   check stays as it was.
5. **Exempt paths match exactly.** GET sub-paths such as `/docs/...` are already exempt
   by method.

## Consequences

- A tossed cookie no longer passes. The attacker cannot sign for the victim's user id
  without the key.
- **Rollout:** tokens issued before the deploy are unsigned and get one 403
  `CSRF_VALIDATION_FAILED`.
  - Frontend 2.63.1 handles it without a logout: on a CSRF 403 it refreshes once and
    retries the request.
  - An older cached frontend logs the user out once.
- Rotating `SECRET_KEY` invalidates CSRF tokens together with every JWT, which is
  already a full logout.
- Binding to the device would be stricter, but it needs the session id before
  authentication runs. That can be added later without changing the token shape.
