# RyderCupAM - Comprehensive Architecture Analysis

## 1. Overall Architecture Pattern

### Primary Pattern: Clean Architecture + Domain-Driven Design (DDD)

The project implements **Clean Architecture** combined with **Domain-Driven Design (DDD)** principles, organized as a **modular monolith** with bounded contexts.

**Architecture Layers:**
- **Domain Layer** - Pure business logic, no external dependencies
- **Application Layer** - Use Cases, orchestration, DTOs
- **Infrastructure Layer** - Database, external services, HTTP APIs
- **Presentation Layer** - FastAPI routes and HTTP contracts

**Key Characteristics:**
- Dependency flows inward toward the domain
- Domain logic is completely isolated from framework/infrastructure concerns
- Testable at each layer independently
- Scalable to multiple bounded contexts

---

## 2. Directory Structure and Organization

### Root Level
```
/home/user/RyderCupAM/
├── src/                          # Source code
├── tests/                         # Test suite (54 test files)
├── alembic/                       # Database migrations
├── docs/                          # Project documentation
├── main.py                        # FastAPI application entry point
├── requirements.txt               # Python dependencies
├── pytest.ini                     # Test configuration
├── docker-compose.yml             # Docker setup
└── Dockerfile                     # Container definition
```

### Source Code Structure (src/)
```
src/
├── config/
│   ├── settings.py               # Environment configuration
│   ├── database.py               # SQLAlchemy async setup
│   └── dependencies.py           # FastAPI dependency injection (Composition Root)
│
├── modules/                       # Bounded contexts
│   └── user/                      # User Management bounded context
│       ├── domain/                # Pure business logic
│       │   ├── entities/          # User aggregate root
│       │   ├── value_objects/     # UserId, Email, Password, Handicap
│       │   ├── events/            # Domain events (8 types)
│       │   ├── repositories/      # Repository interfaces
│       │   ├── services/          # Domain services
│       │   └── errors/            # Custom domain exceptions
│       │
│       ├── application/           # Use case orchestration
│       │   ├── use_cases/         # 10 use case implementations
│       │   ├── dto/               # Request/Response DTOs
│       │   └── handlers/          # Event handlers
│       │
│       └── infrastructure/        # External concerns
│           ├── api/v1/            # FastAPI routes (3 routers)
│           ├── persistence/       # SQLAlchemy repositories
│           ├── external/          # External services (RFEG, Mailgun)
│           ├── security/          # JWT, password hashing
│           └── http/              # HTTP utilities
│
└── shared/                        # Cross-cutting concerns
    ├── domain/
    │   ├── events/                # EventBus interface, DomainEvent base
    │   ├── repositories/          # UnitOfWork interface
    │   ├── errors/                # Shared exceptions
    │   └── value_objects/         # Shared VOs
    │
    └── infrastructure/
        ├── database/              # Database utilities
        ├── email/                 # Email service abstraction
        ├── security/              # JWT handler
        ├── logging/               # Structured logging
        └── http/                  # HTTP utilities
```

### Test Structure (tests/)
```
tests/
├── unit/                          # 360 isolated unit tests (no DB)
│   ├── modules/user/
│   │   ├── domain/                # Entity, VO, Event tests
│   │   ├── application/           # Use case unit tests
│   │   └── infrastructure/        # Repository mocks, external service tests
│   └── shared/domain/             # Event bus, repository interface tests
│
└── integration/                   # 60 integration tests (with DB)
    ├── api/v1/                    # FastAPI endpoint tests
    ├── domain_events/             # Event flow tests
    └── modules/user/
        └── infrastructure/        # Repository SQLAlchemy tests
```

---

## 3. Common Patterns Used

### 3.1 Domain-Driven Design Patterns

**Aggregate Root (Entity)**
- `User` - The primary aggregate in the user module
- Encapsulates business rules and state management
- Manages domain events internally

**Value Objects**
- `UserId` - UUID with domain semantics
- `Email` - Validated, normalized email address
- `Password` - Hashed password with verification
- `Handicap` - Golf handicap with range validation (-10.0 to 54.0)

**Domain Events**
- `UserRegisteredEvent` - When user signs up
- `UserLoggedInEvent` - When user logs in
- `UserLoggedOutEvent` - When user logs out
- `EmailVerifiedEvent` - When email is verified
- `UserProfileUpdatedEvent` - When profile changes
- `UserEmailChangedEvent` - When email changes
- `UserPasswordChangedEvent` - When password changes
- `HandicapUpdatedEvent` - When handicap is updated

**Repository Pattern**
- `UserRepositoryInterface` - Domain abstraction
- `SQLAlchemyUserRepository` - Async SQLAlchemy implementation
- `InMemoryUserRepository` - In-memory testing implementation
- Dual implementations enable testing without database

**Unit of Work Pattern**
- `UserUnitOfWorkInterface` - Transaction management interface
- `SQLAlchemyUnitOfWork` - Async implementation with context manager
- Async context manager (`async with`) for automatic commit/rollback
- Decouples transactional concerns from use cases

**Service Pattern**
- `UserFinder` - Domain service for user queries
- `HandicapService` - Interface for handicap operations
- `RFEGHandicapService` - External RFEG integration
- Encapsulates complex domain logic

### 3.2 Clean Architecture Patterns

**Use Cases / Application Services**
Each use case is a single command orchestrator:

1. **RegisterUserUseCase** - User registration with email verification
2. **LoginUserUseCase** - Authentication with JWT token generation
3. **LogoutUserUseCase** - Session management and audit logging
4. **VerifyEmailUseCase** - Email confirmation with token validation
5. **ResendVerificationEmailUseCase** - Retry email verification
6. **UpdateProfileUseCase** - Name/personal info updates
7. **UpdateSecurityUseCase** - Email/password changes
8. **UpdateUserHandicapUseCase** - RFEG handicap lookup
9. **UpdateUserHandicapManuallyUseCase** - Manual handicap input
10. **UpdateMultipleHandicapsUseCase** - Batch handicap updates

**Data Transfer Objects (DTOs)**
- Separate request/response models for each use case
- Validated with Pydantic v2
- Contain no business logic
- Enable loose coupling between layers

**Dependency Injection**
- FastAPI's dependency injection system for endpoint dependencies
- Composition Root pattern in `dependencies.py`
- Factory functions for creating use case instances
- Database session lifecycle management

### 3.3 Additional Patterns

**Event-Driven Architecture**
- Domain events published from entities
- Event handlers (currently in-memory, extensible)
- Event bus abstraction for decoupling
- Async event processing support

**Hexagonal Architecture (Ports & Adapters)**
- Domain events as ports
- Handlers as adapters
- External services (RFEG, Mailgun) as adapters

**Error Handling**
- Custom domain exceptions with semantic meaning
- Domain-level error handling before persistence
- User-friendly HTTP error responses
- Proper error codes (409 Conflict, 404 Not Found, etc.)

---

## 4. Programming Language and Framework

### Language
- **Python 3.12+** (Modern async/await support)

### Core Framework
- **FastAPI 0.115** - Modern async web framework
  - Automatic OpenAPI documentation
  - Type-safe dependency injection
  - Built-in request/response validation

### Key Dependencies

#### Web & Async
- `uvicorn[standard]` 0.30 - ASGI application server
- `httpx` 0.27 - Async HTTP client for testing

#### Database
- `SQLAlchemy` 2.0 - Modern ORM with async support
- `asyncpg` 0.29 - Async PostgreSQL driver
- `psycopg2-binary` 2.9 - Sync PostgreSQL driver (fallback)
- `alembic` 1.13 - Database migrations
- `greenlet` 3.0 - Lightweight concurrency

#### Security
- `python-jose[cryptography]` 3.4 - JWT token handling
- `bcrypt` 4.2 - Password hashing
- `email-validator` 2.3 - Email validation

#### Data Validation
- `pydantic` (via FastAPI) - Runtime data validation

#### Testing
- `pytest` 8.3 - Testing framework
- `pytest-asyncio` 0.24 - Async test support
- `pytest-xdist` 3.8 - Parallel test execution
- `pytest-json-report` 1.5 - JSON test reporting

#### Configuration
- `python-dotenv` 1.0 - Environment variable management

#### External Services
- `requests` 2.32 - HTTP requests (RFEG, Mailgun APIs)

---

## 5. Dependency Management

### Configuration Loading Hierarchy
1. **Environment Variables** (highest priority)
   - Database URL
   - API keys (JWT, Mailgun)
   - Frontend origins
   - Documentation credentials

2. **Settings Object** (`src/config/settings.py`)
   - Centralized configuration management
   - Default values for development
   - Type-safe configuration access

3. **.env File** (local development only)
   - git-ignored, not in version control
   - Loaded by `python-dotenv`

### Dependency Injection Strategy

**Application Level (FastAPI)**
```python
# Composition Root: src/config/dependencies.py
- get_db_session()              # Database session provider
- get_uow()                      # Unit of work provider
- get_register_user_use_case()   # Use case factories
- get_login_user_use_case()
- get_verify_email_use_case()
- etc.
```

**Database Connections**
- Async session factory: `async_session_maker`
- Per-request session lifecycle
- Automatic cleanup via context manager

**External Services**
- RFEG Handicap Service - Golf federation integration
- Mailgun Email Service - Email delivery
- JWT Handler - Token generation/verification

### Dependency Graph

```
API Endpoint
    ↓
Use Case (via DI)
    ├─→ Domain Entity/Service (no dependencies)
    ├─→ Repository Interface (injected implementation)
    │   └─→ SQLAlchemy (persistence)
    ├─→ Domain Service
    │   └─→ External Service (RFEG, Mailgun)
    └─→ Unit of Work (transaction management)
```

---

## 6. Testing Structure

### Testing Framework: pytest

**Configuration** (`pytest.ini`)
```ini
asyncio_mode = auto              # Auto-run async tests
markers = integration            # Mark integration tests
```

**Test Execution** (`dev_tests.py`)
- Parallel execution with pytest-xdist
- Automatic report generation
- 420 total tests (100% passing, 0 warnings)

### Test Layers

#### Unit Tests (360 tests) - `tests/unit/`
- **Domain Tests** - Entities, Value Objects, Events
  - Business logic validation
  - Event emission verification
  - No external dependencies
  - Execution time: <1s

- **Application Tests** - Use Cases
  - Orchestration logic
  - Error handling
  - DTO transformation
  - Mocked repositories
  - Execution time: <5ms each

- **Infrastructure Tests** - External services
  - RFEG service mocking
  - Email service behavior
  - JWT token generation
  - Isolated from database

#### Integration Tests (60 tests) - `tests/integration/`
- **API Tests** - HTTP endpoints
  - Full request/response flow
  - Status code verification
  - Error responses
  - Uses AsyncClient from httpx
  - Execution time: 50-200ms each

- **Persistence Tests** - SQLAlchemy repository
  - Database operations
  - Query correctness
  - Transaction handling
  - Uses isolated test databases

- **Domain Events Tests** - Event flow
  - Event publishing
  - Handler execution
  - Async event processing

### Test Infrastructure

**Fixtures** (`tests/conftest.py`)
- `client()` - AsyncClient for API tests with isolated test database
- `db_session()` - Raw database session for persistence tests
- `sample_user_data` - Reusable test user data
- `multiple_users_data` - Multiple users for batch testing

**Database Isolation**
- Per-worker test databases: `test_db_gw0`, `test_db_gw1`, etc.
- Schema created before each test
- Database destroyed after each test
- Zero interference between parallel tests

**Test Reports**
- `test_report.json` - Machine-readable results
- `test_summary.md` - Human-readable summary
- `warnings.txt` - Deprecation and issue tracking

### Test Coverage

**Overall**
- 420 tests total
- 100% passing
- 0 warnings
- >90% coverage on business logic

**By Module**
- User Registration: 40+ tests (unit + integration)
- Authentication (Login/Logout): 35+ tests
- Email Verification: 24 tests (100% coverage)
- Handicap Management: 30+ tests
- User Management: 25+ tests
- Domain Events: 20+ tests

---

## 7. Key Architectural Decisions

### 1. Async-First Design
- All database operations are async (`AsyncSession`, `asyncpg`)
- All use cases are coroutines (`async def`)
- Tests are async-compatible (`pytest-asyncio`)
- Enables scalability and non-blocking I/O

### 2. Value Objects for Domain Validation
- Email validation at VO level (not controller)
- Password hashing at VO level
- Handicap range validation at VO level
- Domain rules enforced at creation

### 3. Event-Driven Architecture
- Domain events emitted by entities
- Decoupled handlers for side effects
- Foundation for future microservices
- Audit trail capability

### 4. Repository + Unit of Work Pattern
- Repository interface in domain
- SQLAlchemy implementation in infrastructure
- In-memory implementation for testing
- Testable without database dependency

### 5. DTO Per Use Case
- Independent request/response models
- Validation at boundary
- Loose coupling between layers
- Clear API contracts

### 6. Modular Structure
- User module is self-contained
- Easy to add new bounded contexts
- Shared infrastructure for cross-cutting concerns
- Prepared for future Tournament, Team modules

---

## 8. Scalability & Evolution

### Current Status
- **Phase 1 Complete** - Foundation (authentication, user management)
- **420 tests** - High confidence for refactoring
- **Clean architecture** - Easy to add new features

### Future Extensibility
- **Tournament Module** - Another bounded context
- **Event Handlers** - Currently in-memory, can be extended to RabbitMQ/Kafka
- **CQRS** - Could split read/write models
- **Microservices** - Domain events enable migration
- **WebSockets** - Real-time score updates ready

---

## 9. Code Quality & Standards

**Code Style**
- Type hints throughout (Python 3.12+)
- Docstring documentation
- Black formatting (implied)
- MyPy compatibility

**Error Handling**
- Domain-level validation
- Semantic exceptions (UserAlreadyExistsError)
- Proper HTTP status codes
- Clear error messages

**Logging**
- Structured logging infrastructure
- Factory pattern for logger creation
- Event handlers for audit trails
- Production-ready configuration

**Security**
- Password hashing with bcrypt
- JWT token authentication
- Email verification tokens
- CORS configuration
- API documentation protection (HTTP Basic Auth)

---

## 10. Performance Characteristics

- **Parallel test execution**: 420 tests in ~25 seconds
- **Database**: PostgreSQL 15+ with async driver
- **API Response**: Milliseconds (sub-100ms typical)
- **Scalability**: Supports thousands of concurrent users (ASGI)
- **Memory**: Async enables efficient resource usage

---

## Summary

**RyderCupAM** is a **production-ready** backend API implementing:
✅ Clean Architecture + DDD
✅ Async-first Python (FastAPI + SQLAlchemy)
✅ Comprehensive test coverage (420 tests, 100% passing)
✅ Event-driven design
✅ Repository pattern with dual implementations
✅ Modular structure ready for multiple bounded contexts
✅ Professional error handling and logging
✅ Security best practices

The project demonstrates **enterprise-grade software design** principles while maintaining code clarity and testability.
