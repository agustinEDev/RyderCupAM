# Design Document - Ryder Cup Manager

**v2.0** · 9 Nov 2025 · En desarrollo

---

## Resumen

Sistema de torneos de golf amateur formato Ryder Cup.

**Stack**: Python 3.12+, FastAPI, PostgreSQL, Clean Architecture + DDD

**Features**:
- User management + JWT auth
- Email verification (Mailgun, UUID tokens, bilingüe)
- Handicap system (RFEG integration)
- Tournament management (planeado)
- Real-time scoring (planeado)

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

### Tournament *(Planeado)*

**Domain**: Tournament, Team, Match, Score entities
**Features**: Formación equipos, scoring, leaderboard

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

**Estrategia**: Test Pyramid (87% unit, 13% integration)

```
395 tests (100% passing)
├── Unit: 341 (26 archivos)
│   ├── Domain: ~220
│   ├── Application: ~78
│   └── Infrastructure: ~40
└── Integration: 54 (8 archivos)
```

**Cobertura**: >90% en lógica de negocio
**Performance**: ~13s (paralelización con pytest-xdist)

> ADR: [003](architecture/decisions/ADR-003-testing-strategy.md)

---

## Referencias ADRs

**Fundación**: [001](architecture/decisions/ADR-001-clean-architecture.md), [004](architecture/decisions/ADR-004-tech-stack.md)

**Patrones**: [002](architecture/decisions/ADR-002-value-objects.md), [005](architecture/decisions/ADR-005-repository-pattern.md), [006](architecture/decisions/ADR-006-unit-of-work-pattern.md), [007](architecture/decisions/ADR-007-domain-events-pattern.md)

**Infra**: [009](architecture/decisions/ADR-009-docker-for-development-environment.md), [010](architecture/decisions/ADR-010-alembic-for-database-migrations.md)

**Features**: [011](architecture/decisions/ADR-011-application-layer-use-cases.md), [012](architecture/decisions/ADR-012-composition-root.md), [013](architecture/decisions/ADR-013-external-services-pattern.md), [014](architecture/decisions/ADR-014-handicap-management-system.md), [015](architecture/decisions/ADR-015-session-management-progressive-strategy.md)

---

## 📊 Métricas del Proyecto

**Última actualización**: 9 Nov 2025

### Testing

| Métrica | Valor |
|---------|-------|
| Tests totales | 395 (100% passing) |
| Tests unitarios | 341 (26 archivos) |
| Tests integración | 54 (8 archivos) |
| Cobertura | >90% |
| Tiempo ejecución | ~13s (paralelo) |

### Progreso de Módulos

| Módulo | Estado | Tests | Endpoints |
|--------|--------|-------|-----------|
| User | ✅ Completo + Auth | 341+ | 9 |
| Tournament | 🚧 En desarrollo | 0 | 0 |
| Team | ⏳ Pendiente | 0 | 0 |

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

### API Endpoints Activos (9)

| Endpoint | Método | Auth | Status |
|----------|--------|------|--------|
| `/api/v1/auth/register` | POST | No | ✅ Activo |
| `/api/v1/auth/login` | POST | No | ✅ Activo |
| `/api/v1/auth/logout` | POST | JWT | ✅ Activo |
| `/api/v1/users/profile` | PATCH | JWT | ✅ Activo |
| `/api/v1/users/security` | PATCH | JWT | ✅ Activo |
| `/api/v1/users/search` | GET | JWT | ✅ Activo |
| `/api/v1/handicaps/update` | POST | JWT | ✅ Activo |
| `/api/v1/handicaps/update-manual` | POST | JWT | ✅ Activo |
| `/api/v1/handicaps/update-multiple` | POST | JWT | ✅ Activo |

### External Services Implementados (18 tests)

- **RFEGHandicapService** (5 tests integración) - Web scraping RFEG real
- **MockHandicapService** (13 tests) - Mock determinístico para testing
