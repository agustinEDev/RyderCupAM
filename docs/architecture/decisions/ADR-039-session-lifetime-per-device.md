# ADR-039: Sessions Belong to a Device, and Inactivity Is Decided by the Server

**Status:** Accepted
**Date:** September 24, 2026
**Context:** Security - OWASP A07 (Identification and Authentication Failures)
**Author:** Agustín Estévez
**Supersedes:** the logout behaviour described in ADR-015 (Phase 1 revoked every token)

---

## Context

Found during an end-to-end test in the local cluster (BE #376). Three players lost their
session without doing anything: their `POST /auth/refresh-token` returned 401, and the
database showed their refresh tokens revoked in bulk (50 tokens from 4 users in 4
seconds, and again an hour later).

Two pieces, each reasonable on its own, caused it together:

1. **The frontend logged you out after 30 minutes of inactivity** (`useInactivityLogout`,
   added in the December 2025 security sprint). It was a timer in the browser.
2. **`LogoutUserUseCase` revoked every refresh token of the user**, on every device.

So an idle window on one device dropped the session on all of them. For this product
that is a real failure. Players use the app on the course, often without signal. A
lunch break or a nine-hole stretch without touching the phone logged them out, and they
could not log back in. A window left open at home logged them out of the phone at the
course.

The 30-minute timer was also a weak control. It only fired while the tab was open. With
the tab closed or the battery dead, nothing was invalidated and the refresh token stayed
valid for 7 days.

## Decision

OWASP Top 10 compliance is required. A07 lists as a weakness *sessions or tokens that are
not properly invalidated during logout or after a period of inactivity*. The policy
covers both.

| Rule | Where |
|---|---|
| A session lasts at most **7 days** (refresh token lifetime, no rotation) | backend, unchanged |
| A device's session is invalidated after **24 hours without use** | backend: `UserDevice.is_idle()` / `SESSION_IDLE_TIMEOUT`, checked on refresh |
| **Logout revokes only the current device**: its refresh token (from the httpOnly cookie, never from the body) and older tokens of the same device | backend: `LogoutUserUseCase` |
| **Log out everywhere** means revoking devices from device management | existing |
| No client-side inactivity timer | frontend: `useInactivityLogout` removed |

- **Why 24 hours.** It covers a tournament day (tee time, 18 holes, lunch, afternoon
  session) without touching the phone. Someone who does not open the app for a day logs
  in again at home, with signal. OWASP ASVS 3.3.2 names 30 minutes idle or 12 hours
  absolute for level 2. This app holds golf scores and handicaps, with no payments or
  health data, and targets level 1 (re-authentication within 30 days). The 24-hour idle
  limit goes beyond that.
- **How "use" is measured.** A device's `last_used_at` is updated on login and on every
  token refresh. The app refreshes while it is in use, so a refresh after more than
  24 hours of silence means the device was idle.
- **Tokens without a device** predate device tracking. They cannot be measured and stay
  bounded by the 7-day lifetime.

## Consequences

- Logging out on one device never drops the others.
- Idle sessions are invalidated on the server whatever happens to the client (closed tab,
  dead battery, uninstalled app). The old timer could not do that.
- A player who leaves the app untouched for more than 24 hours in the middle of a
  multi-day tournament has to log in again. The first session of each day is usually
  opened at the hotel or the clubhouse, with signal.
