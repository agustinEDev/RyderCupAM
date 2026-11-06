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
   When it locks, a new hour starts at zero once the lock ends. A correct password,
   and a Google sign-in, no longer reset it: the owner cannot erase a distributed attack.
4. **The per-network ceiling** (30 failures per minute, any email) moves into the use
   case, so a trusted device is not stopped by an attacker on the same network.
5. **Google sign-in is never stopped by the password brakes**: Google proves who it is,
   and a Google-only account has no right password to defend itself with.
6. **Email to the owner** when a network is locked for their account, or the backstop
   trips: one per failure (the backstop first).
   - Only to a confirmed email. At most one per hour per account, reserved with the
     user row locked before sending, and at most 20 per hour app-wide, to protect the
     mail quota that verification and password reset share. In the background.
   - It says the country, that they can still sign in from their devices, and links
     to changing the password.
7. **Same answers for an unknown email:** the same 401, 423 and 429, the same bcrypt
   (BE #281) and the same one device lookup. A locked origin is refused before bcrypt.
8. **Admin unlock** (admins only since 2.50.1) clears the backstop and every
   per-network lock of that account, and goes to the security log.

## Brute-force bounds

| Attacker | Guesses against one account |
|---|---|
| One network | 10 per 30 min (5 per minute until then) |
| Many networks | 50 per hour in total, then only trusted devices for 30 min |
| A stolen trusted-device cookie | 10 per 30 min, then it counts as its network |

## Consequences

**Positive:**
- Failed logins from another network cannot keep the owner out (A04/A07), also on a
  club's shared wifi with the attacker inside, if the owner signs in from their device.

**Negative / residual risk:**
- **The per-network state lives in memory** (capped at 50,000 pairs per table, old
  ones first out), like the other limits. One process; a restart resets it (at most
  another 10 guesses per network). Several instances would need a shared store.
- **Without the real IP** (no Cloudflare secret), every request is one network. A
  missing `ENVIRONMENT` no longer lets the caller pick its network (`X-Test-Client-ID`).
- **Safari without the device cookie** (cleared, or capped at 7 days) is an unknown
  device: a distributed attack can keep it out for 30 minutes at a time.
- **After 50 distributed failures** an existing email answers 423 from a new network and
  an unknown one 401. It costs 50 guesses and notifies the owner; the old 10-failure
  lock had the same signal.
- Attempts already past the gate when their origin locks still finish their bcrypt.
  The 5 per minute bounds them; each memory operation has no `await`, so it is atomic.
