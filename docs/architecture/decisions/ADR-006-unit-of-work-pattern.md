# ADR-006: Unit of Work Pattern for Transaction Management

## Status
**ACCEPTED** - November 1, 2025

## Context

With the Repository pattern implemented, we need to coordinate multiple repository operations within atomic transactions. Unit of Work ensures data consistency and complete commit/rollback.

### Identified Problems
1. Complex transactions involving multiple repositories
2. Data consistency ensuring atomicity
3. Manual commit/rollback in each use case
4. Performance optimization of database connections

### Alternatives Considered

1. **Manual transaction management**: In each use case - Rejected (repetitive, error-prone)
2. **Transactions in repositories**: Each repo manages its transaction - Rejected (no atomicity guarantee)
3. **Unit of Work Pattern**: Central transaction coordinator - Accepted (automatic management, atomicity)

## Decision

We implement the **Unit of Work pattern** with async support and context manager for automatic transaction management.

### Interface Architecture

**Base Interface**:
- `__aenter__` / `__aexit__`: Async context manager
- `commit()`, `rollback()`, `flush()`: Transaction management
- `is_active()`: Transaction state

**Module-Specific Interface**:
- UserUnitOfWorkInterface with `users` property
- Future: CompetitionUnitOfWorkInterface, TeamUnitOfWorkInterface

### Implemented Features

**Core Features**:
1. Async Context Manager: Automatic management with `async with`
2. Type Safety: Typed interfaces
3. Module-Specific: Specific UoW per module
4. Exception Handling: Automatic rollback on error

**Evolution (Nov 9, 2025)** - Clean Architecture Enhancement:
5. Fully Automatic Transactions: Context manager handles all commit/rollback
6. Domain Events Publication: Automatic post-commit
7. Zero Transaction Code in Use Cases: Complete separation of concerns
8. Robust Error Handling: Guaranteed rollback

### Usage Pattern

**Current Version (Nov 9, 2025)**:
```python
async def execute_use_case(command: Command, uow: UserUnitOfWorkInterface):
    async with uow:  # Context manager handles EVERYTHING
        user = await User.create(...)
        await uow.users.save(user)
        # NO explicit commit - Clean Architecture compliance
    # Automatic commit on __aexit__ (success) or rollback (exception)
```

## Consequences

### Benefits
- ✅ **Guaranteed atomicity**: All operations successful or none
- ✅ **Automatic management**: Context manager handles commit/rollback
- ✅ **Consistency**: Guaranteed coherent data state
- ✅ **Testability**: Easy to mock for unit tests
- ✅ **Performance**: One connection per transaction
- ✅ **Clean Code**: Readable and maintainable use cases

### Challenges
- ⚠️ **Initial complexity**: Advanced transaction concepts
- ⚠️ **Async complexity**: Proper handling of async context managers
- ⚠️ **Memory management**: Proper resource cleanup

### Technical Impact
- Testing: 18 specific tests for Unit of Work interfaces
- Architecture: Additional transactional coordination layer
- Performance: Database connection optimization

## Implementation Status

**Phase 1 (Nov 1, 2025)**:
- ✅ Base UnitOfWorkInterface with async context manager
- ✅ UserUnitOfWorkInterface specific for user module
- ✅ 18 unit tests verifying interface behavior
- ✅ Full documentation integration

**Phase 2 (Nov 9, 2025)** - Clean Architecture Evolution:
- ✅ SQLAlchemy implementation with PostgreSQL
- ✅ Automatic transaction management
- ✅ Domain Events integration (post-commit)
- ✅ Clean Architecture compliance
- ✅ 360 tests passing (complete validation)
This pattern is fundamental for maintaining data integrity and providing a solid foundation for complex business operations. The async implementation enables scalability in modern web applications.