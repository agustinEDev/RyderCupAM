# ADR-042: Devices Are Checked by Id, and a New Device Is Notified by Email

**Status:** Accepted
**Date:** November 6, 2026
**Context:** Security - OWASP A01, A04, A07, A09
**Author:** Agustín Estévez
**Amends:** ADR-039 (session lifetime per device)

---

## Context

Before this release (BE #737, FE #1046), revoking a device was checked by a browser
and IP fingerprint that never updated. With every browser update or network change it
missed the device: 34 of 60 in production. It could also log a legitimate user out
with a false "revoked". Other gaps:

- The list showed dead devices.
- One cookie held one account.
- The installed app and Safari merged into one device.
- A login without User-Agent opened a session with no device, which nobody could see
  or revoke.

## Decision

1. **The access token carries its device (`did`).**
   - `get_current_user` looks it up by id on every request. A revoked device gets a 401
     "Dispositivo revocado".
   - A token without `did` gets a plain 401, which the app answers with a refresh.
   - If the lookup fails, the request does not pass.
2. **Every session has a device.**
   - This covers login, Google, verify-email and refresh, also without a User-Agent
     (`unknown-user-agent`).
   - The refresh reuses the device of its refresh token and binds legacy tokens to the
     device it recognises.
3. **The device cookie holds up to 5 ids**, one per account in the browser. Logout does
   not delete it. `X-App-Mode: standalone` separates the installed app where it has its
   own cookies (iOS).
4. **The list shows only live sessions**, with the IP masked and the Cloudflare country.
   An hourly purge deletes devices unused for 30 days and refresh tokens expired more
   than 7 days ago.
5. **New sign-in email to the owner.**
   - It is sent when a login (password or Google) arrives without the device cookie:
     a new device, or one recognised only by its fingerprint, since the same phone on
     the same network cannot tell two people apart.
   - It is not sent to an unconfirmed email, nor on the Google sign-up.
   - At most one per device per hour.
   - It goes in the background and never breaks the login.
6. **Every revocation goes to the security audit log** with the revoked device id.

## Consequences

**Positive:**
- Revocation is immediate and does not depend on the network or the browser version.
- No device is invisible.
- The owner learns about a sign-in that does not carry their cookie.

**Negative / residual risk:**
- **A stolen refresh token still works from another browser** until it is revoked or
  expires: it receives the same `did`, and the route sets that device's cookie. Being
  bound to a device does not stop it being used elsewhere. The fix is rotating refresh
  tokens on each use with reuse detection, left for its own release.
- Whoever clears their cookies gets the notice when they sign in again.
- On Android and desktop the installed app and the browser share cookies, so they are
  one device. The list shows whichever was used last.
- Two simultaneous sign-ins from the same unknown device may send two emails. The cap
  is read before it is written.
- Naive datetimes are assumed to be UTC, as Render runs. This is the same assumption as
  BE #727.
