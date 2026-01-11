# ADR-013: External Services Pattern

**Status**: ✅ Accepted
**Date**: Nov 9, 2025

---

## Context

We need to integrate the **Royal Spanish Golf Federation (RFEG)** to obtain official handicaps. The service is external, with no control over its availability.

**Requirements**:
- Maintain Clean Architecture (do not contaminate domain)
- Testable without external dependencies
- Flexible to change/add providers
- Robust error handling
- Non-blocking if it fails

**RFEG Characteristics**:
- URL: `https://www.rfegolf.es`
- Method: Web scraping (no public API)
- Auth: Bearer token extracted from HTML
- Complexity: 2 HTTP calls (token + search)
- Reliability: No guaranteed SLA

---

## Decision

**Domain Service with Interface** (Domain) + **Concrete Implementations** (Infrastructure).

### Implementation

**1. Interface in Domain**
```python
class HandicapService(ABC):
    @abstractmethod
    async def search_handicap(self, full_name: str) -> float?
```

**2. Real Implementation (Infrastructure)**
- RFEGHandicapService: Web scraping from RFEG
- Error handling: TimeoutException, HandicapServiceError
- Robustness: Graceful degradation on failures

**3. Mock for Tests**
- MockHandicapService: Configurable test data
- Deterministic testing without network calls

**4. Usage in Use Cases**
- Use Cases depend on HandicapService interface
- Dependency injection provides implementation
- Testable with mocks, extensible with new providers

**5. Dependency Injection**
```python
def get_handicap_service() -> HandicapService:
    return RFEGHandicapService(timeout=10)  # Production
    # return MockHandicapService()  # Tests
```

---

## Rejected Alternatives

**1. Direct Call in Use Case**: Couples logic, not testable
**2. Interface in Application Layer**: Violates Dependency Inversion
**3. Message Queue (RabbitMQ)**: Unnecessary complexity for monolith

---

## Consequences

### Positive
✅ **Dependency Inversion**: Use Cases depend on abstraction
✅ **Open/Closed**: Easy to extend with new providers
✅ **Testable**: 100% coverage with mocks
✅ **Flexible**: Change implementation without touching use cases
✅ **Maintainable**: RFEG changes isolated in one class

### Negative
⚠️ **More Files**: Interface + impl + mock
⚠️ **Indirection**: Extra level of abstraction

**Mitigation**: Benefits outweigh additional complexity.

---

## Benefits

### 1. Clean Architecture
- Domain defines contract (HandicapService)
- Infrastructure provides implementations
- Application uses abstractions

### 2. Maximum Testability
- Mock service with predefined data
- No network calls in tests
- Deterministic behavior

### 3. Extensibility
- Easy to add: EGAHandicapService, USGAHandicapService
- Easy fallback: Try RFEG → EGA → USGA
- Easy to change without touching use cases

### 4. Error Handling
- HandicapServiceError for failures
- Continue without blocking flow
- Graceful degradation

---

## References

- **Patterns**: Dependency Inversion (SOLID), Strategy Pattern, Adapter Pattern
- [ADR-001: Clean Architecture](./ADR-001-clean-architecture.md)
- [ADR-005: Repository Pattern](./ADR-005-repository-pattern.md)
- [ADR-012: Composition Root](./ADR-012-composition-root.md)
- [ADR-014: Handicap System](./ADR-014-handicap-management-system.md)
- [Design Document](../design-document.md) - See Metrics section for implemented external services
