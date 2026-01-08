# Module: User Management

## 📋 Description

Module responsible for user management, including registration, JWT authentication, profile management, handicaps, and email verification. Implements Clean Architecture with DDD.

**📋 See complete API:** `docs/API.md`

---

## 🎯 Implemented Use Cases

### Authentication
1. **RegisterUserUseCase** - New user registration
2. **LoginUserUseCase** - Authentication with JWT
3. **LogoutUserUseCase** - Session logout with refresh token revocation
4. **RefreshAccessTokenUseCase** - Access token renewal
5. **VerifyEmailUseCase** - Email verification with unique token
6. **ResendVerificationEmailUseCase** - Resend verification email

### Profile Management
7. **GetCurrentUserUseCase** - Get authenticated user data
8. **UpdateProfileUseCase** - Update personal information (name, surname, country_code)
9. **UpdateSecurityUseCase** - Change email or password

### Handicap Management
10. **UpdateUserHandicapManuallyUseCase** - Update handicap manually
11. **UpdateUserHandicapUseCase** - Get handicap from RFEG API
12. **BatchUpdateHandicapsUseCase** - Batch handicap update (cron job)

---

## 🗃️ Domain Model

### Entity: User (Aggregate Root)

**Identification:**
- `id`: UserId (Value Object - UUID)

**Personal Data:**
- `email`: Email (Value Object with RFC 5322 validation)
- `password`: Password (Value Object - bcrypt hashed, OWASP ASVS V2.1)
- `first_name`: str (100 chars max)
- `last_name`: str (100 chars max)
- `country_code`: CountryCode (Value Object - ISO 3166-1 alpha-2, optional)

**Handicap:**
- `handicap`: Handicap (Value Object - float, range -10.0 to 54.0, optional)
- `handicap_updated_at`: datetime

**Email Verification:**
- `email_verified`: bool (default False)
- `verification_token`: str (unique UUID, optional)

**Timestamps:**
- `created_at`: datetime
- `updated_at`: datetime

### Value Objects

**Implemented:**
- `UserId` - Unique user UUID
- `Email` - RFC 5322 validation, lowercase normalization
- `Password` - OWASP ASVS V2.1 validation (12 chars min, complexity, blacklist)
- `Handicap` - Range validation [-10.0, 54.0]
- `CountryCode` - ISO 3166-1 alpha-2 validation

**📋 See implementation:** `src/modules/user/domain/value_objects/`

### Domain Events

**Implemented:**
1. `UserCreatedEvent` - User registered
2. `EmailVerifiedEvent` - Email verified
3. `HandicapUpdatedEvent` - Handicap updated
4. `LoginAttemptEvent` - Login attempt (success/failure) - Security
5. `LogoutEvent` - Logout executed - Security
6. `RefreshTokenUsedEvent` - Refresh token used - Security
7. `RefreshTokenRevokedEvent` - Refresh token revoked - Security
8. `PasswordChangedEvent` - Password changed - Security
9. `EmailChangedEvent` - Email changed - Security

**📋 See security events:** `src/shared/domain/events/security_events.py`

---

## 🏗️ Architecture

### Repository Pattern

**Interfaces (Domain Layer):**
- `UserRepositoryInterface` - User CRUD
  - find_by_id, find_by_email, add, update, delete, exists_by_email
- `RefreshTokenRepositoryInterface` - Refresh token management
  - save, find_by_token_hash, revoke_all_for_user, delete_expired

**Implementations (Infrastructure Layer):**
- `SQLAlchemyUserRepository` - Async persistence with PostgreSQL
- `SQLAlchemyRefreshTokenRepository` - Refresh token persistence

**📋 See implementation:** `src/modules/user/infrastructure/persistence/sqlalchemy/`

### Unit of Work Pattern

**Interface (Domain Layer):**
```python
UserUnitOfWorkInterface
├── users: UserRepositoryInterface
├── refresh_tokens: RefreshTokenRepositoryInterface
├── async commit()
├── async rollback()
└── async __aenter__() / __aexit__()
```

**Implementation (Infrastructure Layer):**
- `SQLAlchemyUserUnitOfWork` - Atomic transaction management

**Benefits:**
- Atomic transactions (commit/rollback)
- Multiple repositories in single transaction
- Business logic isolation from persistence

### Domain Services

**Implemented:**
- `UserFinder` - User search with business validations
- `PasswordHasher` (ABC) → `BcryptPasswordHasher` (Infrastructure)
  - hash_password(), verify_password()
  - bcrypt: 12 rounds (prod), 4 rounds (tests)

### Application Services (Ports)

**Interfaces (Application Layer):**
- `IEmailService` - Email sending (Port)
- `ITokenService` - JWT token generation (Port)

**Implementations (Infrastructure Layer):**
- `EmailService` - Mailgun API (EU region)
- `JWTTokenService` - python-jose, HS256 algorithm

**Dependency Injection:**
- Configured in `src/config/dependencies.py`
- Complete Inversion of Control (IoC)

**📋 See refactoring:** CLAUDE.md - Dependency Injection Refactoring (16 Nov 2025)

---

## 🔐 Security Implemented

### JWT Authentication
- **Access Token:** 15 minutes (httpOnly cookie)
- **Refresh Token:** 7 days (httpOnly cookie, SHA256 hash in DB)
- **Algorithm:** HS256
- **Revocation:** Logout invalidates refresh tokens in DB

### Password Security (OWASP ASVS V2.1)
- Minimum length: 12 characters
- Complexity: Uppercase + Lowercase + Digits + Symbols
- Common password blacklist
- Hashing: bcrypt 12 rounds

### httpOnly Cookies
- XSS protection (JavaScript cannot access)
- Flags: httponly=True, secure=production, samesite="lax"
- Dual support: cookies (priority 1) + headers (legacy)

### Rate Limiting
- Login: 5 attempts/minute per IP
- Register: 3 attempts/hour per IP
- RFEG API: 5 calls/hour per user

### Security Logging (Audit Trail)
- Logs in `logs/security_audit.log` (structured JSON)
- 9 audited security events
- HTTP Context: IP, User-Agent
- Severity levels: CRITICAL, HIGH, MEDIUM, LOW

**📋 See complete implementation:** `docs/SECURITY_IMPLEMENTATION.md`

---

## 📊 Database Schema

### Table: users
```sql
CREATE TABLE users (
    id UUID PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    handicap DECIMAL(4,1),
    handicap_updated_at TIMESTAMP,
    email_verified BOOLEAN DEFAULT FALSE,
    verification_token VARCHAR(255),
    country_code VARCHAR(2) REFERENCES countries(code),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

### Table: refresh_tokens
```sql
CREATE TABLE refresh_tokens (
    id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(36) REFERENCES users(id) ON DELETE CASCADE,
    token_hash VARCHAR(64) UNIQUE NOT NULL,
    expires_at DATETIME NOT NULL,
    created_at DATETIME DEFAULT NOW(),
    revoked BOOLEAN DEFAULT FALSE,
    revoked_at DATETIME
);
CREATE INDEX idx_refresh_tokens_user_id ON refresh_tokens(user_id);
CREATE INDEX idx_refresh_tokens_token_hash ON refresh_tokens(token_hash);
CREATE INDEX idx_refresh_tokens_expires_at ON refresh_tokens(expires_at);
```

**SQLAlchemy Mappers:**
- Imperative Mapping (no declarative base)
- TypeDecorators for single-column Value Objects
- Composites for multi-column Value Objects

**📋 See mappers:** `src/modules/user/infrastructure/persistence/sqlalchemy/mappers.py`

---

## 📡 API Endpoints

### Authentication
- `POST /api/v1/auth/register` - User registration
- `POST /api/v1/auth/login` - Login with JWT
- `POST /api/v1/auth/logout` - Logout with revocation
- `POST /api/v1/auth/refresh-token` - Renew access token
- `POST /api/v1/auth/verify-email` - Verify email with token
- `POST /api/v1/auth/resend-verification` - Resend verification email
- `GET /api/v1/auth/current-user` - Get authenticated user

### Profile Management
- `GET /api/v1/users/profile` - Get profile
- `PUT /api/v1/users/profile` - Update profile (name, surname, country_code)
- `PUT /api/v1/users/security` - Update email or password

### Handicap Management
- `PUT /api/v1/users/handicaps/manual` - Update handicap manually
- `POST /api/v1/users/handicaps/update` - Get from RFEG API
- `POST /api/v1/users/handicaps/batch-update` - Batch update (admin)

**📋 See complete documentation:** `docs/API.md`

**📋 See Postman Collection:** `docs/postman_collection.json`

---

## 🧪 Testing

### Testing Stack
- **pytest** - Testing framework
- **pytest-asyncio** - Async tests
- **pytest-xdist** - Parallelization
- **httpx** - HTTP client for integration tests

### Statistics
- **Total User Module:** 507 tests (100% passing)
- **Unit Tests:** 308 tests
  - Domain: 49 tests (entities)
  - Value Objects: Complete validation tests
  - Use Cases: 83 tests
- **Integration Tests:** 72 tests (API endpoints)

### Structure
```
tests/
├── unit/
│   └── modules/user/
│       ├── domain/entities/test_user.py
│       ├── domain/value_objects/test_*.py
│       ├── application/use_cases/test_*.py
│       └── infrastructure/test_*.py
└── integration/
    └── api/v1/
        ├── test_user_routes.py
        └── test_auth_routes.py
```

### Execution
```bash
# All tests for User module
pytest tests/unit/modules/user/ tests/integration/api/v1/test_user_routes.py -v

# Only unit tests (fast, no DB required)
pytest tests/unit/modules/user/ -v

# With parallelization
pytest tests/unit/modules/user/ -n auto
```

### Test Doubles (In-Memory)
- `InMemoryUserRepository` - Tests without PostgreSQL
- `InMemoryRefreshTokenRepository` - Refresh token tests
- `InMemoryUnitOfWork` - Transaction tests

**📋 See test doubles:** `tests/in_memory/`

---

## 🔄 Key Architecture Decisions

### 1. Handicap Value Object Mapping
**Decision:** TypeDecorator (not composite())

**Reason:**
- Handicap is a single-column optional Value Object (NULL)
- composite() does not handle NULL correctly
- TypeDecorator transparently converts Handicap ↔ float

**📋 See ADR:** CLAUDE.md - Architecture Decisions

### 2. Dependency Injection Refactoring
**Decision:** Ports & Adapters (Hexagonal Architecture)

**Before (❌):**
- Use cases directly imported EmailService, JWTTokenService
- Violation of Dependency Inversion Principle

**After (✅):**
- Application Layer: IEmailService, ITokenService (Ports)
- Infrastructure Layer: EmailService, JWTTokenService (Adapters)
- Use cases depend on abstractions

**Result:** 440/440 tests passing - Clean Architecture 100%

### 3. Session Timeout with Refresh Tokens
**Decision:** Short access token + long refresh token pattern

**Before (❌):**
- Access token: 60 minutes
- No revocation possible
- Logout only deleted browser cookie

**After (✅):**
- Access token: 15 minutes (-75% hijacking window)
- Refresh token: 7 days (SHA256 hash in DB)
- DB revocation on logout
- 722/722 tests passing (+35 new)

**📋 See implementation:** CLAUDE.md - Session Timeout with Refresh Tokens

### 4. Password Policy (OWASP ASVS V2.1)
**Decision:** Update from 8 to 12 minimum characters

**Before (❌):**
- 8 minimum characters (obsolete according to OWASP 2024)

**After (✅):**
- 12 minimum characters
- Full complexity required
- Common password blacklist
- 681 tests updated (100%)

**📋 See migration:** CLAUDE.md - Password Policy

---

## 🔗 Related Links

### Documentation
- **API Endpoints:** `docs/API.md`
- **Security Implementation:** `docs/SECURITY_IMPLEMENTATION.md`
- **Postman Collection:** `docs/postman_collection.json`

### Source Code
- **Domain Layer:** `src/modules/user/domain/`
- **Application Layer:** `src/modules/user/application/`
- **Infrastructure Layer:** `src/modules/user/infrastructure/`

### ADRs (Architecture Decision Records)
- **ADR-002:** Value Objects
- **ADR-005:** Repository Pattern
- **ADR-006:** Unit of Work Pattern
- **ADR-007:** Domain Events Pattern
- **ADR-013:** External Services Pattern
- **ADR-015:** Session Management Progressive Strategy
- **ADR-019:** Email Verification System

### Testing
- **Unit Tests:** `tests/unit/modules/user/`
- **Integration Tests:** `tests/integration/api/v1/`
- **Test Doubles:** `tests/in_memory/`

---

## 💡 Development Tips

### Create New Use Case
1. Define Request and Response DTO in `application/dto/`
2. Create Use Case in `application/use_cases/`
3. Inject dependencies (UoW, services) in constructor
4. Implement logic in `execute()` method
5. Use `async with self._uow:` for transactions
6. Emit domain events if necessary
7. Create unit + integration tests

### Add New Value Object
1. Create class in `domain/value_objects/`
2. Inherit from base class if applicable
3. Implement validations in constructor
4. Add `__eq__()` method for comparisons
5. Create TypeDecorator in mapper (if 1 column)
6. Create complete validation tests

### Add New Endpoint
1. Define route in `infrastructure/api/v1/`
2. Inject Use Case with `Depends()`
3. Inject `get_current_user` if auth required
4. Handle domain exceptions → HTTP status codes
5. Add rate limiting if applicable
6. Document in `docs/API.md`
7. Update Postman collection

---

**Last Updated:** 8 January 2026
**Version:** v1.13.0
