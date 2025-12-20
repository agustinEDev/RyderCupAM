# Módulo: Competition Management

## 📋 Descripción

Módulo responsable de la gestión de torneos formato Ryder Cup, incluyendo inscripciones (enrollments), equipos y configuración de handicaps. Implementa Clean Architecture con DDD.

**📋 Ver API completa:** `docs/API.md`

---

## 🎯 Casos de Uso Implementados

### Competition Management (10 use cases)
1. **CreateCompetitionUseCase** - Crear torneo en estado DRAFT
2. **GetCompetitionUseCase** - Obtener detalles de un torneo
3. **ListCompetitionsUseCase** - Listar torneos con filtros
4. **UpdateCompetitionUseCase** - Actualizar torneo (solo DRAFT)
5. **DeleteCompetitionUseCase** - Eliminar torneo (solo DRAFT)
6. **ActivateCompetitionUseCase** - Transición DRAFT → ACTIVE
7. **CloseEnrollmentsUseCase** - Transición ACTIVE → CLOSED
8. **StartCompetitionUseCase** - Transición CLOSED → IN_PROGRESS
9. **CompleteCompetitionUseCase** - Transición IN_PROGRESS → COMPLETED
10. **CancelCompetitionUseCase** - Transición a CANCELLED desde cualquier estado

### Enrollment Management (7 use cases)
11. **RequestEnrollmentUseCase** - Solicitar inscripción (REQUESTED)
12. **DirectEnrollPlayerUseCase** - Inscripción directa por creador (APPROVED)
13. **ListEnrollmentsUseCase** - Listar inscripciones con filtros
14. **HandleEnrollmentUseCase** - Aprobar/rechazar solicitudes
15. **CancelEnrollmentUseCase** - Cancelar solicitud/invitación
16. **WithdrawEnrollmentUseCase** - Retirarse de competición
17. **SetCustomHandicapUseCase** - Establecer handicap personalizado

---

## 🗃️ Modelo de Dominio

### Entity: Competition (Agregado Raíz)

**Identificación:**
- `id`: CompetitionId (Value Object - UUID)

**Datos Principales:**
- `name`: CompetitionName (Value Object - 3-100 chars, unique)
- `dates`: DateRange (Value Object - start_date, end_date)
- `location`: Location (Value Object - hasta 3 países adyacentes)
- `creator_id`: UserId (Value Object - creador del torneo)
- `max_players`: int (2-100 jugadores)
- `status`: CompetitionStatus (enum - DRAFT/ACTIVE/CLOSED/IN_PROGRESS/COMPLETED/CANCELLED)

**Configuración de Handicap:**
- `handicap_settings`: HandicapSettings (Value Object)
  - `type`: HandicapType (SCRATCH o PERCENTAGE)
  - `percentage`: int (90/95/100, opcional si PERCENTAGE)

**Configuración de Equipos:**
- `team_assignment`: TeamAssignment (RANDOM o MANUAL)
- `team_1_name`: str (opcional, max 50)
- `team_2_name`: str (opcional, max 50)

**Timestamps:**
- `created_at`: datetime
- `updated_at`: datetime

### Entity: Enrollment (Agregado Secundario)

**Identificación:**
- `id`: EnrollmentId (Value Object - UUID)
- `competition_id`: CompetitionId
- `user_id`: UserId

**Estado y Configuración:**
- `status`: EnrollmentStatus (REQUESTED/INVITED/APPROVED/REJECTED/CANCELLED/WITHDRAWN)
- `custom_handicap`: float (opcional, -10.0 a 54.0)
- `team_id`: str (opcional, "1" o "2")

**Timestamps:**
- `created_at`: datetime
- `updated_at`: datetime

### Entity: Country (Shared Domain)

**Identificación:**
- `code`: CountryCode (Value Object - ISO 3166-1 alpha-2)

**Datos:**
- `name_en`: str (nombre en inglés)
- `name_es`: str (nombre en español)
- `active`: bool (si está disponible para selección)

---

## 🏗️ Value Objects Implementados

### Competition Module (9 VOs)
- `CompetitionId` - UUID único de la competición
- `CompetitionName` - Nombre validado (3-100 chars, unique)
- `DateRange` - Rango de fechas (start_date ≤ end_date)
- `Location` - Hasta 3 países adyacentes (main + 2 optional)
- `HandicapSettings` - Tipo de handicap + porcentaje
- `CompetitionStatus` - Estado del torneo (6 estados posibles)
- `EnrollmentId` - UUID único del enrollment
- `EnrollmentStatus` - Estado de la inscripción (6 estados posibles)
- `CountryCode` - Código ISO 3166-1 alpha-2 (shared)

---

## 🔄 Domain Events Implementados

### Competition Events (11 eventos)
1. `CompetitionCreatedEvent` - Torneo creado
2. `CompetitionUpdatedEvent` - Torneo actualizado
3. `CompetitionActivatedEvent` - Transición a ACTIVE
4. `EnrollmentsClosedEvent` - Transición a CLOSED
5. `CompetitionStartedEvent` - Transición a IN_PROGRESS
6. `CompetitionCompletedEvent` - Transición a COMPLETED
7. `CompetitionCancelledEvent` - Torneo cancelado
8. `CompetitionDeletedEvent` - Torneo eliminado

### Enrollment Events (4 eventos)
9. `EnrollmentRequestedEvent` - Solicitud de inscripción
10. `EnrollmentApprovedEvent` - Inscripción aprobada
11. `EnrollmentCancelledEvent` - Inscripción cancelada
12. `EnrollmentWithdrawnEvent` - Jugador retirado

---

## 🏛️ Arquitectura

### Repository Pattern

**Interfaces (Domain Layer):**
- `CompetitionRepositoryInterface` - CRUD de competiciones
  - find_by_id, find_by_creator, find_by_status, find_active_in_date_range
  - add, update, delete, exists_with_name, count_by_creator
- `EnrollmentRepositoryInterface` - CRUD de enrollments
  - find_by_id, find_by_competition, find_by_competition_and_status, find_by_user
  - add, update, exists_for_user_in_competition, count_approved, find_by_competition_and_team
- `CountryRepositoryInterface` - Consultas de países (shared)
  - find_by_code, find_all_active, are_adjacent, find_adjacent_countries, exists

**Implementaciones (Infrastructure Layer):**
- `SQLAlchemyCompetitionRepository` - Persistencia async con PostgreSQL
- `SQLAlchemyEnrollmentRepository` - Persistencia de enrollments
- `SQLAlchemyCountryRepository` - Consultas de países (seed data)

**📋 Ver implementación:** `src/modules/competition/infrastructure/persistence/sqlalchemy/`

### Unit of Work Pattern

**Interface (Domain Layer):**
```
CompetitionUnitOfWorkInterface
├── competitions: CompetitionRepositoryInterface
├── enrollments: EnrollmentRepositoryInterface
├── countries: CountryRepositoryInterface
├── async commit()
├── async rollback()
└── async __aenter__() / __aexit__()
```

**Implementación (Infrastructure Layer):**
- `SQLAlchemyCompetitionUnitOfWork` - Gestión de transacciones atómicas

---

## 📊 Esquema de Base de Datos

### Tabla: competitions
```sql
CREATE TABLE competitions (
    id UUID PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    country_code VARCHAR(2) REFERENCES countries(code),
    secondary_country_code VARCHAR(2) REFERENCES countries(code),
    tertiary_country_code VARCHAR(2) REFERENCES countries(code),
    max_players INTEGER NOT NULL CHECK (max_players BETWEEN 2 AND 100),
    handicap_type VARCHAR(20) NOT NULL,
    handicap_percentage INTEGER,
    team_assignment VARCHAR(20) NOT NULL,
    team_1_name VARCHAR(50),
    team_2_name VARCHAR(50),
    status VARCHAR(20) NOT NULL,
    creator_id UUID REFERENCES users(id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX idx_competitions_creator_id ON competitions(creator_id);
CREATE INDEX idx_competitions_status ON competitions(status);
CREATE INDEX idx_competitions_dates ON competitions(start_date, end_date);
```

### Tabla: enrollments
```sql
CREATE TABLE enrollments (
    id UUID PRIMARY KEY,
    competition_id UUID REFERENCES competitions(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    status VARCHAR(20) NOT NULL,
    custom_handicap DECIMAL(4,1),
    team_id VARCHAR(1),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE (competition_id, user_id)
);
CREATE INDEX idx_enrollments_competition_id ON enrollments(competition_id);
CREATE INDEX idx_enrollments_user_id ON enrollments(user_id);
CREATE INDEX idx_enrollments_status ON enrollments(status);
```

### Tabla: countries (Shared - Seed Data)
```sql
CREATE TABLE countries (
    code VARCHAR(2) PRIMARY KEY,
    name_en VARCHAR(100) NOT NULL,
    name_es VARCHAR(100) NOT NULL,
    active BOOLEAN DEFAULT TRUE
);
```

### Tabla: country_adjacencies (Relaciones Bidireccionales)
```sql
CREATE TABLE country_adjacencies (
    country_code VARCHAR(2) REFERENCES countries(code),
    adjacent_country_code VARCHAR(2) REFERENCES countries(code),
    PRIMARY KEY (country_code, adjacent_country_code)
);
```

**Seed Data:**
- 166 países globales (no solo Europa)
- 614 relaciones bidireccionales de fronteras (Wikipedia)
- Nombres bilingües (inglés/español)

**📋 Ver mappers:** `src/modules/competition/infrastructure/persistence/sqlalchemy/mappers.py`

---

## 📡 API Endpoints

### Competition Management (10 endpoints)
- `POST /api/v1/competitions` - Crear competición
- `GET /api/v1/competitions` - Listar competiciones con filtros
- `GET /api/v1/competitions/{id}` - Obtener competición
- `PUT /api/v1/competitions/{id}` - Actualizar competición (solo DRAFT)
- `DELETE /api/v1/competitions/{id}` - Eliminar competición (solo DRAFT)
- `POST /api/v1/competitions/{id}/activate` - DRAFT → ACTIVE
- `POST /api/v1/competitions/{id}/close-enrollments` - ACTIVE → CLOSED
- `POST /api/v1/competitions/{id}/start` - CLOSED → IN_PROGRESS
- `POST /api/v1/competitions/{id}/complete` - IN_PROGRESS → COMPLETED
- `POST /api/v1/competitions/{id}/cancel` - Cualquier estado → CANCELLED

### Enrollment Management (8 endpoints)
- `POST /api/v1/competitions/{id}/enrollments` - Solicitar inscripción
- `POST /api/v1/competitions/{id}/enrollments/direct` - Inscripción directa (creador)
- `GET /api/v1/competitions/{id}/enrollments` - Listar inscripciones
- `POST /api/v1/enrollments/{id}/approve` - Aprobar solicitud
- `POST /api/v1/enrollments/{id}/reject` - Rechazar solicitud
- `POST /api/v1/enrollments/{id}/cancel` - Cancelar solicitud
- `POST /api/v1/enrollments/{id}/withdraw` - Retirarse de competición
- `PUT /api/v1/enrollments/{id}/handicap` - Establecer handicap personalizado

### Country Management (2 endpoints - Shared)
- `GET /api/v1/countries` - Lista países activos
- `GET /api/v1/countries/{code}/adjacent` - Países adyacentes

**📋 Ver documentación completa:** `docs/API.md`

---

## 🔐 Seguridad y Rate Limiting

### Rate Limits
- `POST /api/v1/competitions` - 10 torneos/hora (anti-spam)

### Autorización
- **Solo creador** puede actualizar, eliminar o cambiar estado de torneo
- **Solo creador** puede aprobar/rechazar solicitudes de inscripción
- **Solo creador** puede inscribir jugadores directamente
- **Solo creador** puede establecer custom handicaps
- **Solo dueño** puede cancelar/retirarse de su propia inscripción

---

## 🧪 Testing

### Estadísticas
- **Total Competition Module:** 174 tests (97.6% pasando)
- **Unit Tests (Domain):** 38 tests (entities, value objects, repositories)
- **Unit Tests (Application):** 58 tests (use cases)
- **Unit Tests (DTOs):** 48 tests (validaciones)
- **Integration Tests:** Incluidos en test suite general (API endpoints)

### Estructura
```
tests/unit/modules/competition/
├── domain/value_objects/test_*.py (38 tests)
├── application/dto/test_*.py (48 tests)
├── application/use_cases/test_*.py (58 tests)
└── infrastructure/ (pendiente)

tests/integration/api/v1/
├── test_competition_routes.py
└── test_enrollment_routes.py
```

### Ejecución
```bash
# Todos los tests del módulo Competition
pytest tests/unit/modules/competition/ -v

# Solo tests unitarios (rápido)
pytest tests/unit/modules/competition/domain/ -v

# Con paralelización
pytest tests/unit/modules/competition/ -n auto
```

---

## 🔄 Estados y Transiciones

### Competition Status (Estado de Torneo)

```
DRAFT → ACTIVE → CLOSED → IN_PROGRESS → COMPLETED
  ↓        ↓         ↓           ↓
  └────────┴─────────┴───────────┴─→ CANCELLED
```

**Estados:**
- `DRAFT` - Borrador, solo visible para creador, editable
- `ACTIVE` - Activo, inscripciones abiertas
- `CLOSED` - Inscripciones cerradas, equipos configurados
- `IN_PROGRESS` - Torneo en curso
- `COMPLETED` - Torneo finalizado
- `CANCELLED` - Cancelado desde cualquier estado

**Reglas:**
- Solo DRAFT es editable/eliminable
- Solo ACTIVE acepta inscripciones
- Solo creador puede cambiar estados

### Enrollment Status (Estado de Inscripción)

```
REQUESTED → APPROVED → WITHDRAWN
    ↓           ↓
REJECTED    CANCELLED
```

**Estados:**
- `REQUESTED` - Solicitud pendiente
- `INVITED` - Invitado por creador (futuro)
- `APPROVED` - Inscripción aprobada
- `REJECTED` - Solicitud rechazada
- `CANCELLED` - Cancelada por jugador (pre-aprobación)
- `WITHDRAWN` - Retirado por jugador (post-aprobación)

---

## 🏛️ Decisiones Arquitectónicas

### 1. Location Value Object - Multi-Country Support
**Decisión:** Soporte para hasta 3 países adyacentes en una competición

**Razón:**
- Torneos transfronterizos son comunes en Europa
- Validación automática de adyacencia geográfica
- Base de datos local con seed data (sin API externa)

**Implementación:**
- Composite Value Object: Location(main, secondary, tertiary)
- Validación de adyacencia contra tabla country_adjacencies
- 614 relaciones bidireccionales precargadas

### 2. Custom Handicap Override
**Decisión:** Permitir override del handicap oficial por enrollment

**Razón:**
- Flexibilidad para organizadores
- Casos especiales (jugadores lesionados, categorías especiales)
- No modifica el handicap oficial del usuario

**Implementación:**
- Campo `custom_handicap` opcional en Enrollment entity
- Solo creador puede establecer
- Si NULL, usa handicap oficial del usuario

### 3. Competition State Machine
**Decisión:** Estados explícitos con validaciones estrictas

**Razón:**
- Prevenir inconsistencias (ej: iniciar torneo sin cerrar inscripciones)
- Trazabilidad completa con Domain Events
- Seguridad (solo creador puede cambiar estados)

**Implementación:**
- CompetitionStatus enum con 6 estados
- Métodos de transición en entidad (activate, close, start, complete, cancel)
- Domain Events emitidos en cada transición

---

## 🔗 Enlaces Relacionados

### Documentación
- **API Endpoints:** `docs/API.md`
- **User Management Module:** `docs/modules/user-management.md`
- **Security Implementation:** `docs/SECURITY_IMPLEMENTATION.md`

### Código Fuente
- **Domain Layer:** `src/modules/competition/domain/`
- **Application Layer:** `src/modules/competition/application/`
- **Infrastructure Layer:** `src/modules/competition/infrastructure/`

### ADRs (Architecture Decision Records)
- **ADR-020:** Competition Module Domain Design
- **ADR-005:** Repository Pattern
- **ADR-006:** Unit of Work Pattern
- **ADR-007:** Domain Events Pattern

### Testing
- **Tests Unitarios:** `tests/unit/modules/competition/`
- **Tests Integración:** `tests/integration/api/v1/`

---

## 💡 Tips para Desarrollo

### Crear Nuevo Use Case de Competition
1. Definir DTO de Request y Response en `application/dto/competition_dto.py`
2. Crear Use Case en `application/use_cases/`
3. Inyectar CompetitionUnitOfWork en constructor
4. Implementar lógica en método `execute()`
5. Usar `async with self._uow:` para transacciones
6. Emitir domain events si es necesario
7. Crear tests unitarios + integración

### Añadir Nueva Transición de Estado
1. Crear método en Competition entity (`def transition_name(self)`)
2. Validar estado actual con `_ensure_state(CompetitionStatus.XXX)`
3. Cambiar estado y emitir Domain Event
4. Crear Use Case wrapper (opcional, recomendado)
5. Añadir endpoint en `competition_routes.py`
6. Crear tests de transición válida/inválida

### Trabajar con Enrollments
1. Validar siempre que competition.status == ACTIVE
2. Verificar que no existe enrollment duplicado
3. Usar `custom_handicap` solo si necesario (NULL usa oficial)
4. Emitir eventos de dominio para trazabilidad
5. Validar permisos (solo creador/dueño según acción)

---

**Última actualización:** 18 de Diciembre de 2025
**Versión:** 1.8.0
