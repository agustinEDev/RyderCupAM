# ADR-050: Remove the Unused Domain Events

**Status:** Accepted (replaces ADR-007, removed)
**Date:** November 17, 2026
**Context:** Architecture - DDD, code quality plan (re-audit r2, finding F-03)
**Author:** Agustín Estévez

---

## Context

ADR-007 adopted domain events: entities record what happened (`_add_domain_event`) and a
bus publishes them after the transaction. Only the first half was ever built. Ten
entities recorded events in 66 places, but nothing read them: no use case, repository or
Unit of Work pulled or published them, and `EventBus` / `InMemoryEventBus` had no
subscribers. Meanwhile every real side effect (activity feed, competition notices,
emails, security log) was written as an explicit call from the use case.

The result misled readers into looking for event handlers that did not exist, kept
about 7,000 lines of code and tests alive, and made two password flows run a query whose
only purpose was to fill an event.

## Decision

1. **Remove the mechanism.** Event lists and emissions leave the entities, together with
   the module event packages, `EventBus`, `EventHandler`, `InMemoryEventBus`, the
   SQLAlchemy load listeners that only initialised the list, the methods that only
   recorded an event (`User.record_login`, `record_logout`, `record_google_unlinked`), the
   parameters that only fed events and the password-history count.
2. **Side effects stay explicit.** A use case that must trigger something calls the port
   that does it (notices publisher, mailer, security logger), as it already did.
3. **Security audit events stay.** `DomainEvent` remains only as the base of
   `src/shared/domain/events/security_events.py`, which the security logger writes.

## Consequences

- Behaviour is unchanged: nothing consumed the removed events. The one visible difference
  is that logout no longer rewrites the user row, which nothing changed anyway.
- Readers find the side effects where they happen, in the use case.
- If an event-driven flow is ever needed, it must come with its dispatcher and its first
  consumer in the same change, and a new ADR.
- Done in two PRs (user, social, golf course; then competition and quick match), because
  of the review tool's 100-file limit.
