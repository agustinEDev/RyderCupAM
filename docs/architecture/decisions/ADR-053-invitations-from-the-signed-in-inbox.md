# ADR-053: Invitations Are Answered from the Signed-in Player's Inbox

**Status:** Accepted
**Date:** November 17, 2026
**Context:** Competition module; Security - OWASP A01, A07
**Author:** Agustín Estévez
**Replaces:** ADR-033 (invitation token security), removed on November 17, 2026

---

## Context

ADR-033 planned a secure token in each invitation link, checked by the backend, and a
scheduled job to expire invitations. Neither was built: the `invitations` table has no
token column and there is no job scheduler for them. Invitations work from the player's
own inbox, and the rules around them grew with the security audits. ADR-033 no longer
described the code, so it was deleted.

## Decision

1. **Only the organiser invites**, by user or by email. Players are not added by hand
   (decided on 15 November 2026). Sending is capped at `min(max_players, 100)` per hour
   per organiser (`MAX_INVITATIONS_PER_HOUR`), and the message cannot contain links
   (SB-05).
2. **No token in the link.** The email points to `/player/invitations`; the player
   answers there, signed in. An invitation sent to an email is tied to an account only
   when that account has verified the address; otherwise it is answered after verifying.
   Someone else's invitation answers 404, without saying its state.
3. **Accepting enrols the player directly.** With enrolments closed, a pending invitation
   waits until the organiser reopens; a waiting one can be declined, not accepted.
4. **Seven days to answer** (`INVITATION_EXPIRATION_DAYS`). Expiry is checked when the
   invitation is read or answered, not by a scheduled job.

## Consequences

- A forwarded email gives nothing to whoever receives it: the inbox needs the session.
- No token to store, hash, rotate or leak.
- Expired invitations stay pending in the table until something reads them.
