# Design Document - Ryder Cup Manager

**v1.13.0** · 8 January 2026 · Phase 2 Complete

---

## Summary

Amateur golf tournament system in Ryder Cup format.

**Stack**: Python 3.11-3.12, FastAPI, PostgreSQL, Clean Architecture + DDD

**Features**:
- ✅ User management + JWT auth
- ✅ Email verification (Mailgun, UUID tokens, bilingual)
- ✅ Handicap system (RFEG integration)
- ✅ Competition Module (Ryder Cup format tournaments)
- ✅ CI/CD Pipeline (GitHub Actions)
- ⏳ Real-time scoring (planned)

---

## Architecture

### Clean Architecture (3 Layers)

```
Infrastructure (FastAPI, SQLAlchemy, RFEG)
    ↓
Application (Use Cases, DTOs, Handlers)
    ↓
Domain (Entities, VOs, Events, Repos)
```

**Rule**: Dependencies point inward.

**Patterns**: Repository, UoW, Domain Events, Value Objects, External Services.

> ADRs: [001](architecture/decisions/ADR-001-clean-architecture.md), [002](architecture/decisions/ADR-002-value-objects.md), [005](architecture/decisions/ADR-005-repository-pattern.md), [006](architecture/decisions/ADR-006-unit-of-work-pattern.md), [007](architecture/decisions/ADR-007-domain-events-pattern.md)

---

## Modules

### User Management

**Domain**:
- Entity: `User`
- VOs: `UserId`, `Email`, `Password`, `Handicap`
- Events: `UserRegistered`, `HandicapUpdated`, `UserLoggedIn`, `UserLoggedOut`, `UserProfileUpdated`, `UserEmailChanged`, `UserPasswordChanged`
- Repos: `UserRepositoryInterface`
- Services: `HandicapService` (interface)
- Email Verification: Fields `email_verified`, `verification_token`, event `EmailVerifiedEvent`

**Application**:
- Use Cases: `RegisterUser`, `LoginUser`, `LogoutUser`, `UpdateProfile`, `UpdateSecurity`, `UpdateHandicap`, `UpdateHandicapManually`, `UpdateMultipleHandicaps`, `FindUser`
- DTOs: Request/Response
- Handlers: `UserRegisteredEventHandler`
- Email Verification: `VerifyEmailUseCase`, integrated in registration

**Infrastructure**:
- Routes: `/auth/*`, `/handicaps/*`, `/users/*`
- Repos: `SQLAlchemyUserRepository`
- External: `RFEGHandicapService`, `MockHandicapService`
- Email Verification: Service `EmailService` (Mailgun), endpoint `/api/v1/auth/verify-email`

**Email Verification**:
- Domain: Fields `email_verified`, `verification_token`, event `EmailVerifiedEvent`
- Application: Use case `VerifyEmailUseCase`, integrated in registration
- Infrastructure: Service `EmailService` (Mailgun), endpoint `/api/v1/auth/verify-email`

> ADRs: [011](architecture/decisions/ADR-011-application-layer-use-cases.md), [013](architecture/decisions/ADR-013-external-services-pattern.md), [014](architecture/decisions/ADR-014-handicap-management-system.md)

### Competition Management ✅

**Domain**:
- Entities: `Competition`, `Enrollment`, `Country`
- VOs: `CompetitionId`, `CompetitionName`, `DateRange`, `Location`, `HandicapSettings`, `EnrollmentId`, `EnrollmentStatus`, `CountryCode`
- Events: `CompetitionCreated`, `CompetitionActivated`, `CompetitionStarted`, `CompetitionCompleted`, `EnrollmentRequested`, `EnrollmentApproved`, `EnrollmentCancelled`, `EnrollmentWithdrawn`
- Repos: `CompetitionRepositoryInterface`, `EnrollmentRepositoryInterface`, `CountryRepositoryInterface`

**Application**:
- Use Cases: 17 use cases (CreateCompetition, RequestEnrollment, HandleEnrollment, etc.)
- DTOs: 19 DTOs (Request/Response pairs)

**Infrastructure**:
- Routes: `/competitions/*`, `/enrollments/*`, `/countries/*`
- Repos: `SQLAlchemyCompetitionRepository`, `SQLAlchemyEnrollmentRepository`, `SQLAlchemyCountryRepository`
- Database: Alembic migrations (competitions, enrollments, countries, country_adjacencies)
- Seed Data: 166 countries + 614 border relations

**Features**:
- Complete tournament management (CRUD + state machine)
- Enrollment system (requests, invitations, approvals)
- Multi-country support (up to 3 adjacent countries)
- Custom handicaps per enrollment
- 20 REST API endpoints

> ADR: [020](architecture/decisions/ADR-020-competition-module-domain-design.md)

---

## Data Models

### User Entity

```python
User:
    id: UserId (UUID)
    email: Email (validated, normalized)
    password: Password (bcrypt, rounds=12)
    first_name: str
    last_name: str
    handicap: float? (-10.0 to 54.0)
    handicap_updated_at: datetime?
    created_at: datetime
    updated_at: datetime
    email_verified: bool
    verification_token: str?
```

**Schema**:
```sql
CREATE TABLE users (
    id UUID PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL,
    first_name VARCHAR(50) NOT NULL,
    last_name VARCHAR(50) NOT NULL,
    handicap FLOAT,
    handicap_updated_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL,
    email_verified BOOLEAN DEFAULT FALSE,
    verification_token VARCHAR(255)
);
CREATE INDEX idx_users_email ON users(email);
```

> ADR: [002](architecture/decisions/ADR-002-value-objects.md), [010](architecture/decisions/ADR-010-alembic-for-database-migrations.md)

---

## Business Flows

### 1. User Registration

```
Client → API → UseCase → User.create() → UoW.save() → commit()
                                            ↓
                                       EventBus → Handlers
```

1. Validate email does not exist
2. `User.create()` generates `UserRegisteredEvent`
3. UoW saves + commits
4. Events published
5. Handlers process (email, audit)

> ADR: [006](architecture/decisions/ADR-006-unit-of-work-pattern.md), [007](architecture/decisions/ADR-007-domain-events-pattern.md)

### 2. Update Handicap (RFEG)

```
API → UseCase → HandicapService.search(name) → RFEG
                      ↓
                user.update_handicap() → HandicapUpdatedEvent
                      ↓
                  UoW.commit()
```

1. Find user
2. Query RFEG with full name
3. Update + emit event
4. Commit publishes event

**Fallback**: If RFEG fails, use `manual_handicap` (optional)

**Error Handling**: If player not found in RFEG and no `manual_handicap`, throw `HandicapNotFoundError` (404)

> ADR: [013](architecture/decisions/ADR-013-external-services-pattern.md), [014](architecture/decisions/ADR-014-handicap-management-system.md)

---

## External Integrations

### RFEG (Royal Spanish Golf Federation)

**Type**: Web scraping (no public API)
**Flow**: Extract token → Search by name → Parse JSON
**Timeout**: 10s
**Errors**: Log + return None

**Implementation**:
- Interface: `HandicapService` (domain)
- Impl: `RFEGHandicapService` (infra)
- Mock: `MockHandicapService` (tests)

> ADR: [013](architecture/decisions/ADR-013-external-services-pattern.md)

---

## Security

### Authentication

**JWT**: HS256, exp 60min, secret in env
**Password**: bcrypt, rounds=12 (prod), rounds=4 (test)

### Validation

1. Pydantic (API): types and formats
2. Value Objects (Domain): business rules
3. Database: constraints (UNIQUE, NOT NULL)

> ADR: [004](architecture/decisions/ADR-004-tech-stack.md)

---

## API Endpoints

### Auth
- `POST /api/v1/auth/register` - User registration
- `POST /api/v1/auth/login` - JWT authentication + UserLoggedInEvent
- `POST /api/v1/auth/logout` - Logout with audit + UserLoggedOutEvent
- `POST /api/v1/auth/verify-email` - Email verification (token via email)

### Handicaps
- `POST /api/v1/handicaps/update` - RFEG lookup + fallback
- `POST /api/v1/handicaps/update-manual` - Direct manual update
- `POST /api/v1/handicaps/update-multiple` - Batch update

### Users
- `GET /api/v1/users/search` - Search by email or name
- `PATCH /api/v1/users/profile` - Update name/surname (no password)
- `PATCH /api/v1/users/security` - Update email/password (with password verification)

> Details: [API.md](API.md)

---

## Testing

**Strategy**: Test Pyramid (89% unit, 11% integration)

```
672 tests (100% passing)
├── Unit: 595+ tests
│   ├── User Module: 308 tests
│   ├── Competition Module: 173 tests
│   ├── Shared: 60 tests
│   └── Other: 54+ tests
└── Integration: 72+ tests
    ├── API: ~60 tests
    └── Domain Events: ~12 tests
```

**Coverage**: >90% in business logic
**Email Verification**: 100% (24 tests across 3 layers)
**Competition Module**: 97.6% (174 comprehensive tests)
**Performance**: ~30s (parallelized with pytest-xdist)

**CI/CD**: Tests run automatically on GitHub Actions (Python 3.11, 3.12)

> ADR: [003](architecture/decisions/ADR-003-testing-strategy.md)

---

## CI/CD Pipeline

**Platform**: GitHub Actions

**Jobs (7 parallel)**:
1. Preparation (Python 3.11/3.12 setup + cache)
2. Unit Tests (matrix Python 3.11, 3.12)
3. Integration Tests (PostgreSQL service container)
4. Security Scan (Gitleaks)
5. Code Quality (Ruff)
6. Type Checking (Mypy)
7. Database Migrations (Alembic validation)

**Execution Time**: ~3 minutes
**Trigger**: Push, Pull Request
**Matrix**: Python 3.11, 3.12

**Configurations**:
- Mypy: Pragmatic configuration for SQLAlchemy imperative mapping
- Gitleaks: Whitelist for false positives in docs
- PostgreSQL: Service container for integration tests
- Cache: pip dependencies

> ADR: [021](architecture/decisions/ADR-021-github-actions-ci-cd-pipeline.md)

---

## ADR References

**Foundation**: [001](architecture/decisions/ADR-001-clean-architecture.md), [004](architecture/decisions/ADR-004-tech-stack.md)

**Patterns**: [002](architecture/decisions/ADR-002-value-objects.md), [005](architecture/decisions/ADR-005-repository-pattern.md), [006](architecture/decisions/ADR-006-unit-of-work-pattern.md), [007](architecture/decisions/ADR-007-domain-events-pattern.md)

**Infrastructure**: [009](architecture/decisions/ADR-009-docker-for-development-environment.md), [010](architecture/decisions/ADR-010-alembic-for-database-migrations.md), [021](architecture/decisions/ADR-021-github-actions-ci-cd-pipeline.md)

**Features**: [011](architecture/decisions/ADR-011-application-layer-use-cases.md), [012](architecture/decisions/ADR-012-composition-root.md), [013](architecture/decisions/ADR-013-external-services-pattern.md), [014](architecture/decisions/ADR-014-handicap-management-system.md), [015](architecture/decisions/ADR-015-session-management-progressive-strategy.md), [020](architecture/decisions/ADR-020-competition-module-domain-design.md)

---

## 📊 Project Metrics

**Last Updated**: 8 January 2026

### Testing

| Metric | Value |
|--------|-------|
| Total tests | 672 (100% passing) |
| Unit tests | 595+ tests |
| Integration tests | 72+ tests |
| Coverage | >90% |
| Email Verification | 100% (24 tests) |
| Competition Module | 97.6% (174 tests) |
| Execution time | ~30s (parallel) |
| CI/CD Pipeline | ~3 min (7 jobs) |

### Module Progress

| Module | Status | Tests | Endpoints |
|--------|--------|-------|-----------|
| User | ✅ Complete + Auth + Email | 308+ | 10 |
| Competition | ✅ Complete + Enrollments | 174 | 20 |
| CI/CD | ✅ GitHub Actions | - | - |
| Real-time Scoring | ⏳ Pending | 0 | 0 |

### Implemented Value Objects (69 tests)

- **UserId** (12 tests) - Unique UUID identifier
- **Email** (14 tests) - Validated and normalized email
- **Password** (23 tests) - Bcrypt hashed password
- **Handicap** (20 tests) - Range -10.0 to 54.0 (RFEG/EGA)

### Implemented Domain Events (59 tests)

- **UserRegisteredEvent** (9 tests) - User registered
- **HandicapUpdatedEvent** (16 tests) - Handicap updated with delta
- **UserLoggedOutEvent** (7 tests) - User logged out (audit)
- **UserLoggedInEvent** (7 tests) - User logged in (complete audit)
- **UserProfileUpdatedEvent** (7 tests) - User profile updated
- **UserEmailChangedEvent** (7 tests) - Email changed
- **UserPasswordChangedEvent** (6 tests) - Password changed

### Implemented Use Cases (68 tests)

**User Module (9 use cases)**:
- `RegisterUserUseCase` (5 tests) - User registration
- `LoginUserUseCase` (5 tests) - JWT authentication + events
- `LogoutUserUseCase` (5 tests) - Logout with complete audit
- `UpdateProfileUseCase` (7 tests) - Update name/surname without password
- `UpdateSecurityUseCase` (9 tests) - Update email/password with verification
- `UpdateUserHandicapUseCase` (10 tests) - Update from RFEG with fallback
- `UpdateUserHandicapManuallyUseCase` (6 tests) - Direct manual update
- `UpdateMultipleHandicapsUseCase` - Batch update with statistics
- `FindUserUseCase` (10 tests) - Search by email or name

### API Endpoints Active (30)
- `/api/v1/auth/register`, `/login`, `/logout`, `/verify-email`
- `/api/v1/users/profile`, `/security`, `/search`
- `/api/v1/handicaps/update`, `/update-manual`, `/update-multiple`

**Competitions (10)**:
- `/api/v1/competitions` (GET, POST)
- `/api/v1/competitions/{id}` (GET, PUT, DELETE)
- `/api/v1/competitions/{id}/activate`, `/close-enrollments`, `/start`, `/complete`, `/cancel`

**Enrollments (8)**:
- `/api/v1/competitions/{id}/enrollments` (GET, POST)
- `/api/v1/competitions/{id}/enrollments/direct`
- `/api/v1/enrollments/{id}/approve`, `/reject`, `/cancel`, `/withdraw`, `/handicap`

**Countries (2)**:
- `/api/v1/countries` (GET)
- `/api/v1/countries/{code}/adjacent` (GET)

### Implemented External Services (18 tests)

- **RFEGHandicapService** (5 integration tests) - Real RFEG web scraping
- **MockHandicapService** (13 tests) - Deterministic mock for testing
