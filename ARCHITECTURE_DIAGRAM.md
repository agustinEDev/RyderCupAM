# RyderCupAM - Architecture Diagram

## Clean Architecture Layers (Onion Model)

```
┌─────────────────────────────────────────────────────────────────┐
│                     PRESENTATION LAYER                          │
│              FastAPI Routes / HTTP Handlers                      │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────┐  │
│  │  auth_routes.py  │  │ handicap_routes  │  │ user_routes  │  │
│  └──────────────────┘  └──────────────────┘  └──────────────┘  │
└──────────────────────────────┬──────────────────────────────────┘
           ↑                    ↓
┌──────────────────────────────────────────────────────────────────┐
│                   APPLICATION LAYER                              │
│              Use Cases & Orchestration                           │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  RegisterUserUseCase    LoginUserUseCase    VerifyEmail   │  │
│  │  UpdateProfileUseCase   UpdateSecurityUseCase             │  │
│  │  FindUserUseCase        LogoutUserUseCase                 │  │
│  │  UpdateHandicapUseCase  ResendVerificationEmailUseCase    │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ DTOs (Request/Response Models) + Event Handlers          │   │
│  └──────────────────────────────────────────────────────────┘   │
└──────────────────────────────┬──────────────────────────────────┘
           ↑                    ↓
┌──────────────────────────────────────────────────────────────────┐
│                    DOMAIN LAYER (Core)                           │
│              Pure Business Logic - NO Dependencies               │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │ ENTITY: User (Aggregate Root)                              │  │
│  │  ├─ id: UserId                                             │  │
│  │  ├─ email: Email                                           │  │
│  │  ├─ password: Password                                     │  │
│  │  ├─ handicap: Handicap                                     │  │
│  │  ├─ Methods: create(), verify_password()                   │  │
│  │  ├─ Event Methods: record_login(), record_logout()         │  │
│  │  └─ Domain Events: _domain_events: List[DomainEvent]       │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                   │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │ VALUE OBJECTS (Immutable, Validated)                       │  │
│  │  ├─ UserId(frozen dataclass)                               │  │
│  │  ├─ Email(frozen dataclass) - validated, normalized        │  │
│  │  ├─ Password(frozen dataclass) - bcrypt hashed             │  │
│  │  └─ Handicap(frozen dataclass) - range [-10.0, 54.0]      │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                   │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │ DOMAIN EVENTS                                              │  │
│  │  ├─ UserRegisteredEvent                                    │  │
│  │  ├─ UserLoggedInEvent / UserLoggedOutEvent                 │  │
│  │  ├─ EmailVerifiedEvent                                     │  │
│  │  ├─ UserProfileUpdatedEvent                                │  │
│  │  ├─ UserEmailChangedEvent                                  │  │
│  │  ├─ UserPasswordChangedEvent                               │  │
│  │  └─ HandicapUpdatedEvent                                   │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                   │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │ REPOSITORY INTERFACES (Abstraction Boundaries)             │  │
│  │  ├─ UserRepositoryInterface (CRUD operations)              │  │
│  │  └─ UserUnitOfWorkInterface (Transaction management)       │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                   │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │ DOMAIN SERVICES                                            │  │
│  │  ├─ UserFinder - complex user queries                      │  │
│  │  └─ HandicapService - handicap operations (interface)      │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                   │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │ DOMAIN EXCEPTIONS                                          │  │
│  │  ├─ UserAlreadyExistsError                                 │  │
│  │  ├─ InvalidEmailError                                      │  │
│  │  ├─ InvalidPasswordError                                   │  │
│  │  └─ HandicapServiceError                                   │  │
│  └────────────────────────────────────────────────────────────┘  │
└──────────────────────────────┬──────────────────────────────────┘
           ↑                    ↓
┌──────────────────────────────────────────────────────────────────┐
│              INFRASTRUCTURE LAYER                                │
│          Implementations of Domain Abstractions                  │
│                                                                   │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │ PERSISTENCE (Implements Domain Interfaces)                 │  │
│  │  ├─ SQLAlchemyUserRepository                               │  │
│  │  │   └─ Uses SQLAlchemy ORM + asyncpg driver              │  │
│  │  ├─ SQLAlchemyUnitOfWork                                   │  │
│  │  │   └─ Context manager for transactions                   │  │
│  │  └─ InMemoryUserRepository (for testing)                   │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                   │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │ EXTERNAL SERVICES (Adapters)                               │  │
│  │  ├─ RFEGHandicapService - Golf federation integration      │  │
│  │  ├─ MockHandicapService - Testing implementation           │  │
│  │  ├─ MailgunEmailService - Email delivery                   │  │
│  │  └─ JWTHandler - Token generation/verification             │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                   │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │ SHARED INFRASTRUCTURE                                      │  │
│  │  ├─ EventBus / InMemoryEventBus                            │  │
│  │  ├─ Database configuration (SQLAlchemy setup)              │  │
│  │  ├─ Settings (environment management)                      │  │
│  │  └─ Logging configuration                                  │  │
│  └────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
```

---

## Dependency Flow (Inversion of Control)

```
┌─ DEPENDS ON →
│
HTTP Request (FastAPI)
    ↓
API Route Handler
    ↓
Use Case (via Dependency Injection)
    ├─→ Domain Entity ← (no dependencies, pure logic)
    ├─→ Value Objects ← (no dependencies, immutable)
    ├─→ Repository Interface
    │   └─→ SQLAlchemy Repository Implementation
    │       └─→ Database (PostgreSQL)
    ├─→ Domain Service
    │   └─→ External Service (RFEG API, Mailgun API)
    └─→ Unit of Work
        └─→ Session Management & Transactions
```

**KEY PRINCIPLE**: Dependencies point inward toward the domain. The domain depends on nothing.

---

## Module Structure (Bounded Context)

```
src/modules/user/
│
├── domain/                           [DOMAIN LAYER]
│   ├── entities/
│   │   └── user.py                   User Aggregate Root
│   │
│   ├── value_objects/
│   │   ├── user_id.py               UUID wrapper
│   │   ├── email.py                 Validated email
│   │   ├── password.py              Hashed password
│   │   └── handicap.py              Golf handicap (range validation)
│   │
│   ├── events/
│   │   ├── user_registered_event.py
│   │   ├── user_logged_in_event.py
│   │   ├── user_logged_out_event.py
│   │   ├── email_verified_event.py
│   │   ├── user_profile_updated_event.py
│   │   ├── user_email_changed_event.py
│   │   ├── user_password_changed_event.py
│   │   └── handicap_updated_event.py
│   │
│   ├── repositories/
│   │   ├── user_repository_interface.py       [ABSTRACTION]
│   │   └── user_unit_of_work_interface.py     [ABSTRACTION]
│   │
│   ├── services/
│   │   ├── handicap_service.py                [INTERFACE]
│   │   └── user_finder.py                     Domain Service
│   │
│   └── errors/
│       ├── user_errors.py
│       └── handicap_errors.py
│
│
├── application/                      [APPLICATION LAYER]
│   ├── use_cases/
│   │   ├── register_user_use_case.py
│   │   ├── login_user_use_case.py
│   │   ├── logout_user_use_case.py
│   │   ├── verify_email_use_case.py
│   │   ├── resend_verification_email_use_case.py
│   │   ├── find_user_use_case.py
│   │   ├── update_profile_use_case.py
│   │   ├── update_security_use_case.py
│   │   ├── update_user_handicap_use_case.py
│   │   ├── update_user_handicap_manually_use_case.py
│   │   └── update_multiple_handicaps_use_case.py
│   │
│   ├── dto/
│   │   └── user_dto.py                 All Request/Response models
│   │
│   └── handlers/
│       └── user_registered_event_handler.py
│
│
└── infrastructure/                   [INFRASTRUCTURE LAYER]
    ├── api/v1/
    │   ├── auth_routes.py             Endpoints: register, login, logout, verify
    │   ├── user_routes.py             Endpoints: search users
    │   └── handicap_routes.py          Endpoints: update handicaps
    │
    ├── persistence/
    │   ├── sqlalchemy/
    │   │   ├── mappers.py             SQLAlchemy mappers
    │   │   ├── user_repository.py      [IMPLEMENTATION]
    │   │   └── unit_of_work.py         [IMPLEMENTATION]
    │   │
    │   └── in_memory/
    │       ├── in_memory_user_repository.py    [TEST IMPL]
    │       └── in_memory_unit_of_work.py       [TEST IMPL]
    │
    ├── external/
    │   ├── rfeg_handicap_service.py    Real RFEG integration
    │   └── mock_handicap_service.py    Mock for testing
    │
    └── security/
        └── jwt_handler.py              Token verification
```

---

## Data Flow for User Registration

```
POST /api/v1/auth/register
│
└─→ API Route Handler (auth_routes.py)
    │
    └─→ Dependency Injection: get_register_user_use_case()
        │
        └─→ RegisterUserUseCase.execute(RegisterUserRequestDTO)
            │
            ├─→ 1. Validate email (via Email VO)
            │      └─→ email_validator library
            │
            ├─→ 2. Check if email already exists
            │      └─→ UserFinder (Domain Service)
            │          └─→ UserRepository.find_by_email() (interface call)
            │              └─→ SQLAlchemyUserRepository (implementation)
            │                  └─→ Database query
            │
            ├─→ 3. Create User aggregate with User.create() factory
            │      ├─→ Create UserId (UUID generation)
            │      ├─→ Create Email VO (validated)
            │      ├─→ Create Password VO (bcrypt hashing)
            │      └─→ Emit UserRegisteredEvent
            │
            ├─→ 4. Attempt to fetch initial handicap
            │      └─→ HandicapService.search_handicap()
            │          └─→ RFEGHandicapService (implementation)
            │              └─→ HTTP request to RFEG API
            │
            ├─→ 5. Save user via Unit of Work
            │      └─→ UnitOfWork context manager
            │          ├─→ await repository.save(user)
            │          └─→ async with uow: ... (auto-commit/rollback)
            │
            ├─→ 6. Send verification email
            │      └─→ MailgunEmailService
            │          └─→ HTTP request to Mailgun API
            │
            └─→ 7. Return UserResponseDTO
                └─→ DTO.model_validate(user) conversion
```

---

## Event Flow

```
1. User Registered
   ├─→ UserRegisteredEvent emitted by User.create()
   ├─→ Stored in User._domain_events list
   └─→ Handler: UserRegisteredEventHandler
       ├─→ Send welcome email
       ├─→ Log registration audit
       └─→ Notify external systems

2. User Logged In
   ├─→ UserLoggedInEvent emitted by record_login()
   └─→ Handler: [Future - to be implemented]
       └─→ Update last login timestamp
           Log session start

3. User Logged Out
   ├─→ UserLoggedOutEvent emitted by record_logout()
   └─→ Handler: [Future]
       └─→ Invalidate JWT token
           Log session end

4. Email Verified
   ├─→ EmailVerifiedEvent emitted by verify_email()
   └─→ Handler: [Future]
       └─→ Send welcome message
           Enable full access

5. Handicap Updated
   ├─→ HandicapUpdatedEvent emitted by update_handicap()
   └─→ Handler: [Future]
       └─→ Log handicap change
           Notify team members
```

---

## Test Architecture

```
Unit Tests (360 tests)
├── Domain Tests
│   ├── entities/
│   │   └── test_user.py (creation, methods, events)
│   ├── value_objects/
│   │   ├── test_email.py (validation)
│   │   ├── test_password.py (hashing)
│   │   └── test_handicap.py (range validation)
│   ├── events/
│   │   └── test_user_events.py (event data)
│   └── repositories/
│       └── test_user_repository_interface.py (spec)
│
├── Application Tests
│   └── use_cases/
│       ├── test_register_user.py (with mocked repo)
│       ├── test_login_user_use_case.py
│       ├── test_verify_email_use_case.py
│       └── ... (other use cases)
│
└── Infrastructure Tests
    └── external/
        ├── test_rfeg_service.py (mocked HTTP)
        └── test_mailgun_service.py (mocked HTTP)

Integration Tests (60 tests)
├── API Tests (httpx AsyncClient)
│   ├── test_register_endpoint.py (full flow)
│   ├── test_login_endpoint.py
│   └── test_verify_email_endpoint.py
│
├── Persistence Tests (real PostgreSQL)
│   └── sqlalchemy/
│       └── test_user_repository.py (CRUD operations)
│
└── Event Tests
    └── test_domain_event_flow.py (event publishing)
```

**Test Database Isolation**:
- Each worker: `test_db_gw0`, `test_db_gw1`, etc.
- Schema created before test
- Schema destroyed after test
- Zero interference with pytest-xdist parallelization

---

## Configuration & Dependency Injection

```
Environment Variables (top priority)
    ↓
settings.py (Settings dataclass)
    ├── SECRET_KEY
    ├── DATABASE_URL
    ├── MAILGUN_API_KEY
    └── ... (14+ settings)
    
Composition Root (dependencies.py)
    ├── get_db_session() 
    │   └─→ async_session_maker (FastAPI dependency)
    │
    ├── get_uow()
    │   └─→ SQLAlchemyUnitOfWork
    │
    ├── get_register_user_use_case()
    │   ├─→ depends on: get_uow()
    │   ├─→ depends on: RFEGHandicapService
    │   └─→ depends on: email_service
    │
    └── ... (other use case factories)

FastAPI Endpoints
    └─→ @router.post("/register", route_handler)
        └─→ async def register_user(
              request: RegisterUserRequestDTO,
              use_case: RegisterUserUseCase = Depends(get_register_user_use_case)
            )
```

---

## Summary Metrics

| Aspect | Count | Notes |
|--------|-------|-------|
| **Domain Events** | 8 | UserRegistered, Login, Logout, EmailVerified, etc. |
| **Use Cases** | 10 | Complete user management lifecycle |
| **Value Objects** | 4 | UserId, Email, Password, Handicap |
| **API Endpoints** | 8 | Auth, handicap, user search |
| **Tests** | 420 | 360 unit + 60 integration, 100% passing |
| **Test Coverage** | >90% | Business logic fully tested |
| **Dependencies** | 15+ | FastAPI, SQLAlchemy, pytest, etc. |
| **Async Operations** | 100% | All I/O is non-blocking |
| **Database Migrations** | Alembic | Version-controlled schema changes |

---

## Key Takeaways

✅ **Clean Architecture**: Layered, decoupled, testable
✅ **Domain-Driven Design**: Business logic at the center
✅ **Async-First**: Non-blocking I/O throughout
✅ **Repository Pattern**: Dual implementations (SQL + In-Memory)
✅ **Dependency Inversion**: Domain depends on nothing
✅ **Event-Driven**: Foundation for microservices
✅ **Comprehensive Testing**: Unit + Integration, isolated DB, parallel execution
✅ **Production-Ready**: Error handling, logging, security, monitoring

