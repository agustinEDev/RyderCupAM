# Design Document - Ryder Cup Manager

**v3.0** · 30 Nov 2025 · Fase 2 Completa

---

## Resumen

Sistema de torneos de golf amateur formato Ryder Cup.

**Stack**: Python 3.11-3.12, FastAPI, PostgreSQL, Clean Architecture + DDD

**Features**:
- ✅ User management + JWT auth
- ✅ Email verification (Mailgun, UUID tokens, bilingüe)
- ✅ Handicap system (RFEG integration)
- ✅ Competition Module (torneos formato Ryder Cup)
- ✅ CI/CD Pipeline (GitHub Actions)
- ⏳ Real-time scoring (planeado)

---

## Arquitectura

### Clean Architecture (3 capas)

```
Infrastructure (FastAPI, SQLAlchemy, RFEG)
    ↓
Application (Use Cases, DTOs, Handlers)
    ↓
Domain (Entities, VOs, Events, Repos)
```

**Regla**: Dependencias hacia adentro.

**Patrones**: Repository, UoW, Domain Events, Value Objects, External Services.

> ADRs: [001](architecture/decisions/ADR-001-clean-architecture.md), [002](architecture/decisions/ADR-002-value-objects.md), [005](architecture/decisions/ADR-005-repository-pattern.md), [006](architecture/decisions/ADR-006-unit-of-work-pattern.md), [007](architecture/decisions/ADR-007-domain-events-pattern.md)

---

## Módulos

### User Management

**Domain**:
- Entity: `User`
- VOs: `UserId`, `Email`, `Password`, `Handicap`
- Events: `UserRegistered`, `HandicapUpdated`, `UserLoggedIn`, `UserLoggedOut`, `UserProfileUpdated`, `UserEmailChanged`, `UserPasswordChanged`
- Repos: `UserRepositoryInterface`
- Services: `HandicapService` (interface)
- Email Verification: Campo `email_verified`, `verification_token`, evento `EmailVerifiedEvent`

**Application**:
- Use Cases: `RegisterUser`, `LoginUser`, `LogoutUser`, `UpdateProfile`, `UpdateSecurity`, `UpdateHandicap`, `UpdateHandicapManually`, `UpdateMultipleHandicaps`, `FindUser`
- DTOs: Request/Response
- Handlers: `UserRegisteredEventHandler`
- Email Verification: `VerifyEmailUseCase`, integración en registro

**Infrastructure**:
- Routes: `/auth/*`, `/handicaps/*`, `/users/*`
- Repos: `SQLAlchemyUserRepository`
- External: `RFEGHandicapService`, `MockHandicapService`
- Email Verification: Servicio `EmailService` (Mailgun), endpoint `/api/v1/auth/verify-email`

**Email Verification**:
- Domain: Campo `email_verified`, `verification_token`, evento `EmailVerifiedEvent`
- Application: Use case `VerifyEmailUseCase`, integración en registro
- Infrastructure: Servicio `EmailService` (Mailgun), endpoint `/api/v1/auth/verify-email`

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
- Database: Migraciones Alembic (competitions, enrollments, countries, country_adjacencies)
- Seed Data: 166 países + 614 relaciones de fronteras

**Features**:
- Gestión completa de torneos (CRUD + state machine)
- Sistema de inscripciones (solicitudes, invitaciones, aprobaciones)
- Soporte multi-país (hasta 3 países adyacentes)
- Custom handicaps por enrollment
- 20 endpoints REST API

> ADR: [020](architecture/decisions/ADR-020-competition-module-domain-design.md)

---

## Modelos de Datos

### User Entity

```python
User:
    id: UserId (UUID)
    email: Email (validado, normalizado)
    password: Password (bcrypt, rounds=12)
    first_name: str
    last_name: str
    handicap: float? (-10.0 a 54.0)
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

## Flujos de Negocio

### 1. Registro Usuario

```
Client → API → UseCase → User.create() → UoW.save() → commit()
                                            ↓
                                       EventBus → Handlers
```

1. Validar email no existe
2. `User.create()` genera `UserRegisteredEvent`
3. UoW guarda + commit
4. Eventos publicados
5. Handlers procesan (email, audit)

> ADR: [006](architecture/decisions/ADR-006-unit-of-work-pattern.md), [007](architecture/decisions/ADR-007-domain-events-pattern.md)

### 2. Update Handicap (RFEG)

```
API → UseCase → HandicapService.search(name) → RFEG
                      ↓
                user.update_handicap() → HandicapUpdatedEvent
                      ↓
                  UoW.commit()
```

1. Buscar usuario
2. Consultar RFEG con nombre completo
3. Actualizar + emitir evento
4. Commit publica evento

**Fallback**: Si RFEG falla, usar `manual_handicap` (opcional)

**Error Handling**: Si jugador no encontrado en RFEG y no hay `manual_handicap`, lanzar `HandicapNotFoundError` (404)

> ADR: [013](architecture/decisions/ADR-013-external-services-pattern.md), [014](architecture/decisions/ADR-014-handicap-management-system.md)

---

## Integraciones Externas

### RFEG (Real Federación Española de Golf)

**Tipo**: Web scraping (no API pública)
**Flujo**: Extraer token → Buscar por nombre → Parsear JSON
**Timeout**: 10s
**Errors**: Log + retornar None

**Implementación**:
- Interface: `HandicapService` (domain)
- Impl: `RFEGHandicapService` (infra)
- Mock: `MockHandicapService` (tests)

> ADR: [013](architecture/decisions/ADR-013-external-services-pattern.md)

---

## Seguridad

### Autenticación

**JWT**: HS256, exp 60min, secret en env
**Password**: bcrypt, rounds=12 (prod), rounds=4 (test)

### Validación

1. Pydantic (API): tipos y formatos
2. Value Objects (Domain): reglas de negocio
3. Database: constraints (UNIQUE, NOT NULL)

> ADR: [004](architecture/decisions/ADR-004-tech-stack.md)

---

## API Endpoints

### Auth
- `POST /api/v1/auth/register` - Registro de usuario
- `POST /api/v1/auth/login` - Autenticación JWT + UserLoggedInEvent
- `POST /api/v1/auth/logout` - Logout con auditoría + UserLoggedOutEvent
- `POST /api/v1/auth/verify-email` - Verificación de email (token por correo)

### Handicaps
- `POST /api/v1/handicaps/update` - RFEG lookup + fallback
- `POST /api/v1/handicaps/update-manual` - Manual directo
- `POST /api/v1/handicaps/update-multiple` - Batch update

### Users
- `GET /api/v1/users/search` - Buscar por email o nombre
- `PATCH /api/v1/users/profile` - Actualizar nombre/apellido (sin password)
- `PATCH /api/v1/users/security` - Actualizar email/password (con password)

> Detalle: [API.md](API.md)

---

## Testing

**Estrategia**: Test Pyramid (89% unit, 11% integration)

```
667 tests (97.6% passing)
├── Unit: 595+ tests
│   ├── User Module: 308 tests
│   ├── Competition Module: 173 tests
│   ├── Shared: 60 tests
│   └── Other: 54+ tests
└── Integration: 72+ tests
    ├── API: ~60 tests
    └── Domain Events: ~12 tests
```

**Cobertura**: >90% en lógica de negocio
**Email Verification**: 100% (24 tests en 3 niveles)
**Competition Module**: 97.6% (174 tests completos)
**Performance**: ~30s (paralelización con pytest-xdist)

**CI/CD**: Tests ejecutados automáticamente en GitHub Actions (Python 3.11, 3.12)

> ADR: [003](architecture/decisions/ADR-003-testing-strategy.md)

---

## CI/CD Pipeline

**Platform**: GitHub Actions

**Jobs (7 paralelos)**:
1. Preparation (Python 3.11/3.12 setup + cache)
2. Unit Tests (matrix Python 3.11, 3.12)
3. Integration Tests (PostgreSQL service container)
4. Security Scan (Gitleaks)
5. Code Quality (Ruff)
6. Type Checking (Mypy)
7. Database Migrations (Alembic validation)

**Execution Time**: ~3 minutos
**Trigger**: Push, Pull Request
**Matrix**: Python 3.11, 3.12

**Configurations**:
- Mypy: Configuración pragmática para SQLAlchemy imperative mapping
- Gitleaks: Whitelist para false positives en docs
- PostgreSQL: Service container para integration tests
- Caché: pip dependencies

> ADR: [021](architecture/decisions/ADR-021-github-actions-ci-cd-pipeline.md)

---

## Referencias ADRs

**Fundación**: [001](architecture/decisions/ADR-001-clean-architecture.md), [004](architecture/decisions/ADR-004-tech-stack.md)

**Patrones**: [002](architecture/decisions/ADR-002-value-objects.md), [005](architecture/decisions/ADR-005-repository-pattern.md), [006](architecture/decisions/ADR-006-unit-of-work-pattern.md), [007](architecture/decisions/ADR-007-domain-events-pattern.md)

**Infra**: [009](architecture/decisions/ADR-009-docker-for-development-environment.md), [010](architecture/decisions/ADR-010-alembic-for-database-migrations.md), [021](architecture/decisions/ADR-021-github-actions-ci-cd-pipeline.md)

**Features**: [011](architecture/decisions/ADR-011-application-layer-use-cases.md), [012](architecture/decisions/ADR-012-composition-root.md), [013](architecture/decisions/ADR-013-external-services-pattern.md), [014](architecture/decisions/ADR-014-handicap-management-system.md), [015](architecture/decisions/ADR-015-session-management-progressive-strategy.md), [020](architecture/decisions/ADR-020-competition-module-domain-design.md)

---

## 📊 Métricas del Proyecto

**Última actualización**: 30 Nov 2025

### Testing

| Métrica | Valor |
|---------|-------|
| Tests totales | 667 (97.6% passing) |
| Tests unitarios | 595+ tests |
| Tests integración | 72+ tests |
| Cobertura | >90% |
| Email Verification | 100% (24 tests) |
| Competition Module | 97.6% (174 tests) |
| Tiempo ejecución | ~30s (paralelo) |
| CI/CD Pipeline | ~3 min (7 jobs) |

### Progreso de Módulos

| Módulo | Estado | Tests | Endpoints |
|--------|--------|-------|-----------|
| User | ✅ Completo + Auth + Email | 308+ | 10 |
| Competition | ✅ Completo + Enrollments | 174 | 20 |
| CI/CD | ✅ GitHub Actions | - | - |
| Real-time Scoring | ⏳ Pendiente | 0 | 0 |

### Value Objects Implementados (69 tests)

- **UserId** (12 tests) - Identificador UUID único
- **Email** (14 tests) - Email validado y normalizado
- **Password** (23 tests) - Contraseña bcrypt hasheada
- **Handicap** (20 tests) - Rango -10.0 a 54.0 (RFEG/EGA)

### Domain Events Implementados (59 tests)

- **UserRegisteredEvent** (9 tests) - Usuario registrado
- **HandicapUpdatedEvent** (16 tests) - Handicap actualizado con delta
- **UserLoggedOutEvent** (7 tests) - Usuario cerró sesión (auditoría)
- **UserLoggedInEvent** (7 tests) - Usuario inició sesión (auditoría completa)
- **UserProfileUpdatedEvent** (7 tests) - Perfil de usuario actualizado
- **UserEmailChangedEvent** (7 tests) - Email cambiado
- **UserPasswordChangedEvent** (6 tests) - Password cambiado

### Use Cases Implementados (68 tests)

**User Module (9 use cases)**:
- `RegisterUserUseCase` (5 tests) - Registro de usuario
- `LoginUserUseCase` (5 tests) - Autenticación JWT + eventos
- `LogoutUserUseCase` (5 tests) - Logout con auditoría completa
- `UpdateProfileUseCase` (7 tests) - Actualización de nombre/apellido sin password
- `UpdateSecurityUseCase` (9 tests) - Actualización de email/password con verificación
- `UpdateUserHandicapUseCase` (10 tests) - Actualización desde RFEG con fallback
- `UpdateUserHandicapManuallyUseCase` (6 tests) - Actualización manual directa
- `UpdateMultipleHandicapsUseCase` - Batch update con estadísticas
- `FindUserUseCase` (10 tests) - Búsqueda por email o nombre

### API Endpoints Activos (30)

**Auth & Users (10)**:
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

### External Services Implementados (18 tests)

- **RFEGHandicapService** (5 tests integración) - Web scraping RFEG real
- **MockHandicapService** (13 tests) - Mock determinístico para testing
