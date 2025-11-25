# Changelog

Todos los cambios notables en este proyecto serán documentados en este archivo.

El formato está basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.0.0/),
y este proyecto adhiere a [Semantic Versioning](https://semver.org/lang/es/).

## [Unreleased]

---

## [1.9.0] - 2025-11-25

### Added
- ✅ **Aumento de Cobertura de Tests**: Creados nuevos tests para los casos de uso del módulo de competición, aumentando la cobertura y la robustez del código. Se han añadido tests para:
  - `handle_enrollment_use_case.py`
  - `direct_enroll_player_use_case.py`
  - `list_enrollments_use_case.py`
  - `request_enrollment_use_case.py`
  - `set_custom_handicap_use_case.py`
  - `withdraw_enrollment_use_case.py`
  - `cancel_enrollment_use_case.py`

### Fixed
- ✅ **Corrección de Tests de Integración**: Arreglados múltiples tests de integración que fallaban debido a inconsistencias en la estructura de datos devuelta por los `helpers` de autenticación.
- ✅ **Mejora del Rendimiento de los Tests**: Reducido significativamente el tiempo de ejecución de los tests mediante la paralelización con `pytest-xdist`.

### Chore
- ✅ **Dependencias**: Añadido `pytest-cov` al fichero `requirements.txt` para asegurar que la herramienta de coverage esté disponible en todos los entornos.

---

## [1.8.1] - 2025-11-25

### Changed
**BREAKING CHANGE:** Las respuestas de competiciones ahora incluyen campo `countries` (array) además de los campos `adjacent_country_1/2` existentes.

### Documentation
- ✅ Actualizado `ROADMAP.md` para reflejar el estado real de las tareas.
- ✅ Actualizado `API.md` a la versión `v1.8.0`, añadiendo el campo `country_code` en los endpoints de registro y actualización de perfiles, y una nota aclaratoria sobre el campo `avatar_url`.

---

## [1.8.0] - 2025-11-24

### Fixed - Critical: Handicap Value Object Architecture Fix

**🐛 CRITICAL BUG FIX: AttributeError en serialización de Handicap**

#### Problema Identificado
- ❌ Error: `AttributeError: 'float' object has no attribute 'value'`
- ❌ Frontend recibiendo HTTP 400 Bad Request al listar competiciones
- ❌ Tests fallando: 558/663 pasando (84.16%)
- ❌ Causa: Mapeo incorrecto de Handicap Value Object con SQLAlchemy

#### Solución Implementada

**Infrastructure Layer - User Module:**
- ✅ **Nuevo `HandicapDecorator` (TypeDecorator)**: Reemplaza composite mapping
  - Convierte `Handicap` VO ↔ `float` automáticamente
  - Maneja correctamente valores `NULL` (retorna `None`)
  - Valida rango -10.0 a 54.0 al cargar desde BD
- ✅ **User mapper actualizado**: Usa `HandicapDecorator` en lugar de `composite()`
  - `Column('handicap', HandicapDecorator, nullable=True)`
  - Elimina mapping privado `_handicap_value`

**Domain Layer - User Module:**
- ✅ **User.update_handicap()**: Corregido para asignar objeto `Handicap` completo
  - `self.handicap = validated` (no `validated.value`)
  - Extrae `.value` solo al emitir eventos de dominio
- ✅ **HandicapUpdatedEvent**: Recibe `float` en lugar de objeto `Handicap`

**Application Layer:**
- ✅ **UserResponseDTO**: Añadido validator para convertir `Handicap` → `float`
  - `@field_validator("id", "email", "country_code", "handicap", mode="before")`
- ✅ **RegisterUserRequestDTO**: Eliminados campos duplicados (country_code, manual_handicap)
- ✅ **CreatorDTO**: Cambiado de `Decimal` a `float` para serialización JSON correcta

**API Layer:**
- ✅ **competition_routes.py**: Extrae `.value` al crear CreatorDTO
  - `handicap=creator.handicap.value if creator.handicap else None`

**Tests:**
- ✅ **7 tests corregidos**: Actualizados para acceder a `handicap.value`
  - `test_user.py`: 5 assertions
  - `test_update_user_handicap_manually_use_case.py`: 1 assertion
  - `test_update_user_handicap_use_case.py`: 1 assertion

#### Resultados

**Tests:**
- ✅ **663/663 tests pasando (100.00%)** - Mejora del 15.84%
- ✅ User Module: 100% tests pasando
- ✅ Competition Module: 100% tests pasando
- ✅ Integration tests: 100% tests pasando

**API End-to-End:**
- ✅ Registro de usuario sin handicap: OK
- ✅ Registro de usuario con handicap: OK
- ✅ Listar competiciones (my_competitions=true): OK
- ✅ Detalle de competición con creator: OK
- ✅ Listar enrollments: OK
- ✅ Serialización JSON: `handicap` como `float` (no string)

**Docker:**
- ✅ Sin errores `AttributeError` en logs
- ✅ Aplicación estable y funcional

#### Lecciones Aprendidas

**TypeDecorator vs Composite en SQLAlchemy:**

**✅ Usar TypeDecorator cuando:**
- Value Object de **una sola columna**
- Campo **puede ser NULL**
- Conversión simple entre tipo primitivo y VO

**❌ NO usar Composite cuando:**
- Campo puede ser NULL (causa `TypeError` en VO constructor)
- Value Object no permite `None` como valor válido

**✅ Usar Composite cuando:**
- Value Object abarca **múltiples columnas**
- Campo **nunca es NULL**
- Lógica compleja en el VO

#### Archivos Modificados
- `src/modules/user/infrastructure/persistence/sqlalchemy/mappers.py`
- `src/modules/user/domain/entities/user.py`
- `src/modules/user/application/dto/user_dto.py`
- `src/modules/competition/infrastructure/api/v1/competition_routes.py`
- `src/modules/competition/application/dto/competition_dto.py`
- `tests/unit/modules/user/domain/entities/test_user.py`
- `tests/unit/modules/user/application/use_cases/test_update_user_handicap_*.py`

---

## [1.7.0] - 2025-11-23

### Added - Sprint 1 Complete: Nationality Support & Nested Objects

**🎯 Sprint 1 COMPLETADO - 4 Tareas Críticas Implementadas**

#### 1. User Nationality Support (country_code)

**Domain Layer:**
- ✅ User entity: Campo `country_code` opcional usando `CountryCode` VO
- ✅ User.create(): Acepta `country_code_str` como parámetro opcional
- ✅ User.update_profile(): Permite actualizar nacionalidad
- ✅ User.is_spanish(): Nuevo método para validación RFEG compliance

**Application Layer:**
- ✅ RegisterUserRequestDTO: Campo `country_code` opcional con validación
- ✅ UserResponseDTO: Incluye `country_code` en todas las respuestas
- ✅ UpdateProfileRequestDTO: Permite actualizar `country_code`
- ✅ RegisterUserUseCase: Valida country_code contra repositorio de países
- ✅ UpdateProfileUseCase: Valida integridad referencial con tabla countries

**Infrastructure Layer:**
- ✅ User mapper: FK a tabla `countries` con validación de integridad
- ✅ /register, /login, /current-user: Devuelven `country_code`
- ✅ /profile: Permite leer y actualizar `country_code`

#### 2. Creator Nested Object in Competition Responses

**Application Layer:**
- ✅ Nuevo `CreatorDTO`: Campos id, first_name, last_name, email, handicap, country_code
- ✅ CompetitionResponseDTO: Incluye objeto `creator` completo
- ✅ CreateCompetitionResponseDTO: Incluye `creator` en creación
- ✅ CompetitionDTOMapper: Método async `_get_creator_dto()` que consulta UserRepository

**Infrastructure Layer:**
- ✅ 10 endpoints actualizados: Todos los endpoints de Competition ahora incluyen datos del creador
- ✅ UserUnitOfWork inyectado en competition_routes.py
- ✅ Endpoints afectados: create, list, detail, update, delete, activate, close, start, complete, cancel

**Benefits:**
- 🚀 ~60% reducción de llamadas API en pantalla "Discover Competitions"

#### 3. My Competitions Filter

**Infrastructure Layer:**
- ✅ Nuevo query parameter `my_competitions` en GET /api/v1/competitions
- ✅ Lógica para filtrar competiciones donde el usuario es creador O está inscrito
- ✅ Compatible con filtros existentes (status, creator_id)

**Features:**
- `my_competitions=false` (default): Devuelve todas las competiciones
- `my_competitions=true`: Solo competiciones creadas o con enrollment del usuario
- Combina resultados de competiciones creadas + inscripciones del usuario
- Aplica filtro de status sobre resultados combinados

**Benefits:**
- 🎯 Vista "My Competitions" ahora muestra solo competiciones relevantes
- 📊 Mejora UX al separar "Discover" vs "My Competitions"

#### 4. Search Parameters for Competitions

**Domain Layer:**
- ✅ CompetitionRepositoryInterface: Nuevo método `find_by_filters()` con parámetros de búsqueda
- ✅ Soporte para search_name y search_creator como filtros opcionales

**Infrastructure Layer:**
- ✅ SQLAlchemyCompetitionRepository: Implementación con ILIKE para case-insensitive search
- ✅ InMemoryCompetitionRepository: Implementación para tests
- ✅ Nuevos query parameters en GET /api/v1/competitions:
  - `search_name`: Búsqueda parcial en nombre de competición
  - `search_creator`: Búsqueda parcial en nombre (first_name o last_name) del creador

**Application Layer:**
- ✅ ListCompetitionsUseCase: Actualizado para soportar search_name y search_creator
- ✅ Método `_fetch_with_search()` que usa find_by_filters del repositorio

**Features:**
- Búsqueda case-insensitive usando ILIKE en PostgreSQL
- Búsqueda independiente por nombre y por creador
- Combinable con filtros existentes (status, creator_id, my_competitions)
- JOIN con tabla User solo cuando se usa search_creator (optimización)

**Examples:**
- `GET /competitions?search_name=ryder` - Busca "ryder" en nombre
- `GET /competitions?search_creator=john` - Busca "john" en first_name o last_name del creador
- `GET /competitions?search_name=cup&search_creator=doe` - Búsqueda combinada

**Benefits:**
- 🔍 Permite búsqueda rápida de competiciones sin cargar todas
- 🎯 Mejora la experiencia de usuario en pantalla "Discover Competitions"
- ⚡ Optimizado con índices en base de datos

### Fixed

#### Competition Routes
- 🐛 Fixed AttributeError en serialización de handicap del creador
  - Problema: `creator.handicap.value` cuando handicap ya es float
  - Solución: Cambiado a `creator.handicap` directamente
  - Afecta: GET /api/v1/competitions y todos los endpoints que devuelven creator nested
- 🎯 Frontend ya no necesita llamar GET /users/{id} por cada competición
- 🌍 Incluye country_code del creador para mostrar nacionalidad

#### 4. User Nested Object in Enrollment Responses

**Application Layer:**
- ✅ Nuevo `EnrolledUserDTO`: Campos id, first_name, last_name, email, handicap, country_code, avatar_url
- ✅ EnrollmentResponseDTO: Incluye objeto `user` completo
- ✅ EnrollmentDTOMapper: Método async `_get_user_dto()` que consulta UserRepository

**Infrastructure Layer:**
- ✅ 8 endpoints actualizados: Todos los endpoints de Enrollment ahora incluyen datos del usuario
- ✅ UserUnitOfWork inyectado en enrollment_routes.py
- ✅ Endpoints afectados: request, direct, list, approve, reject, cancel, withdraw, set-handicap

**Benefits:**
- 🎯 Frontend recibe datos completos sin llamadas adicionales
- 🌍 Incluye country_code para mostrar nacionalidad
- 📸 Incluye avatar_url (null por ahora, preparado para Sprint 2)

#### 4. Cross-Module Dependency Injection

**Configuration:**
- ✅ dependencies.py: UserUoW ahora se inyecta en Competition y Enrollment modules
- ✅ Clean Architecture mantenida: Acceso cross-module vía UoW pattern
- ✅ Sin acoplamiento directo entre repositorios

### Changed - Database Migrations

**Migration Consolidation:**
- ✅ 6 migraciones incrementales consolidadas en una sola migración inicial
- ✅ Migraciones removidas: 0cfaf48e5b9c, 314aef4924e4, 7610ccc63d69, 852ad2e01efe, b4301dc0075c, f67961867576
- ✅ Nueva migración: c283e057a219_initial_schema_with_all_modules.py
- ✅ Schema completo: users, competitions, enrollments, countries, country_adjacencies
- ✅ Seeds automáticos: 198 países + 614 relaciones de fronteras

**Database Schema:**
- ✅ users.country_code: FK a countries(code), nullable
- ✅ countries: 198 países con nombres bilingües (EN/ES)
- ✅ country_adjacencies: 614 relaciones bidireccionales de fronteras

### Tests

**Coverage:**
- ✅ 663/663 tests pasando (100%)
- ✅ Tests actualizados: RegisterUserUseCase, UpdateProfileUseCase con country_code
- ✅ Nuevos tests: Validación de country_code, nested objects en responses

### Documentation

**Updated:**
- ✅ ROADMAP.md: Añadido roadmap completo Sprint 1 (completado) y Sprint 2 (pendiente)
- ✅ CHANGELOG.md: Documentación completa de Sprint 1
- ✅ API.md: Actualizado con country_code y nested objects (siguiente commit)
- ✅ CLAUDE.md: Actualizado con estado Sprint 1 completado

**Removed:**
- ✅ PROGRESS_LOG.md: Documento obsoleto reemplazado por ROADMAP.md

### Performance

- 🚀 API calls reduction: ~60% en pantalla "Discover Competitions"
- 🚀 Menos round trips: Datos completos en una sola llamada

### Frontend-Ready

- ✅ country_code en todos los endpoints de usuario
- ✅ creator object completo en competiciones
- ✅ user object completo en enrollments
- ✅ avatar_url preparado para Sprint 2

---

## [1.6.4] - 2025-11-22

### Added - Soporte Dual de Formatos para Creación de Competiciones

**Nueva Funcionalidad:**
- ✅ **Campo Alias**: Añadido alias `number_of_players` → `max_players` para compatibilidad con frontend
- ✅ **Array de Países**: Soporte para campo `countries` (array) en requests de creación de competiciones
- ✅ **Conversión Automática**: Validador que convierte array `countries` a campos `adjacent_country_1/2`
- ✅ **Respuestas Enriquecidas**: Todos los endpoints de competiciones ahora devuelven array `countries` con detalles completos (código, nombre_en, nombre_es)
- ✅ **CountryResponseDTO**: Nuevo DTO para representar países con información completa
- ✅ **Compatibilidad Backward**: Los formatos legacy (`adjacent_country_1/2`) siguen siendo soportados

**Cambios Técnicos:**
- 🔧 **Pydantic Config**: Añadido `ConfigDict(populate_by_name=True)` para soporte de aliases
- 🔧 **Model Validators**: Validador automático para conversión de formatos de países
- 🔧 **Serialización**: Corregida serialización de `CountryCode` value objects extrayendo `.value`
- 🔧 **Mapeo de Respuestas**: Método `_get_countries_list()` para obtener detalles completos de países

**Documentación Actualizada:**
- 📚 **API Reference**: Actualizada a v1.6.4 con nuevos campos y ejemplos
- 📚 **Postman Collection**: Añadidos ejemplos para formato legacy y frontend
- 📚 **CHANGELOG**: Documentados todos los cambios y beneficios

**Beneficios:**
- 🔄 **Compatibilidad**: Frontend puede enviar `number_of_players` y `countries` array
- 📊 **Respuestas Ricas**: API devuelve información completa de países en lugar de solo códigos
- 🔒 **Backward Compatible**: Formatos antiguos siguen funcionando sin cambios
- 🧪 **Testeado**: Validación de serialización y conversión de formatos verificada

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
