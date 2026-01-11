# ADR-014: Handicap Management System

**Status**: ✅ Accepted
**Date**: Nov 9, 2025

---

## Context

We need to manage golf handicaps for competitive equity, balanced teams, and adjusted scores.

**Requirements**: Automatic RFEG search, batch update, RFEG/EGA validation (-10.0 to 54.0), complete auditing

---

## Decision

Implement **Handicap as Value Object** + **Domain Events** + **External Service Pattern**.

### Components

**1. Handicap Value Object**
- Range validation: -10.0 to 54.0 (RFEG/EGA rules)
- Immutable, type-safe
- Throws ValueError on invalid range

**2. HandicapUpdatedEvent**
- Tracks: user_id, old/new handicap, updated_at
- Computed property: handicap_delta

**3. User.update_handicap()**
- Updates handicap, emits HandicapUpdatedEvent
- Automatic timestamp update

**4. Use Cases**
- UpdateUserHandicapUseCase: RFEG lookup + optional manual fallback
- UpdateUserHandicapManuallyUseCase: Direct update without RFEG
- UpdateMultipleHandicapsUseCase: Batch with detailed statistics

**5. External Service**
- HandicapService interface (Domain)
- RFEGHandicapService: RFEG web scraping (Infrastructure)
- MockHandicapService: Deterministic tests (Infrastructure)

**6. API Endpoints**
- POST /api/v1/handicaps/update - RFEG + optional fallback
- POST /api/v1/handicaps/update-manual - Direct manual
- POST /api/v1/handicaps/update-multiple - Batch with stats

---

## Rejected Alternatives

**1. Handicap as primitive float**: No validation, allows invalid values (999.9, -100.0)
**2. Service in Application Layer**: Violates Dependency Inversion
**3. Synchronous update on registration**: Blocks registration if RFEG fails, poor UX

---

## Consequences

### Positive
✅ **Type-safe**: Impossible to create `Handicap(999)`
✅ **Auditing**: Events for all changes
✅ **Testable**: MockHandicapService for tests
✅ **Extensible**: Easy to add EGA, USGA
✅ **Non-blocking**: RFEG errors don't affect main flow

### Negative
⚠️ **Complexity**: More files than simple float
⚠️ **Overhead**: Value Object per handicap

**Mitigation**: Investment pays off in maintainability and quality.

---

## Update Points

**1. User Registration** (Optional, non-blocking): Try handicap search in background, doesn't block if fails

**2. Pre-Tournament** (Critical): Batch update of all participants

**3. Manual Admin** (Fallback): Manual update for non-federated players

---

## References

- [ADR-002: Value Objects](./ADR-002-value-objects.md)
- [ADR-007: Domain Events](./ADR-007-domain-events-pattern.md)
- [ADR-013: External Services](./ADR-013-external-services-pattern.md)
- [RFEG Handicaps](https://www.rfegolf.es/Handicaps.aspx)
- [Design Document](../design-document.md) - See Metrics section for implementation details
