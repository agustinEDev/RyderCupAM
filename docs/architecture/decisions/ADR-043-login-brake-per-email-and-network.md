# ADR-043: The Login Brake Counts per Email and Network, and a Trusted Device Is Never Locked Out

**Status:** Accepted
**Date:** November 6, 2026
**Context:** Security - OWASP A04, A07, A09
**Author:** Agustín Estévez
**Amends:** ADR-027 (account lockout)

---

## Context

Two brakes against password guessing counted per email only (BE #732):

- **5 attempts per minute per email**, from any network.
- **10 wrong passwords locked the account for 30 minutes**, for everyone.

Anyone who knew a user's email could therefore keep them out, without any
credential: on tournament day, for example, the organiser. Since 2.49 the real client
IP arrives from Cloudflare (ADR-041), and since 2.50 devices are checked by id
(ADR-042). Together they can tell the attacker apart from the owner.

## Decision

1. **Per email and origin.** The origin is the network: the real IP, or its /64 for
   IPv6. With a trusted device, the origin is that device.
   - 5 attempts per minute → 429 for that origin only.
   - 10 failures in 30 minutes → that origin is locked for 30 minutes for that email
     (423). Other networks, and other accounts from the same network, still sign in.
   - A correct password resets that origin's failures, not the other origins'.
2. **A trusted device** is an *active* device of that account in the device cookie.
   - Failures elsewhere never lock it out. It still needs the right password.
   - Its own 10 failures remove that pass for 30 minutes, so a stolen cookie cannot
     guess passwords without a limit.
   - An id from another account, a revoked device or a made-up id gives no pass.
3. **The account backstop** stays in the `users` table. It counts failures from all
   networks: 50 in one hour lock the account for 30 minutes, for unknown devices only.
   A correct password no longer resets it, so the owner signing in cannot erase a
   distributed attack. It ends with its hour.
4. **The per-network ceiling** (30 failures per minute, any email) is unchanged.
5. **Email to the owner** when a network is locked for their account, or the
   backstop trips.
   - Only to a confirmed email, at most one per hour per account, sent in the
     background.
   - It says the country, that they can still sign in from their devices, and links
     to changing the password.
6. **Same answers for an unknown email:** the same 401, 423 and 429, and the same
   bcrypt (BE #281). A locked origin is refused before bcrypt.
7. **Admin unlock** clears the backstop and every per-network lock of that account.

## Brute-force bounds

| Attacker | Guesses against one account |
|---|---|
| One network | 10 per 30 min (5 per minute until then) |
| Many networks | 50 per hour in total, then only trusted devices for 30 min |
| A stolen trusted-device cookie | 10 per 30 min, then it counts as its network |

## Consequences

**Positive:**
- Failed logins from another network cannot keep the owner out (A04/A07).
- At a club's shared wifi with an attacker inside, the owner's device still signs in.

**Negative / residual risk:**
- **The per-network state lives in memory**, like the other limits. The API runs as
  one process. A deploy or restart resets it: an attacker gains at most another 10
  guesses per network. Running several instances would need a shared store.
- **Without the real IP** (no Cloudflare secret), every request is one network:
  behaviour falls back to today's shared counter. Documented in ADR-041.
- **A tripped backstop also stops a Google login from an unknown device**, as the
  account lock always did (`google_login_use_case`).
- Attempts already past the gate when their origin locks still finish their bcrypt.
  The 5 per minute bounds how many can be in flight. Each memory operation has no
  `await`, so it is atomic in the event loop and the 10th failure locks once.
