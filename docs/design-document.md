# Design Document - Ryder Cup Manager

**v2.0** · 9 Nov 2025 · En desarrollo

---

## Resumen

Sistema de torneos de golf amateur formato Ryder Cup.

**Stack**: Python 3.12+, FastAPI, PostgreSQL, Clean Architecture + DDD

**Features**:
- User management + JWT auth
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
- Events: `UserRegistered`, `HandicapUpdated`
- Repos: `UserRepositoryInterface`
- Services: `HandicapService` (interface)

**Application**:
- Use Cases: `RegisterUser`, `UpdateHandicap`, `UpdateHandicapManually`, `UpdateMultipleHandicaps`, `FindUser`
- DTOs: Request/Response
- Handlers: `UserRegisteredEventHandler`

**Infrastructure**:
- Routes: `/auth/*`, `/handicaps/*`, `/users/*`
- Repos: `SQLAlchemyUserRepository`
- External: `RFEGHandicapService`, `MockHandicapService`

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
    updated_at TIMESTAMP NOT NULL
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

### Handicaps
- `POST /api/v1/handicaps/update` - RFEG lookup + fallback
- `POST /api/v1/handicaps/update-manual` - Manual directo
- `POST /api/v1/handicaps/update-multiple` - Batch update

### Users
- `GET /api/v1/users/search` - Buscar por email o nombre

> Detalle: [API.md](API.md)

---

## Testing

**Estrategia**: Test Pyramid (90% unit, 10% integration)

```
330 tests (100% passing)
├── Unit: 302
│   ├── Domain: ~200
│   ├── Application: ~50
│   └── Infrastructure: ~50
└── Integration: 28
```

**Cobertura**: >90% en lógica de negocio
**Performance**: ~8s (paralelización con pytest-xdist)

> ADR: [003](architecture/decisions/ADR-003-testing-strategy.md)

---

## Referencias ADRs

**Fundación**: [001](architecture/decisions/ADR-001-clean-architecture.md), [004](architecture/decisions/ADR-004-tech-stack.md)

**Patrones**: [002](architecture/decisions/ADR-002-value-objects.md), [005](architecture/decisions/ADR-005-repository-pattern.md), [006](architecture/decisions/ADR-006-unit-of-work-pattern.md), [007](architecture/decisions/ADR-007-domain-events-pattern.md)

**Infra**: [009](architecture/decisions/ADR-009-docker-for-development-environment.md), [010](architecture/decisions/ADR-010-alembic-for-database-migrations.md)

**Features**: [011](architecture/decisions/ADR-011-application-layer-use-cases.md), [012](architecture/decisions/ADR-012-composition-root.md), [013](architecture/decisions/ADR-013-external-services-pattern.md), [014](architecture/decisions/ADR-014-handicap-management-system.md)

---

## Métricas Actuales

| Métrica | Valor |
|---------|-------|
| Tests | 330 (100% pass) |
| Cobertura | >90% |
| Módulos | 1/3 completo |
| Endpoints | 5 activos |
| Integraciones | 1 (RFEG) |
| Líneas código | ~15,000 |
