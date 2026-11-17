# ADR-007: Domain Events Pattern

**Status**: ✅ Accepted
**Date**: Nov 1, 2025

---

## Context

We need to handle side effects and communication between modules without coupling use cases.

**Problems**:
- Coupled use cases (main logic + side effects)
- SRP violation
- Complex tests with multiple mocks
- Difficult to extend
- Lack of auditing

**System Events**: UserRegisteredEvent, HandicapUpdatedEvent, TournamentCreatedEvent, MatchCompletedEvent

---

## Decision

**Domain Events Pattern** with in-memory event bus.

### Components

**1. DomainEvent Base**
- Fields: event_id, occurred_on, aggregate_id, event_version
- Immutable frozen dataclass

**2. Specific Events**
- UserRegisteredEvent: user_id, email, full_name
- HandicapUpdatedEvent: user_id, old/new handicap, handicap_delta property

**3. Event Collection in Entities**
- Entities maintain _domain_events list
- Events added on create/update operations
- Example: User.create() generates UserRegisteredEvent

**4. Event Bus + Handlers**
- EventBus: publish(), subscribe() methods
- EventHandler: handle() method
- Async support for all operations

**5. Integration with Unit of Work**
- Use cases collect domain events from entities
- Events published after successful commit
- Ensures transactional consistency

---

## Rejected Alternatives

**1. Direct Callbacks**: Coupling between layers
**2. Traditional Observer Pattern**: Violates Clean Architecture
**3. Message Queues (RabbitMQ, Redis)**: Unnecessary complexity for monolith

---

## Consequences

### Positive
✅ **Single Responsibility**: Use cases focused on business logic
✅ **Decoupling**: Independent handlers
✅ **Testability**: Isolated tests
✅ **Extensibility**: New handler = new functionality
✅ **Auditing**: Complete traceability
✅ **Performance**: In-memory events, no network
✅ **Transactionality**: Events only after commit

### Negative
⚠️ **Complexity**: More abstractions
⚠️ **Debugging**: Indirect flow
⚠️ **Error handling**: Handling failures in handlers

---

## Implementation

**Components**:
- DomainEvent base class (Domain Layer)
- EventHandler interface (Application Layer)
- EventBus interface + InMemoryEventBus (Shared)
- Domain-specific events (UserRegisteredEvent, HandicapUpdatedEvent)
- Specific handlers (Application)

---

## References

- [ADR-001: Clean Architecture](./ADR-001-clean-architecture.md)
- [ADR-002: Value Objects](./ADR-002-value-objects.md)
- [ADR-005: Repository Pattern](./ADR-005-repository-pattern.md)
- [ADR-006: Unit of Work](./ADR-006-unit-of-work-pattern.md)
- [ADR-008: Logging System](./ADR-008-logging-system.md)
- [ADR-014: Handicap System](./ADR-014-handicap-management-system.md)
- [Design Document](../design-document.md) - See Metrics section for implemented events
