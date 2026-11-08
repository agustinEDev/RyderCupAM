# ADR-045: An Unverified Account Belongs to Whoever Proves Its Email, Every Access Path Locks the Account, and an Email Change Stays Pending

**Status:** Accepted
**Date:** November 7, 2026
**Context:** Security - OWASP A01, A04, A07, A09
**Author:** Agustín Estévez
**Amends:** ADR-044, ADR-042

---

## Context

Reviews of BE #749 found pre-account takeover: anyone could register with someone
else's email and a password and leave it unverified; when the owner later signed in
with Google, the account was linked and verified but kept the creator's password,
sessions and Google. Fixing it case by case kept revealing twin races, because each
path read the account, decided, and wrote in separate steps.

## Decision

1. **An unverified account belongs to whoever proves its email.** Signing in with a
   Google that verified the address, or resetting the password with the link sent to
   it, claims the account: email verified, every earlier device and session revoked,
   any linked Google removed, any pending email change cancelled (and, through Google,
   the unproven password and reset token too). The claim is logged (HIGH).
2. **Google needs proof.** Sign-up and auto-link need Google's `email_verified`
   (strict JSON `true`); linking Google from the profile needs a verified account
   email (`403 GOOGLE_LINK_NEEDS_VERIFIED_EMAIL`).
3. **One rule for every access path.** Paths that open a session or change
   credentials lock the user row (`SELECT ... FOR UPDATE`) before deciding, re-check
   on the locked row and write in the same transaction: password and Google login,
   opening a session after verifying the email (shared `guarda_la_sesion`), reset,
   Security, link and unlink, the claim. If the account changed meanwhile there is no
   session and the device that login created is revoked.
4. **A password reset closes everything:** sessions and devices, on any account.
5. **An email change stays pending** for 24 hours until confirmed from the new
   address with the account's session (`POST /users/me/email-change/confirm`). Until
   then the account keeps its email (and its verification); login, Google, reset and
   notices use it. The token is stored hashed. A link goes to the new address and,
   if the old one is verified, a masked notice to it. Any direct change (an admin's)
   or reset cancels it.

## Consequences

**Positive:** an unverified account can no longer be kept by its creator, and no
access path decides on stale data.

**Negative / residual risk (next release):**
- The sign-up verification link still opens a session: a victim who clicks a link for
  an account they did not create ends up in an account whose password the creator
  knows. Decided: verify without a session, and say so in the mail.
- Linking Google needs only a session: a stolen one can add a Google that survives a
  reset. Decided: ask for the current password, and mail on link and unlink.
- An admin email change still applies at once, unverified; decided: pending too.
- No mail to the old address when the change is confirmed, nor to the owner when the
  account is claimed; no specific rate limit on asking for a new email (3/hour
  decided).
- A first Google sign-in by an owner whose unverified account had a password removes
  it without notice (3 such accounts in production on November 6).

## Amendment (7 Nov 2026, RyderCupAM #753)

The residual risks above were closed in the next release:
- Verifying the sign-up email only verifies; it opens no session, and the mail tells
  whoever did not create the account to use "Forgot password".
- Linking Google needs the current password, confirmed in the last 5 minutes (a signed,
  httpOnly, single-use mark scoped to the Google routes); link and unlink are mailed,
  also an automatic link when signing in with Google.
- A password reset also removes a linked Google on a verified account: a session thief
  could have added it. A real owner links it again.
- An admin email change stays pending too (point 5 above no longer applies to admins).
- A verified old address is told when a change is requested (as since #749) and again
  when it is confirmed; the owner is told when an unverified
  account is secured; asking for a new email is limited to 3 per hour within 10 security
  requests per hour per user.

Amended again (8 Nov 2026): the verification mail no longer mentions "Forgot password"
(the owner read it as an invitation to take accounts); it only says to ignore the mail.
The claim path is told where the email's owner looks for it instead: signing up with an
address that already has an account explains how to recover it (Google or "Forgot
password"), with a link. The sign-up already said the address exists.

Still residual: the single-use mark lives in memory (one process; a restart forgets
spent marks younger than 5 minutes), and reauthenticating does not lock the account,
only the per-user limit applies.

