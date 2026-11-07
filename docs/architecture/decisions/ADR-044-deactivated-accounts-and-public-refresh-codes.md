# ADR-044: A Deactivated Account Loses Its Session, and the Refresh Exposes Two Codes

**Status:** Accepted
**Date:** November 6, 2026
**Context:** Security - OWASP A01, A04, A07, A09
**Author:** Agustín Estévez
**Amends:** ADR-042 (devices) and the refresh rejection codes of BE #731

---

## Context

- **BE #744:** deactivating an account only set `is_active`. The access token kept
  working, and the refresh kept issuing new ones for up to 7 days. A deactivated admin
  kept passing `require_admin`.
- **BE #733:** since BE #731 the refresh 401 carried the exact reason. Anyone holding a
  stolen refresh cookie could learn whether the account was deleted, the password
  changed or the user signed out.
- **BE #738:** code kept for the 2.50 rollout was no longer needed. A read-only check
  in production on 6 Nov found no live refresh token without a device and no device
  with a `10.x` address.

## Decision

1. **Deactivating an account revokes all its devices and refresh tokens** in the same
   transaction, and the security log records who did it and how much was revoked.
   Reactivating does not restore them: the user signs in again.
2. **An inactive account has no session.** `get_current_user` and the refresh both
   reject it (401), without waiting for the access token to expire.
3. **The refresh 401 carries only `SESSION_ENDED`** (missing, expired or idle) **or
   `SESSION_REJECTED`** (everything else), with the same text. The exact reason goes to
   the security log. The frontend, which ships first, accepts the old and new codes.
4. **Every session has a device:** a refresh token without one is rejected, and
   `device_id` is required in the login, Google and refresh responses. The
   `should_set_device_cookie` field is removed (breaking change, `api-breaking`), since
   the device cookie is set on every login and refresh.

## Consequences

**Positive:**
- A deactivated user, admin or not, is out on their next request.
- The refresh no longer tells the state of an account.
- Less code: no legacy refresh binding, no device registration in the refresh.

**Negative / residual risk:**
- The frontend's forced-logout notice can no longer tell a revoked device from a
  deleted account; only the security log can.
- Removing `should_set_device_cookie` breaks any client that still reads it. The
  frontend does not.
