# ADR-028: CSRF Protection (Cross-Site Request Forgery)

**Status:** Accepted
**Date:** January 8, 2026
**Version:** v1.13.0
**Context:** Security - OWASP A01
**Author:** Agustín Estévez

---

## Context

The REST API needs protection against CSRF attacks where a malicious site forces the user's browser to send unauthorized requests to our backend. Without CSRF protection, an attacker could:
- Change user email/password
- Create/modify competitions
- Perform critical actions without consent

**Attack scenario:**
1. Authenticated user visits `evil.com`
2. `evil.com` sends POST to `rydercupfriends.com/api/v1/users/me/security`
3. Browser automatically includes cookies (access_token, refresh_token)
4. Backend accepts request → unauthorized email change

---

## Decision

Implement **triple-layer** CSRF protection:

### 1. Custom Header X-CSRF-Token (Primary)
- Frontend sends token in `X-CSRF-Token` header
- Attacker CANNOT add custom headers in cross-origin requests
- Browser blocks arbitrary headers (Same-Origin Policy)

### 2. Double-Submit Cookie Pattern
- CSRF token sent in `csrf_token` cookie (httpOnly=false)
- Middleware validates: `cookie == header` (timing-safe comparison)
- Token generation: 256 bits (secrets.token_urlsafe(32))

### 3. SameSite="lax" (Already implemented)
- access_token cookie with SameSite="lax"
- Prevents cookie sending in cross-site requests (POST/PUT/DELETE)

**Validation:**
- POST, PUT, PATCH, DELETE: Require valid CSRF token
- GET, HEAD, OPTIONS: Exempt (safe methods RFC 7231)
- Public routes: /health, /docs, /openapi.json exempt

**Generation:**
- Login: Generates CSRF token (15 min)
- Refresh token: Generates NEW CSRF token (15 min)
- Logout: Deletes csrf_token cookie

---

## Consequences

### Positive ✅
- **OWASP A01 9.5→9.7**: Solid CSRF protection
- **No DB changes**: Stateless tokens (not persisted)
- **Minimal overhead**: Simple validation (string comparison)
- **SPA compatible**: React can read cookie and send header

### Negative ⚠️
- **Frontend change**: Must read `csrf_token` and send in header
- **httpOnly=false**: CSRF cookie accessible from JS (required)
- **Synchronization**: Renew token on each refresh (frontend)

### Risk Mitigation
- Non-httpOnly cookie is secure: Attacker CANNOT read it (Same-Origin Policy)
- SameSite="lax" as additional defense layer

---

## Alternatives Considered

### ❌ Option A: SameSite="strict" only
- **Rejection**: Breaks legitimate auth flows (external links)

### ❌ Option B: Verify Origin/Referer header
- **Rejection**: Easily bypassable, not recommended by OWASP

### ❌ Option C: csrf library (npm)
- **Rejection**: Manual implementation simpler for this case

---

## References

- OWASP CSRF Prevention Cheat Sheet: https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html
- ADR-019: Session Timeout with Refresh Tokens
- ADR-014: httpOnly Cookies

---

**Review:** This ADR is immutable. Future changes require new ADR.
