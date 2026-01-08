# ADR-015: Session Management Strategy - Progressive Implementation

**Status**: ✅ Accepted
**Date**: Nov 9, 2025

---

## Context

We need to define the logout strategy for JWT tokens: **immediate invalidation vs. natural expiration**.

**Alternatives**:
1. **Token Blacklist**: Real immediate invalidation (high complexity)
2. **Client-side Logout**: Token valid until expiration (low complexity) 
3. **Progressive Approach**: Phased implementation

---

## Decision

**Progressive implementation in 2 phases** to balance time-to-market and security.

### Phase 1: Simple Logout (IMPLEMENTED)
- **Approach**: Client deletes token locally
- **Server**: Only auditing with `UserLoggedOutEvent`
- **Limitation**: Token technically valid until expiration (24h)
- **Benefit**: Immediate functional logout, architecture prepared

### Phase 2: Token Blacklist (FUTURE)
- **Approach**: Immediate invalidation with persistent blacklist
- **Components**: `TokenBlacklistService`, middleware update
- **Trigger**: When we have >1000 users or enterprise requirements

---

## Justification

**Why not immediate blacklist?**
- Unnecessary complexity for MVP
- 99% cases covered with Phase 1
- Real validation of needs before over-engineering

**Why progressive implementation?**
- Immediate time-to-market
- Extensible architecture without waste
- Incremental risk mitigation

---

## Consequences

### Positive
- ✅ Immediate functional logout
- ✅ Architecture prepared for evolution
- ✅ Optimal complexity/benefit balance

### Negative  
- ⚠️ Temporary security gap (valid tokens post-logout)
- ⚠️ Requires Phase 2 planning

---

## Migration Criteria to Phase 2

Migrate when **any** is met:
- Reported security incidents
- Demand for "logout all devices"
- Compliance requirements
- +1000 active users

---

## References

- [ADR-007: Domain Events Pattern](./ADR-007-domain-events-pattern.md)
- [ADR-006: Unit of Work Pattern](./ADR-006-unit-of-work-pattern.md)