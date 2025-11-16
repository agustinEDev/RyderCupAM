# RyderCupAM - Quick Reference Guide

## File Locations - Key Files to Know

### Configuration
- `/home/user/RyderCupAM/main.py` - FastAPI app entry point
- `/home/user/RyderCupAM/src/config/settings.py` - Environment configuration
- `/home/user/RyderCupAM/src/config/database.py` - SQLAlchemy async setup
- `/home/user/RyderCupAM/src/config/dependencies.py` - Dependency injection (Composition Root)

### Domain Layer (Pure Business Logic)
**User Entity**
- `/home/user/RyderCupAM/src/modules/user/domain/entities/user.py` - Core User aggregate

**Value Objects**
- `/home/user/RyderCupAM/src/modules/user/domain/value_objects/user_id.py` - UUID wrapper
- `/home/user/RyderCupAM/src/modules/user/domain/value_objects/email.py` - Validated email
- `/home/user/RyderCupAM/src/modules/user/domain/value_objects/password.py` - Hashed password
- `/home/user/RyderCupAM/src/modules/user/domain/value_objects/handicap.py` - Golf handicap

**Domain Events**
- `/home/user/RyderCupAM/src/modules/user/domain/events/` - 8 event types

**Repository Interfaces**
- `/home/user/RyderCupAM/src/modules/user/domain/repositories/user_repository_interface.py`
- `/home/user/RyderCupAM/src/modules/user/domain/repositories/user_unit_of_work_interface.py`

**Domain Services**
- `/home/user/RyderCupAM/src/modules/user/domain/services/user_finder.py`
- `/home/user/RyderCupAM/src/modules/user/domain/services/handicap_service.py`

### Application Layer (Use Cases & Orchestration)
- `/home/user/RyderCupAM/src/modules/user/application/use_cases/` - 10 use case implementations
- `/home/user/RyderCupAM/src/modules/user/application/dto/user_dto.py` - All DTOs
- `/home/user/RyderCupAM/src/modules/user/application/handlers/` - Event handlers

### Infrastructure Layer (External Adapters)
**Persistence**
- `/home/user/RyderCupAM/src/modules/user/infrastructure/persistence/sqlalchemy/user_repository.py` - SQLAlchemy impl
- `/home/user/RyderCupAM/src/modules/user/infrastructure/persistence/sqlalchemy/unit_of_work.py` - Transaction management
- `/home/user/RyderCupAM/src/modules/user/infrastructure/persistence/in_memory/` - Testing implementations

**API Routes**
- `/home/user/RyderCupAM/src/modules/user/infrastructure/api/v1/auth_routes.py` - Auth endpoints
- `/home/user/RyderCupAM/src/modules/user/infrastructure/api/v1/handicap_routes.py` - Handicap endpoints
- `/home/user/RyderCupAM/src/modules/user/infrastructure/api/v1/user_routes.py` - User endpoints

**External Services**
- `/home/user/RyderCupAM/src/modules/user/infrastructure/external/rfeg_handicap_service.py` - RFEG integration
- `/home/user/RyderCupAM/src/modules/user/infrastructure/external/mock_handicap_service.py` - Testing mock
- `/home/user/RyderCupAM/src/shared/infrastructure/email/email_service.py` - Email service (Mailgun)
- `/home/user/RyderCupAM/src/shared/infrastructure/security/jwt_handler.py` - JWT tokens

### Shared Infrastructure
- `/home/user/RyderCupAM/src/shared/domain/events/domain_event.py` - Base event class
- `/home/user/RyderCupAM/src/shared/domain/events/event_bus.py` - Event bus interface
- `/home/user/RyderCupAM/src/shared/domain/events/in_memory_event_bus.py` - Event bus implementation

### Tests
- `/home/user/RyderCupAM/tests/unit/` - 360 unit tests (isolated, no DB)
- `/home/user/RyderCupAM/tests/integration/` - 60 integration tests (with DB)
- `/home/user/RyderCupAM/tests/conftest.py` - Test fixtures and configuration

### Project Configuration
- `/home/user/RyderCupAM/requirements.txt` - Python dependencies
- `/home/user/RyderCupAM/pytest.ini` - Test configuration
- `/home/user/RyderCupAM/alembic.ini` - Database migration config
- `/home/user/RyderCupAM/docker-compose.yml` - Docker setup

---

## Command Reference

### Running the Application
```bash
# Local development (with auto-reload)
uvicorn main:app --reload

# Production
uvicorn main:app --host 0.0.0.0 --port 8000

# Docker
docker-compose up -d
```

### Running Tests
```bash
# Full test suite (recommended)
python dev_tests.py

# Specific test files
pytest tests/unit/modules/user/domain/entities/test_user.py

# Specific test
pytest tests/unit/modules/user/domain/entities/test_user.py::TestUserCreation::test_create_user_with_valid_data

# With coverage
pytest --cov=src tests/

# Only integration tests
pytest tests/integration/ -m integration

# Only unit tests
pytest tests/unit/
```

### Database Migrations
```bash
# Create new migration (with auto-detection)
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback
alembic downgrade -1
```

### Code Quality
```bash
# Type checking
mypy src/

# Code formatting
black src/ tests/

# Linting
flake8 src/ tests/
```

---

## Architecture Quick Links

### Pattern Reference
| Pattern | Location | Purpose |
|---------|----------|---------|
| **Aggregate Root** | `user.py` | User entity with business logic |
| **Value Objects** | `value_objects/` | Immutable, validated types |
| **Repository** | `repositories/interface.py` | Data access abstraction |
| **Unit of Work** | `repositories/unit_of_work.py` | Transaction management |
| **Use Case** | `use_cases/` | Application orchestration |
| **DTO** | `dto/user_dto.py` | Request/response models |
| **Domain Event** | `events/` | Business event notifications |
| **Domain Service** | `services/` | Complex domain logic |
| **Event Handler** | `handlers/` | Event side effects |
| **External Service** | `external/` | Third-party integrations |

### Dependency Injection Flow
```
FastAPI Endpoint
    ↓
Dependencies.py Factory (get_use_case())
    ↓
Use Case Instance
    ├─→ Repository (interface, injected as SQLAlchemy impl)
    ├─→ Unit of Work
    ├─→ Domain Services
    └─→ External Services
```

### Adding a New Feature (Feature Checklist)

1. **Define Domain Model**
   - [ ] Create entity/value object in `domain/entities/` or `domain/value_objects/`
   - [ ] Add domain event in `domain/events/`
   - [ ] Add domain service if needed

2. **Implement Business Logic**
   - [ ] Add use case in `application/use_cases/`
   - [ ] Add DTOs in `application/dto/`
   - [ ] Add event handler if needed

3. **Implement Infrastructure**
   - [ ] Add API route in `infrastructure/api/v1/`
   - [ ] Update repository if needed
   - [ ] Add external service if needed

4. **Testing**
   - [ ] Unit tests for domain (`tests/unit/modules/user/domain/`)
   - [ ] Unit tests for use case (`tests/unit/modules/user/application/use_cases/`)
   - [ ] Integration tests for API (`tests/integration/api/v1/`)
   - [ ] Ensure >90% coverage

5. **Documentation**
   - [ ] Update API docs in OpenAPI
   - [ ] Document in design document if architectural
   - [ ] Update README if user-facing

---

## API Endpoints

### Authentication
```
POST   /api/v1/auth/register              # Create user
POST   /api/v1/auth/login                 # Get JWT token
POST   /api/v1/auth/logout                # Logout (audit log)
POST   /api/v1/auth/verify-email          # Verify email token
POST   /api/v1/auth/resend-verification   # Resend verification email
```

### Handicap Management
```
POST   /api/v1/handicaps/update           # RFEG lookup
POST   /api/v1/handicaps/update-manual    # Manual update
POST   /api/v1/handicaps/update-multiple  # Batch update
```

### User Management
```
GET    /api/v1/users/search               # Search by email/name
```

### Utilities
```
GET    /                                   # Health check
GET    /docs                               # API documentation (protected)
GET    /redoc                              # ReDoc documentation (protected)
```

---

## Key Concepts

### Aggregate Root
The User entity is the aggregate root - it owns all related objects and enforces business rules:
```python
user = User.create(
    first_name="John",
    last_name="Doe",
    email_str="john@example.com",
    plain_password="SecurePass123"
)
# Returns User with generated ID, hashed password, domain events
```

### Value Objects
Immutable, validated objects representing domain concepts:
```python
email = Email("john@example.com")      # Validates & normalizes
password = Password.from_plain_text("pwd")  # Hashes with bcrypt
handicap = Handicap(12.5)              # Validates range
user_id = UserId.generate()            # Generates UUID
```

### Domain Events
Business events that occurred:
```python
user.record_login(logged_in_at, ip_address)  # Emits UserLoggedInEvent
user.update_handicap(15.0)                    # Emits HandicapUpdatedEvent
user.verify_email(token)                      # Emits EmailVerifiedEvent
```

### Repository Pattern
Abstract interface for data access:
```python
# Domain layer (interface)
class UserRepositoryInterface(ABC):
    async def save(self, user: User) -> None: ...
    async def find_by_email(self, email: Email) -> Optional[User]: ...

# Infrastructure layer (implementation)
class SQLAlchemyUserRepository(UserRepositoryInterface):
    async def save(self, user: User) -> None:
        self._session.add(user)
```

### Unit of Work
Manages transaction boundaries:
```python
async with self._uow:
    user = await self._uow.users.find_by_email(email)
    # Changes auto-committed on exit, rolled back on exception
```

### Use Cases
Orchestrate domain and infrastructure:
```python
class RegisterUserUseCase:
    async def execute(self, request: RegisterUserRequestDTO):
        # 1. Validate (domain)
        # 2. Create entity (domain)
        # 3. Persist (infrastructure via UoW)
        # 4. Send email (infrastructure)
        return UserResponseDTO
```

### Dependency Injection
FastAPI provides instances automatically:
```python
@router.post("/register")
async def register_user(
    request: RegisterUserRequestDTO,
    use_case: RegisterUserUseCase = Depends(get_register_user_use_case)
):
    # use_case is constructed by factory with all dependencies
    return await use_case.execute(request)
```

---

## Testing Patterns

### Unit Test (Domain)
```python
def test_user_creation():
    user = User.create(
        first_name="John",
        last_name="Doe",
        email_str="john@example.com",
        plain_password="SecurePass123"
    )
    assert user.email.value == "john@example.com"
    assert user.verify_password("SecurePass123")
    assert len(user.get_domain_events()) > 0
```

### Unit Test (Use Case with Mocked Repo)
```python
@pytest.mark.asyncio
async def test_register_user():
    mock_repo = AsyncMock(spec=UserRepositoryInterface)
    mock_repo.find_by_email.return_value = None  # Email not taken
    
    uow = AsyncMock(spec=UserUnitOfWorkInterface)
    uow.users = mock_repo
    
    use_case = RegisterUserUseCase(uow)
    result = await use_case.execute(
        RegisterUserRequestDTO(
            email="john@example.com",
            password="SecurePass123",
            first_name="John",
            last_name="Doe"
        )
    )
    assert result.email == "john@example.com"
    mock_repo.save.assert_called_once()
```

### Integration Test (API)
```python
@pytest.mark.asyncio
@pytest.mark.integration
async def test_register_endpoint(client):
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "john@example.com",
            "password": "SecurePass123",
            "first_name": "John",
            "last_name": "Doe"
        }
    )
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "john@example.com"
    assert "id" in data
```

### Database Test
```python
@pytest.mark.asyncio
@pytest.mark.integration
async def test_user_repository_save(db_session):
    repo = SQLAlchemyUserRepository(db_session)
    user = User.create(...)
    
    await repo.save(user)
    await db_session.commit()
    
    found = await repo.find_by_email(user.email)
    assert found is not None
    assert found.id == user.id
```

---

## Environment Variables

### Required for Production
```bash
SECRET_KEY=<random-32-char-string>
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/dbname
MAILGUN_API_KEY=<your-mailgun-key>
MAILGUN_DOMAIN=<your-domain>
FRONTEND_URL=https://yourfrontend.com
```

### Optional
```bash
ENVIRONMENT=production|development
DOCS_USERNAME=admin
DOCS_PASSWORD=secure-password
MAILGUN_API_URL=https://api.mailgun.net/v3  # or eu endpoint
FRONTEND_ORIGINS=https://app.example.com,https://web.example.com
```

---

## Common Issues & Solutions

| Issue | Solution |
|-------|----------|
| Import errors in tests | Ensure `PYTHONPATH` includes project root: `export PYTHONPATH=/home/user/RyderCupAM` |
| Database connection errors | Check DATABASE_URL format and PostgreSQL is running |
| Test database already exists | Fixtures auto-cleanup; check no stray processes holding connections |
| Async test not running | Ensure pytest.ini has `asyncio_mode = auto` |
| Migration conflicts | Use `alembic downgrade -1` then create new migration |
| Email service failures | Check MAILGUN_API_KEY and MAILGUN_DOMAIN are set |

---

## Learning Resources

### Code Examples in the Codebase
- **Entity with events**: `/home/user/RyderCupAM/src/modules/user/domain/entities/user.py`
- **Value object validation**: `/home/user/RyderCupAM/src/modules/user/domain/value_objects/email.py`
- **Repository pattern**: `/home/user/RyderCupAM/src/modules/user/domain/repositories/user_repository_interface.py`
- **Use case orchestration**: `/home/user/RyderCupAM/src/modules/user/application/use_cases/register_user_use_case.py`
- **API endpoint**: `/home/user/RyderCupAM/src/modules/user/infrastructure/api/v1/auth_routes.py`

### Documentation Files
- `ARCHITECTURE_ANALYSIS.md` - Comprehensive architecture overview
- `ARCHITECTURE_DIAGRAM.md` - Visual diagrams and flows
- `/home/user/RyderCupAM/docs/design-document.md` - Technical specifications
- `/home/user/RyderCupAM/docs/project-structure.md` - Code organization conventions
- `/home/user/RyderCupAM/README.md` - Project overview

---

## Testing Statistics

```
Total Tests: 420
├── Unit Tests: 360
│   ├── Domain: 120
│   ├── Application: 150
│   └── Infrastructure: 90
└── Integration Tests: 60
    ├── API: 40
    ├── Persistence: 15
    └── Events: 5

Coverage: >90% (business logic)
Pass Rate: 100% ✅
Warnings: 0 ✅
Execution Time: ~25 seconds (with parallelization)
```

---

**Last Updated**: 2025-11-16
**Project Phase**: 1 (Foundation) - Complete
**Python Version**: 3.12+
**FastAPI Version**: 0.115+
