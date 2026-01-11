# ADR-011: Implementation of the Application Layer with Use Cases

**Date**: 2025-11-05  
**Status**: Accepted

## Context

With the domain layer and the persistence infrastructure layer already established, the application needs an intermediate layer that orchestrates business logic without coupling the API to domain details. This layer must handle user interactions (or from other systems), execute business rules, and coordinate data persistence transactionally.

## Decision

We have decided to implement an explicit **Application Layer**, whose main component will be the **Use Cases**.

Each use case will represent a single action or functionality that the system can perform, such as `RegisterUserUseCase`, `UpdateUserHandicapUseCase`, or `CreateTournamentUseCase`.

### Responsibilities of a Use Case:

1.  **Orchestration**: A use case does not contain business logic itself. Its function is to orchestrate domain objects (Entities, Value Objects, Domain Services) to perform the work.
2.  **Transaction Management**: The use case will control transaction boundaries through the `UnitOfWork` interface. It will initiate the transaction, coordinate operations, and confirm (`commit`) or revert (`rollback`) changes.
3.  **Decoupling**: It will depend only on abstractions (interfaces) defined in the domain layer (e.g., `UserRepositoryInterface`, `UnitOfWorkInterface`), never on concrete implementations.
4.  **Data Contracts (DTOs)**: It will receive input data through a Request DTO and return output data through a Response DTO.

### Example Flow (`RegisterUserUseCase`):

1.  Receives a `RegisterUserRequestDTO`.
2.  Initiates a transaction with `async with uow:`.
3.  Uses a Domain Service (`UserFinder`) to verify if the user already exists.
4.  Calls the factory `User.create()` to create the entity.
5.  Saves the new entity using `uow.users.save(user)`.
6.  Confirms the transaction with `uow.commit()`.
7.  Returns a `UserResponseDTO`.

## Consequences

### Positive:

-   **Single Responsibility Principle (SRP)**: Application logic is clearly separated from domain logic and infrastructure.
-   **Testability**: Use cases are extremely easy to unit test, as they can be injected with fake dependencies (`InMemoryUnitOfWork`).
-   **Reusability**: The same use case logic can be invoked from different entry points (a REST API, a CLI, a queue worker) without changes.
-   **Clarity**: The code becomes very expressive and easy to follow, as each file represents a clear business action.

### Negative:

-   **Verbosity**: It may seem to add more files (DTOs, Use Cases), but this "verbosity" is actually explicit organization that is appreciated as the project grows.

## Patterns in Use Cases

### Consistent Transaction Management
```python
async with self._uow:
    # Domain operations
    user = await self._uow.users.find_by_id(user_id)
    user.update_handicap(new_handicap)

    # Persistence
    await self._uow.users.update(user)

    # Commit (automatically publishes events)
    await self._uow.commit()
```

### Integration with External Services
```python
class UpdateUserHandicapUseCase:
    def __init__(
        self,
        uow: UserUnitOfWorkInterface,
        handicap_service: HandicapService  # ← Abstraction injection
    ):
        self._uow = uow
        self._handicap_service = handicap_service
```

### Error Handling
```python
# Return None for "not found"
if not user:
    return None

# ValueError for business validations
try:
    user.update_handicap(handicap)
except ValueError as e:
    raise  # Handled in the HTTP endpoint
```

## References

- [ADR-001: Clean Architecture](./ADR-001-clean-architecture.md)
- [ADR-006: Unit of Work](./ADR-006-unit-of-work-pattern.md)
- [ADR-007: Domain Events](./ADR-007-domain-events-pattern.md)
- [ADR-012: Composition Root](./ADR-012-composition-root.md)
- [ADR-013: External Services Pattern](./ADR-013-external-services-pattern.md)
- [ADR-014: Handicap Management System](./ADR-014-handicap-management-system.md)
- [Design Document](../design-document.md) - See Metrics section for implemented Use Cases
