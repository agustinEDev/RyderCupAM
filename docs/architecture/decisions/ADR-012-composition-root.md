# ADR-012: Composition Root Pattern for Dependency Injection

**Date**: 2025-11-05  
**Status**: Accepted

## Context

As we implement Use Cases, the need arises to "build them" and provide them with their dependencies (such as the `UnitOfWork`). The presentation layer (API with FastAPI) needs an instance of a use case to execute it, but it should not be responsible for its construction.

If the API endpoint manually creates the `UnitOfWork` and the `UseCase`, it would be tightly coupled to the implementation details of the persistence layer, violating Clean Architecture.

## Decision

We have decided to adopt the **Composition Root** pattern. This will be the only place in the application where the dependency graph of objects will be composed.

The Composition Root will be a very thin layer of code, located near the application's entry point (`main.py`), that will act as a "factory" or "assembler".

### Implementation with FastAPI:

We will use FastAPI's **Dependency Injection** system (`Depends`) to implement this pattern elegantly.

1.  **We will create "providers"**: Simple functions that know how to build a dependency. For example, a `get_db_session` function that creates and manages a SQLAlchemy session.
2.  **We will compose dependencies in a chain**:
    -   A `get_uow` function will depend on `get_db_session` to create an instance of `SQLAlchemyUnitOfWork`.
    -   A `get_register_user_use_case` function will depend on `get_uow` to create an instance of `RegisterUserUseCase`.
3.  **We will inject the Use Case into the Endpoint**: The API endpoint will simply declare its need for the use case through `Depends`:

    ```python
    @router.post("/register")
    async def register_user(
        use_case: RegisterUserUseCase = Depends(get_register_user_use_case)
    ):
        # ... use the use_case ...
    ```

## Consequences

### Positive:

-   **Maximum Decoupling**: The API layer is completely decoupled from the creation of its dependencies. It only knows the interface of the use case.
-   **Centralized Configuration**: All the application's "wiring" logic resides in a single place. If we need to change an implementation (e.g., from `SQLAlchemyUnitOfWork` to another), we only change it in the Composition Root.
-   **Facilitates Integration Testing**: FastAPI allows overriding dependencies during tests (`app.dependency_overrides`), which greatly facilitates replacing real dependencies with test doubles.
-   **Clean Code in the API**: Endpoints remain thin and focused on their task of handling the HTTP request, delegating all the work to the injected use case.

### Negative:

-   **Learning Curve**: The concept of dependency injection may be new to some developers, but FastAPI's system makes it very intuitive.
-   **Dependency Management**: As the application grows, the Composition Root can become more complex, but there are more advanced dependency injection libraries available if needed.
