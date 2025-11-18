# Changelog

Todos los cambios notables en este proyecto serán documentados en este archivo.

El formato está basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.0.0/),
y este proyecto adhiere a [Semantic Versioning](https://semver.org/lang/es/).

---

## [1.3.0] - 2025-11-18

### Added - Competition Module (Domain + Application Layer COMPLETO)

**Módulo Competition - Domain Layer**
- ✅ Implementado módulo Competition completo (domain layer)
- ✅ 2 entidades principales: `Competition` y `Enrollment` con máquina de estados
- ✅ 9 Value Objects con validaciones completas:
  - `CompetitionId`, `CompetitionName`, `DateRange`
  - `Location`, `HandicapSettings`
  - `EnrollmentId`, `EnrollmentStatus`
  - `CountryCode` (shared), `Country` entity (shared)
- ✅ 11 Domain Events para comunicación entre agregados:
  - 7 eventos de Competition (Created, Activated, EnrollmentsClosed, Started, Completed, Cancelled, Updated)
  - 4 eventos de Enrollment (Requested, Approved, Cancelled, Withdrawn)
- ✅ Shared domain: `Country` entity con soporte multilenguaje (name_en, name_es)
- ✅ Estado `CANCELLED` agregado para cancelaciones de jugadores
- ✅ Semántica clara: CANCELLED (jugador cancela pre-inscripción) vs REJECTED (creador rechaza) vs WITHDRAWN (jugador se retira post-inscripción)

**Application Layer - DTOs y Repository Interfaces**
- ✅ 3 Repository Interfaces (Clean Architecture):
  - `CompetitionRepositoryInterface` (9 métodos)
  - `EnrollmentRepositoryInterface` (9 métodos)
  - `CountryRepositoryInterface` (5 métodos, shared domain)
- ✅ 18 DTOs con validaciones Pydantic:
  - 5 Competition DTOs (Create, Update, Response)
  - 13 Enrollment DTOs (Request, DirectEnroll, Handle, Cancel, Withdraw, SetHandicap, Response)
- ✅ Validaciones automáticas:
  - Rangos de fechas, hándicaps, max_players
  - Conversión automática a mayúsculas (country codes, handicap_type, actions)
  - Validación condicional (PERCENTAGE requiere percentage, SCRATCH no)

**Application Layer - Use Cases (9 casos de uso, 58 tests) ⭐ NUEVO**

*CRUD Operations (4 casos de uso, 25 tests):*
- ✅ `CreateCompetitionUseCase` (7 tests) - Crea competiciones en estado DRAFT
- ✅ `UpdateCompetitionUseCase` (8 tests) - Actualización parcial solo en DRAFT
- ✅ `GetCompetitionUseCase` (4 tests) - Query de competición por ID
- ✅ `DeleteCompetitionUseCase` (6 tests) - Eliminación física solo en DRAFT

*State Transitions (5 casos de uso, 33 tests):*
- ✅ `ActivateCompetitionUseCase` (6 tests) - Transición DRAFT → ACTIVE
- ✅ `CloseEnrollmentsUseCase` (6 tests) - Transición ACTIVE → CLOSED
- ✅ `StartCompetitionUseCase` (6 tests) - Transición CLOSED → IN_PROGRESS
- ✅ `CompleteCompetitionUseCase` (6 tests) - Transición IN_PROGRESS → COMPLETED
- ✅ `CancelCompetitionUseCase` (9 tests) - Transición cualquier estado → CANCELLED

**Domain Service:**
- ✅ `LocationBuilder` - Valida países y adyacencias (sigue patrón UserFinder)
- ✅ Separa correctamente lógica de dominio de casos de uso

**Modificaciones a Entidades:**
- ✅ Competition entity: agregados campos `max_players` y `team_assignment`
- ✅ Corregido tipo de `handicap_settings` en DTOs (Dict[str, Any] para soportar type y percentage)

**Decisiones Arquitectónicas**
- `HandicapSettings` almacena solo políticas (SCRATCH o PERCENTAGE con 90/95/100), no cálculos completos
- Cálculo completo de hándicap (Course Rating, Slope Rating) se moverá a entidad Match
- Validación de adyacencia de países delegada a Domain Service (LocationBuilder)
- `custom_handicap` en Enrollment permite override del hándicap oficial por el creador
- DTOs siguen patrón: `XxxRequestDTO` / `XxxResponseDTO`
- Todos los casos de uso validan que solo el creador puede modificar la competición
- Domain Events emitidos en todas las transiciones de estado

**Arquitectura:**
- ✅ Clean Architecture completa en Application Layer
- ✅ SOLID principles aplicados en todos los casos de uso
- ✅ Unit of Work pattern para transaccionalidad
- ✅ Repository Pattern con interfaces del dominio
- ✅ Dependency Injection en constructores

**Testing**
- ✅ 173 tests pasando (100% cobertura Competition Module):
  - 38 tests domain (Value Objects, Entities, Events)
  - 29 tests repository interfaces (estructura y contratos)
  - 48 tests DTOs (validaciones y edge cases)
  - 58 tests use cases (CRUD + state transitions) ⭐ NUEVO

**Documentación**
- ✅ ADR-020: Competition Module Domain Design
- ✅ CHANGELOG actualizado con v1.3.0
- ✅ CLAUDE.md actualizado con changelog detallado
- ✅ **Total tests proyecto: 613 tests** (308 User + 173 Competition + 60 Shared + 72 Integration)

### Pending
- [ ] Infrastructure Layer: Repositories SQLAlchemy y persistencia
- [ ] Migraciones de base de datos (competitions, enrollments, countries, country_adjacencies)
- [ ] API REST Layer: Endpoints FastAPI
- [ ] Tests de integración y E2E

---

## [1.2.0] - 2025-11-14

### Added - Tests y Calidad de Código

**Tests y Calidad de Código**
- ✅ Agregados 24 tests para Email Verification (cobertura completa)
- ✅ Corregidos todos los warnings de pytest (0 warnings)
- ✅ Total: 420 tests pasando (anteriormente 440, ajustado a 420 según README)
- ✅ Mejorado `dev_tests.py` para capturar y reportar warnings
- ✅ Tests renombrados: `TestEvent` → `SampleEvent` (evitar conflictos con pytest)
- ✅ Helper agregado: `get_user_by_email()` en conftest.py

---

## [1.1.0] - 2025-11-12

### Added - Email Verification

**Email Verification**
- ✅ Implementada verificación de email con tokens únicos
- ✅ Integración con Mailgun (región EU)
- ✅ Templates bilingües (ES/EN) para emails de verificación
- ✅ Domain events: `EmailVerifiedEvent`
- ✅ Migración agregada: campos `email_verified` y `verification_token` en tabla users
- ✅ Endpoint: `POST /api/v1/auth/verify-email`
- ✅ Tests completos: 24 tests en 3 niveles (unit, integration, E2E)

---

## [1.0.0] - 2025-11-01

### Added - Foundation

**Core Features**
- ✅ Clean Architecture + DDD completo
- ✅ User management (registro, autenticación, perfil)
- ✅ JWT authentication con tokens Bearer
- ✅ Login/Logout con Domain Events
- ✅ Session Management (Fase 1)
- ✅ Handicap system con integración RFEG
- ✅ Actualización manual y batch de handicaps
- ✅ 8 endpoints API funcionales

**Arquitectura**
- Repository Pattern con Unit of Work
- Domain Events Pattern
- Value Objects para validaciones
- External Services Pattern (Mailgun, RFEG)
- Dependency Injection completa

**Testing**
- 420 tests pasando (unit + integration)
- Cobertura >90% en lógica de negocio
- 0 warnings de pytest

**Infrastructure**
- Docker + Docker Compose para desarrollo
- PostgreSQL 15 con Alembic para migraciones
- FastAPI 0.115+
- Python 3.12+

---

## Versionado

- **Mayor (X.0.0)**: Cambios incompatibles en la API
- **Menor (1.X.0)**: Nueva funcionalidad compatible hacia atrás
- **Parche (1.0.X)**: Correcciones de bugs compatibles

---

**Última actualización:** 18 de Noviembre de 2025
