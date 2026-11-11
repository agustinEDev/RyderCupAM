# ADR-048: Sign-up Does Not Reveal Existing Accounts, Email Links Are Hashed and Expire, and the Reset Brake Counts per Email and Network

**Status:** Accepted
**Date:** November 10, 2026
**Context:** Security - OWASP A02, A04, A07, A09
**Author:** Agustín Estévez
**Amends:** ADR-043 (the brake model), ADR-045 (the sign-up hint)

---

## Context

The security review of phase 3 found (F-01, F-04, F-05, F-10, F-13):

- Sign-up answered `409 "already registered"` for a taken email, without spending the
  bcrypt: by status, text and time, anyone could check whether an email had an account.
- Verification and reset tokens were stored in plaintext, the verification link never
  expired and the reset link lasted 24 hours.
- Validating a reset link took the token in the URL (`GET /auth/validate-reset-token/{token}`),
  where access logs, proxies and Sentry keep it.
- "Forgot password" counted 3 per hour per email from any network: three requests from
  anyone kept the owner without a link for an hour, and an account had no daily ceiling.

## Decision

1. **Sign-up answers the same** for a new email (B1), an existing verified account (B2)
   and an existing unverified one (B3): `201` with the submitted data and an id that is
   never stored, after the same bcrypt and RFEG lookup. The existing account is not
   touched. Its mailbox gets a notice ("someone tried to sign up with your email; sign in
   or reset your password"), at most one every 24 hours per account, recorded with the
   row locked; a deactivated account gets none. No new verification link is sent for an
   unverified account: it would verify an account whose password its creator knows; the
   reset link claims it instead (ADR-045). Two sign-ups at once: the second answers the
   same `201`, and the same notice as if it had arrived later (the unique violation
reaches the use case as `EmailTakenConcurrentlyError`; any other error goes up).
2. **Emails leave in the background**: the sign-up verification, the sign-up notice and
   the reset link (`ICorreoEnSegundoPlano`), and the verification resend
   (`IReenvioDeVerificacion`). The response never
   waits for the provider, so its time does not depend on the account existing; the
   artificial 0.5 s delay of "forgot password" is gone.
3. **Links are stored as their SHA-256** and looked up by hash: verification (48 hours,
   `VERIFICATION_TOKEN_EXPIRED` when it expires, to offer `POST /auth/resend-verification`)
   and reset (1 hour, single use, a new one voids the previous). The migration of this
   release voids the pending plaintext links: whoever clicks an old one sees "invalid
   link".
4. **Reset links are validated by `POST /auth/validate-reset-token`** with the token in
   the body. The GET stayed in 2.57.0, deprecated, with its token filtered out of
   Sentry; 2.58.0 removed both.
5. **"Forgot password" counts 3 per hour per email and network** (like the login,
   ADR-043), and **10 emails per account in 24 hours** from anywhere. Above that nothing
   is sent, the previous link stays valid and the answer is the same. The daily quota
   resets when the account proves it is its own: a successful sign-in (password or
   Google) or password reset.
6. **Resending the verification link** (decided by Agustín):
   - with a session (the app banner), `POST /auth/resend-verification {email}` as before,
     only for the session's own email; without a session, or with another account's
     email, the same answer and nothing is sent;
   - without a session, `POST /auth/resend-verification-link {token}` with the EXPIRED
     link of an unverified account, as proof of holding the mailbox. Any other token, or
     a still valid one, gets the same answer and nothing is sent. 3 per hour per token
     and network. Nobody can trigger the email with someone else's address, nor void
     their link;
   - the new link is saved only after the email leaves: if sending fails, the previous
     link stays valid.
7. **The public link routes work without a session**: `POST /auth/validate-reset-token`
   and `POST /auth/resend-verification-link` are exempt from CSRF, like
   `forgot-password`. The resend by email needs a session, so it keeps CSRF.

## Consequences

**Positive:** sign-up and "forgot password" no longer tell whether an email has an
account; a database read no longer gives working links; a reset link lives one hour; a
third party cannot keep the owner without a reset link from another network.

**Negative / accepted risks:**
- **M-1, sign-up and then sign-in tells.** Unverified accounts can sign in. After
  registering an email, signing in with the password just chosen succeeds only if the
  sign-up created the account; for an existing one it fails. Accepted (decided by
  Agustín): closing it means not letting unverified accounts sign in, a product change.
  It costs a sign-up per guess, within the sign-up limit, and in B2/B3 notifies the owner.
- **M-2, the daily reset quota.** An attacker can spend an account's 10 reset emails of
  the day from several networks; the owner then gets none until 24 hours pass, or until
  they sign in or reset (which resets the quota). Accepted as the cost of the ceiling.
- **B-1, residual timing.** Accepted, not closed; milliseconds against a bcrypt of
  hundreds, not measured as exploitable:
  - sign-up: a new account is an insert (user and terms acceptance); an existing one is a
    read, and an update only when its notice is due (the branches without a write are
    the fastest);
  - forgot-password: an unknown email is one SELECT; an existing account is a
    transaction with `SELECT ... FOR UPDATE` and an update.
- **B-3, the staggered deploy window.** While 2.56 still serves next to 2.57, it can
  write a plaintext link after this migration ran; that link no longer works with 2.57
  and stays in the table. The plan was for 2.58.0 to repeat the
  `UPDATE ... WHERE token !~ '^[0-9a-f]{64}$'` of both columns; checked read-only in
  production on 11 Nov 2026 there were none left, and 2.57 only writes hashes, so the
  migration was dropped. Also, during that window, links cross between
  versions: a hashed link issued by 2.57 fails on a 2.56 instance and a plaintext one
  issued by 2.56 fails on 2.57. Whoever hits it asks for another link.
- An email sent in the background is lost if the process restarts right then; the user
  can ask again (a lost resend leaves the previous link in place).
- The CSRF exemption of the resend-by-link route lets another site trigger it, but only
  with the expired link, which it does not have.
