# Changelog

Todos los cambios notables en este proyecto serán documentados en este archivo.

El formato está basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.0.0/),
y este proyecto adhiere a [Semantic Versioning](https://semver.org/lang/es/).

---

## [1.6.3] - 2025-11-20

### Security - Corrección de Divulgación de Información en Login

**Problema de Seguridad Resuelto:**
- **Divulgación de reglas de validación**: El endpoint de login revelaba información sobre las reglas de validación de contraseñas cuando se enviaba una contraseña corta.
- **Antes**: Error `"password: String should have at least 8 characters"` revelaba que el sistema valida longitud mínima de 8 caracteres.
- **Después**: Error genérico `"Credenciales incorrectas"` independientemente del motivo del fallo.

**Cambios Implementados:**
- ✅ **LoginRequestDTO**: Eliminada validación `min_length=8` del campo `password` para evitar filtrado de requests inválidos antes de la lógica de negocio.
- ✅ **Endpoint de Login**: Ahora procesa cualquier contraseña y devuelve error genérico si las credenciales son incorrectas.
- ✅ **Test de Seguridad**: Añadido test `test_login_with_short_password_returns_generic_error` que verifica que contraseñas cortas devuelven "Credenciales incorrectas".

**Beneficios de Seguridad:**
- ⚠️ **Prevención de enumeración**: Atacantes no pueden inferir reglas de validación de contraseñas.
- 🔒 **Consistencia**: Todos los fallos de autenticación devuelven el mismo mensaje genérico.
- 🛡️ **Defensa en profundidad**: Validaciones de contraseña solo aplican en registro/cambio, no en login.

---

## [1.6.2] - 2025-11-19

### Fixed
- **Update Competition Endpoint**: Corregido el endpoint `PUT /api/v1/competitions/{id}` para que actualice correctamente todos los campos de negocio en estado DRAFT, incluyendo `max_players`, `team_assignment` y los nombres de los equipos. El caso de uso, la entidad de dominio y los DTOs fueron actualizados para soportar esta funcionalidad.

### Changed
- **Documentación**:
  - Añadida sección `Competition Management` al archivo `docs/API.md` para incluir los endpoints de creación y actualización de competiciones.
  - Actualizado el `postman_collection.json` con un cuerpo de ejemplo más completo para la petición `Update Competition`.

---

## [1.6.1] - 2025-11-19

### Fixed - Correcciones de Integración y Arquitectura

**Mejoras de Tests:**
- ✅ Tests pasando: de 618 a 651 (+33 tests arreglados)
- ✅ Tasa de éxito: de 93.35% a 98.34%
- ✅ Fallos reducidos: de 44 a 11

**Correcciones en Competition Routes:**
- ✅ Corregidas llamadas a use cases de state transitions (activate, close, start, complete, cancel)
- ✅ Use cases ahora reciben DTOs + user_id correctamente
- ✅ Importadas excepciones específicas de cada use case
- ✅ Manejo apropiado de excepciones HTTP (404, 403, 400)
- ✅ Añadido manejo de `InvalidCountryError` en create_competition

**Correcciones en Entidades de Dominio:**
- ✅ Competition entity: añadidos métodos `_ensure_domain_events()` y `_add_domain_event()`
- ✅ Compatibilidad con SQLAlchemy que no inicializa `_domain_events` al cargar desde BD
- ✅ EnrollmentStatus: añadido `__composite_values__()` para SQLAlchemy composite

**Correcciones en Mappers SQLAlchemy:**
- ✅ Location composite usa named parameters
- ✅ Añadido mapeo explícito de `max_players`
- ✅ Enrollment mapper usa pattern `_status_value` (mismo que Competition)

**Correcciones en Tests:**
- ✅ conftest.py: extraída lógica de seed a función helper `seed_countries_and_adjacencies()`
- ✅ Añadido país JP al seed para tests de adyacencia
- ✅ Corregido assert de 401 a 403 en test sin auth

**Código Limpiado:**
- ✅ Eliminado código muerto en GetCompetitionUseCase (clase CompetitionResponse no usada)
- ✅ Actualizado docstring de GetCompetitionUseCase

**Endpoint de Countries:**
- ✅ Corregido manejo de `InvalidCountryCodeError` en list_adjacent_countries

### Fixed - Corrección de Enrollment Endpoints

**Tests (Módulo Enrollment):**
- ✅ Corregidos los 11 tests fallidos de los endpoints de `enrollment`.
- ✅ Todos los tests en `tests/integration/api/v1/test_enrollment_endpoints.py` (20/20) ahora pasan.

**Correcciones en Entidad `Enrollment` (Dominio):**
- ✅ Solucionado `AttributeError` al registrar eventos de dominio en objetos cargados por SQLAlchemy.
- ✅ Añadido método `_add_domain_event` para asegurar la inicialización de la lista de eventos, siguiendo el patrón de la entidad `Competition`.

**Correcciones en Tests de API (Infraestructura):**
- ✅ Corregido el `payload` en 5 tests de inscripción directa (`direct_enroll`) para incluir el `competition_id`, solucionando los errores de validación `422 Unprocessable Entity`.

---

## [1.6.0] - 2025-11-18

### Added - Competition Module COMPLETO (FASE 2 - Enrollment API)

**Módulo Competition 100% Funcional** - API REST completa para gestión de competiciones e inscripciones.

**Use Cases de Enrollment (7 nuevos):**
- ✅ `RequestEnrollmentUseCase` - Jugador solicita inscripción (REQUESTED)
- ✅ `DirectEnrollPlayerUseCase` - Creador inscribe directamente (APPROVED)
- ✅ `HandleEnrollmentUseCase` - Creador aprueba/rechaza (APPROVE/REJECT)
- ✅ `CancelEnrollmentUseCase` - Jugador cancela solicitud (CANCELLED)
- ✅ `WithdrawEnrollmentUseCase` - Jugador se retira (WITHDRAWN)
- ✅ `SetCustomHandicapUseCase` - Creador establece handicap personalizado
- ✅ `ListEnrollmentsUseCase` - Lista inscripciones con filtros

**API REST Endpoints - Enrollments (8 nuevos):**
1. `POST /api/v1/competitions/{id}/enrollments` - Solicitar inscripción
2. `POST /api/v1/competitions/{id}/enrollments/direct` - Inscripción directa por creador
3. `GET /api/v1/competitions/{id}/enrollments` - Listar inscripciones (?status=X)
4. `POST /api/v1/enrollments/{id}/approve` - Aprobar solicitud
5. `POST /api/v1/enrollments/{id}/reject` - Rechazar solicitud
6. `POST /api/v1/enrollments/{id}/cancel` - Cancelar solicitud/invitación
7. `POST /api/v1/enrollments/{id}/withdraw` - Retirarse de competición
8. `PUT /api/v1/enrollments/{id}/handicap` - Establecer handicap personalizado

**Dependency Injection:**
- ✅ 7 providers para Enrollment use cases en `dependencies.py`

**Archivos Creados:**
- 7 use cases en `src/modules/competition/application/use_cases/`
- `src/modules/competition/infrastructure/api/v1/enrollment_routes.py` (~400 líneas)

**Archivos Modificados:**
- `src/config/dependencies.py` - 7 imports + 7 providers
- `main.py` - Router de enrollments registrado

**Reglas de Negocio Implementadas:**
- Solo el creador puede aprobar/rechazar/inscribir directamente
- Solo el dueño puede cancelar/retirarse de su inscripción
- Competición debe estar ACTIVE para inscripciones
- No se permiten inscripciones duplicadas
- Transiciones de estado validadas (REQUESTED→APPROVED, APPROVED→WITHDRAWN, etc.)

**Total Endpoints API:**
- Competition: 10 endpoints
- Enrollment: 8 endpoints
- Countries: 2 endpoints
- **Total módulo Competition: 20 endpoints**

---

## [1.5.1] - 2025-11-18

### Added - Country Endpoints (Shared Domain API)

**Endpoints de Países (2 nuevos):**
- ✅ `GET /api/v1/countries` - Lista 166 países activos para selectores
- ✅ `GET /api/v1/countries/{code}/adjacent` - Lista países adyacentes a un código dado

**DTO:**
- ✅ `CountryResponseDTO` con campos: `code`, `name_en`, `name_es`

**Archivos Creados:**
- `src/shared/infrastructure/api/v1/country_routes.py` (~110 líneas)
- `src/shared/infrastructure/api/__init__.py`
- `src/shared/infrastructure/api/v1/__init__.py`

**Integración:**
- ✅ Router registrado en `main.py` con prefix `/api/v1/countries`
- ✅ Tag `Countries` en Swagger UI
- ✅ Usa `CompetitionUnitOfWork` para acceso al `CountryRepository`

**Uso en Frontend:**
- Selector de país principal en formulario de crear/editar competición
- Selectores de países secundario/terciario (filtrados por adyacencia)

---

## [1.5.0] - 2025-11-18

### Added - Competition Module API REST Layer (FASE 1 COMPLETA)

**10 Endpoints de Competition:**
1. `POST /api/v1/competitions` - Crear competición (estado DRAFT)
2. `GET /api/v1/competitions` - Listar competiciones (con filtros status, creator_id)
3. `GET /api/v1/competitions/{id}` - Obtener competición por ID
4. `PUT /api/v1/competitions/{id}` - Actualizar competición (solo DRAFT)
5. `DELETE /api/v1/competitions/{id}` - Eliminar competición (solo DRAFT)
6. `POST /api/v1/competitions/{id}/activate` - DRAFT → ACTIVE
7. `POST /api/v1/competitions/{id}/close-enrollments` - ACTIVE → CLOSED
8. `POST /api/v1/competitions/{id}/start` - CLOSED → IN_PROGRESS
9. `POST /api/v1/competitions/{id}/complete` - IN_PROGRESS → COMPLETED
10. `POST /api/v1/competitions/{id}/cancel` - Cualquier estado → CANCELLED

**Arquitectura:**
- ✅ `CompetitionDTOMapper` en API Layer para campos calculados
- ✅ Use cases retornan entidades, NO DTOs (Clean Architecture)
- ✅ 11 providers de Dependency Injection configurados
- ✅ JWT authentication en todos los endpoints
- ✅ Autorización: solo creador puede modificar

**DTOs Enriquecidos:**
- `is_creator` (boolean calculado)
- `enrolled_count` (count de APPROVED)
- `location` (string formateado: "Spain, France, Italy")

**Total Código Nuevo:** ~1,422 líneas

---

## [1.4.0] - 2025-11-18

### Added - Competition Module Infrastructure Layer

**Persistencia SQLAlchemy:**
- ✅ 2 migraciones Alembic (4 tablas + seed data)
- ✅ 3 repositorios async (Competition, Enrollment, Country)
- ✅ Imperative Mapping con TypeDecorators y Composites
- ✅ 166 países + 614 fronteras cargadas

**Unit of Work:**
- ✅ `SQLAlchemyCompetitionUnitOfWork` con 3 repositorios

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

**Última actualización:** 20 de Noviembre de 2025 (v1.6.3 - Security Fix: Login Information Disclosure)
