# ADR-001: Clean Architecture Adoption

**Date**: October 31, 2025
**Status**: Accepted
**Deciders**: Development Team

## Context and Problem

We need to establish a scalable and maintainable architecture for the Ryder Cup tournament management system. The system must be:

- Easy to unit test
- Independent of external frameworks
- Independent of the database
- Independent of the user interface
- Scalable as the project grows

## Options Considered

1. **Traditional Layered Architecture**: Controller → Service → Repository
2. **Clean Architecture**: Separation of concerns with dependency inversion
3. **Hexagonal Architecture**: Ports and adapters
4. **Simple MVC Architecture**: Basic Model-View-Controller

## Decision

**We adopt Clean Architecture** with the following layer structure:

```
src/modules/{domain}/
├── domain/                 # Domain Layer (independent)
│   ├── entities/           # Business entities
│   ├── value_objects/      # Immutable Value Objects
│   └── repositories/       # Repository interfaces
├── application/            # Application Layer
│   ├── use_cases/          # Use cases
│   └── services/           # Application services
└── infrastructure/         # Infrastructure Layer
    ├── repositories/       # Concrete implementations
    ├── adapters/           # External adapters
    └── config/             # Configuration
```

## Justification

### Advantages of Clean Architecture:

1. **Superior Testability**
   - Each layer can be tested independently
   - Easy creation of mocks for external dependencies
   - Fast and reliable unit tests

2. **Dependency Inversion**
   - Domain doesn't depend on infrastructure
   - Easy to swap implementations (DB, external APIs)
   - Complies with SOLID principle (Dependency Inversion)

3. **Maintainability**
   - Clear separation of concerns
   - Infrastructure changes don't affect business logic
   - Cleaner and more understandable code

4. **Scalability**
   - Structure ready for multiple modules
   - Easy to add new features
   - Enables parallel team work

### Specific Implementation:

- **Web Framework**: FastAPI (infrastructure layer)
- **Testing**: pytest with organization by layers
- **Modules**: Separated by business domain (user, team, tournament)

## Consequences

### Positive:
- ✅ Higher code quality
- ✅ Faster and more reliable tests
- ✅ Facilitates future technology migrations
- ✅ Clearer onboarding for new developers

### Negative:
- ❌ Higher initial complexity
- ❌ More files and structure
- ❌ Learning curve for the team
- ❌ May be over-engineering for very simple projects

### Mitigated Risks:
- **Complexity**: Detailed documentation and clear examples
- **Over-engineering**: Gradual implementation, starting simple
- **Learning curve**: Step-by-step guided development

## Validation

The decision is considered successful if:
- [ ] Unit tests execute in < 2 seconds
- [x] Domain logic independent of frameworks (✅ Implemented)
- [x] Easy to add new use cases (✅ Demonstrated)
- [x] DB changes don't require entity modifications (✅ Architecture ready)

## References

- [Clean Architecture by Robert Martin](https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html)
- [Implementing Clean Architecture in Python](https://github.com/cosmicpython/book)
- [FastAPI Best Practices](https://fastapi.tiangolo.com/tutorial/bigger-applications/)

## Implementation Notes

### Already Implemented (Oct 31, 2025):
- ✅ Folder structure established
- ✅ User entity in domain layer
- ✅ Value Objects (UserId, Email, Password)
- ✅ Tests organized by layers
- ✅ 80 tests running in 0.54s

### Next:
- 🔄 Repository interfaces (domain)
- ⏳ Concrete implementations (infrastructure)
- ⏳ Use cases (application)