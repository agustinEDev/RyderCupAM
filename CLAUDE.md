# CLAUDE.md

Este archivo proporciona contexto a Claude Code (claude.ai/code) para trabajar en este repositorio.

---

## 🎯 Contexto del Proyecto

**Ryder Cup Amateur Manager - Backend API** - REST API para gestión de torneos de golf amateur formato Ryder Cup.

### 🏗️ Arquitectura del Sistema

Este repositorio contiene **SOLO el Backend API**. La aplicación completa está dividida en repositorios separados:

- **Backend (este repo)**: API REST con Clean Architecture
  - Repository: `RyderCupAm`
  - Stack: Python, FastAPI, PostgreSQL
  - Comunicación: API REST (JSON)

- **Frontend Web** (repositorio separado): Aplicación web React
  - Repository: `RyderCupWeb`
  - Stack: React 18, Vite 5, Tailwind CSS 3
  - Comunicación: Consume API REST del backend via CORS

**Razón de separación**: Deploy independiente, ciclos de vida separados, escalabilidad futura (apps móviles, admin panels).

### Stack Tecnológico
- **Backend**: Python 3.12+, FastAPI
- **Database**: PostgreSQL 15+, SQLAlchemy 2.0, Alembic
- **Architecture**: Clean Architecture + Domain-Driven Design (DDD)
- **Testing**: pytest, pytest-xdist (parallelization), 360 tests

### Estado de Implementación

**Fase 1: Foundation** ✅ COMPLETADO
- **User Management**:
  - Entities: `User`
  - Value Objects: `UserId`, `Email`, `Password`, `Handicap`
  - Events: `UserRegisteredEvent`, `HandicapUpdatedEvent`, `UserLoggedInEvent`, `UserLoggedOutEvent`
  - Use Cases: `RegisterUser`, `LoginUser`, `LogoutUser`, `UpdateHandicap`, `UpdateHandicapManually`, `UpdateMultipleHandicaps`, `FindUser`
  - Auth: JWT (HS256, bcrypt) + Session Management (Fase 1)

- **Handicap System**:
  - RFEG integration (web scraping)
  - Mock service para testing
  - Batch updates con estadísticas
  - Validación: -10.0 a 54.0 (RFEG/EGA)

**Fase 2: Tournament Management** 🚧 EN DESARROLLO
- Tournament, Team, Match entities (planeadas)
- Scoring system (planeado)

### Endpoints API Activos (7 endpoints)
```
POST   /api/v1/auth/register                  # User registration
POST   /api/v1/auth/login                     # JWT authentication + UserLoggedInEvent
POST   /api/v1/auth/logout                    # Logout with audit + UserLoggedOutEvent
POST   /api/v1/handicaps/update                # RFEG lookup + optional fallback
POST   /api/v1/handicaps/update-manual         # Manual handicap update
POST   /api/v1/handicaps/update-multiple       # Batch update with stats
GET    /api/v1/users/search                    # Find by email or full_name
```

**Documentación interactiva**: `http://localhost:8000/docs` (Swagger UI)

**Frontend**: Estos endpoints son consumidos por el frontend web en el repositorio `RyderCupWeb`

**CORS Configuration**:
- Configurado para permitir requests desde `http://localhost:5173` (Vite dev server)
- Middleware: `CORSMiddleware` con credenciales habilitadas
- En producción: Ajustar `allow_origins` según deployment URL

### Integraciones Externas
- **RFEG** (Real Federación Española de Golf): Web scraping para handicaps oficiales
  - Timeout: 10s
  - Fallback: Manual handicap si falla
  - Mock: `MockHandicapService` para tests

### Métricas Actuales
- **Tests**: 360 (100% passing)
  - Unit: 313 (87%)
  - Integration: 47 (13%)
- **Cobertura**: >90% en lógica de negocio
- **Performance**: ~12s (paralelización con pytest-xdist)
- **Módulos**: 1/3 completo (User + Auth)
- **Líneas código**: ~15,000

---

## 🏗️ Arquitectura

### Clean Architecture (3 capas)

```
Infrastructure (FastAPI, SQLAlchemy, RFEG)
    ↓ depende de
Application (Use Cases, DTOs, Handlers)
    ↓ depende de
Domain (Entities, VOs, Events, Repos interfaces)
```

**Regla crítica**: Las dependencias SIEMPRE apuntan hacia adentro. Domain no depende de nada.

### Patrones Implementados

| Patrón | Ubicación | Propósito |
|--------|-----------|-----------|
| **Value Objects** | Domain | Validación inmutable (Email, Password, Handicap) |
| **Repository Pattern** | Domain (interface) + Infra (impl) | Abstracción de persistencia |
| **Unit of Work** | Application | Transacciones atómicas |
| **Domain Events** | Domain + Application | Comunicación desacoplada, auditoría |
| **External Services** | Domain (interface) + Infra (impl) | Integración con APIs externas (RFEG) |
| **Composition Root** | `src/config/dependencies.py` | Dependency Injection |

### Estructura de Módulos

```
src/modules/{module}/
├── domain/
│   ├── entities/        # User (con métodos login/logout)
│   ├── value_objects/   # UserId, Email, Password, Handicap
│   ├── events/          # UserRegisteredEvent, HandicapUpdatedEvent, UserLoggedInEvent, UserLoggedOutEvent
│   ├── repositories/    # UserRepositoryInterface (ABC)
│   ├── services/        # HandicapService (ABC)
│   └── errors/          # UserNotFoundError, InvalidEmailError, etc.
├── application/
│   ├── use_cases/       # RegisterUser, LoginUser, LogoutUser, UpdateHandicap, etc.
│   ├── dto/             # Request/Response DTOs (Pydantic)
│   └── handlers/        # UserRegisteredEventHandler
└── infrastructure/
    ├── api/v1/          # auth_routes.py, handicap_routes.py, user_routes.py
    ├── persistence/     # SQLAlchemyUserRepository + UnitOfWork
    ├── external/        # RFEGHandicapService, MockHandicapService
    └── security/        # JWTHandler, Authentication
```

---

## 💻 Comandos de Desarrollo

### Aplicación
```bash
# Run (local)
uvicorn main:app --reload

# Run (Docker)
docker-compose up -d
docker-compose logs -f app
docker-compose restart
docker-compose down
docker-compose up -d --build  # Rebuild after changes
```

### Testing
```bash
python dev_tests.py                    # Full suite (recomendado, ~12s)
pytest tests/unit/                     # Solo unit tests
pytest tests/integration/              # Solo integration tests
pytest tests/unit/modules/user/        # Tests de un módulo
pytest path/to/test.py::test_name      # Test específico
pytest --cov=src --cov-report=html     # Con cobertura
```

### Database
```bash
alembic revision --autogenerate -m "description"
alembic upgrade head
alembic downgrade -1
alembic history
alembic current
```

### Code Quality
```bash
black src/ tests/      # Format
mypy src/              # Type checking
```

---

## 🔧 Workflow: Agregar Nueva Feature

### Patrón de Uso: Unit of Work (CRÍTICO)

**✅ CORRECTO - Context Manager Automático**:
```python
async def execute(self, command: Command) -> Result:
    async with self._uow:  # ← Context manager maneja TODO
        # Solo lógica de negocio
        user = await User.create(...)
        await self._uow.users.save(user)
        # NO commit explícito - automático al salir del contexto
    # Commit automático (éxito) o rollback (excepción)
```

**❌ INCORRECTO - Commit Explícito**:
```python
async def execute(self, command: Command) -> Result:
    async with self._uow:
        user = await User.create(...)
        await self._uow.users.save(user)
        await self._uow.commit()  # ❌ VIOLACIÓN Clean Architecture
```

**Razón**: Use Cases deben contener solo lógica de negocio, no detalles técnicos de transacciones.

---

### 1. Domain Layer (Lógica de negocio)
- Crear entity en `domain/entities/`
- Crear value objects necesarios en `domain/value_objects/`
- Crear domain events si aplica en `domain/events/`
- Definir repository interface en `domain/repositories/`
- Definir domain service interface si aplica en `domain/services/`

### 2. Application Layer (Orquestación)
- Crear use case en `application/use_cases/`
- Crear DTOs en `application/dto/`
- Crear event handlers si aplica en `application/handlers/`

### 3. Infrastructure Layer (Detalles técnicos)
- Implementar repository en `infrastructure/persistence/sqlalchemy/`
- Crear routes en `infrastructure/api/v1/`
- Implementar external services si aplica en `infrastructure/external/`

### 4. Database
```bash
alembic revision --autogenerate -m "add_feature_name"
alembic upgrade head
```

### 5. Testing
- Unit tests para domain entities y VOs
- Unit tests para use cases (con InMemoryRepository o mocks)
- Integration tests para API endpoints

### 6. Docs (si aplica)
- Crear ADR si hay decisión arquitectónica importante
- Actualizar API.md con nuevos endpoints
- Actualizar design-document.md si cambia arquitectura

---

## 🐛 Troubleshooting Común

**Database connection issues**:
```bash
docker-compose ps                              # Verificar estado
docker-compose down -v && docker-compose up -d # Reset completo
```

**Tests failing**:
- Verificar BD limpia (integration tests pueden dejar datos)
- Verificar dependencias: `pip install -r requirements.txt`
- Run en verbose: `pytest -vv tests/path/`

**Import errors**:
- Verificar PYTHONPATH
- Verificar estructura de módulos respeta convenciones

**RFEG service timeout** (en tests integration):
- Es esperado si RFEG está caído
- Tests usan nombres reales: "Rafael Nadal Parera", "Carlos Alcaraz Garfia"
- Usar MockHandicapService en unit tests

---

## 📋 Convenciones Importantes

### Naming
- **Módulos**: snake_case (`user_management/`)
- **Clases**: PascalCase (`UserRepository`, `UpdateHandicapUseCase`)
- **Funciones/Variables**: snake_case (`get_user_by_id`, `handicap_value`)
- **Constantes**: UPPER_SNAKE_CASE (`MAX_HANDICAP_VALUE`)
- **Tests**: `test_<what_it_tests>.py`

### Testing
- **asyncio_mode = auto** en pytest.ini (importante para async tests)
- **Markers**: `@pytest.mark.integration` para integration tests
- **Coverage target**: >90% en lógica de negocio

### Database
- **Migrations**: Siempre usar Alembic, nunca modificar BD manualmente
- **Mappers**: SQLAlchemy classical mapping (iniciado en `main.py` lifespan)
- **Transactions**: Unit of Work con context manager automático (NO commit explícito)

### Domain Events
- **Emisión**: Entities emiten eventos con `_add_domain_event()`
- **Publicación**: UoW publica eventos automáticamente post-commit
- **Inmutabilidad**: Todos los eventos son `@dataclass(frozen=True)`

### Unit of Work Pattern (Actualizado 9 Nov 2025)
- **Context Manager Automático**: `async with uow:` maneja commit/rollback
- **NO commits explícitos**: Violación de Clean Architecture eliminada
- **Separación de responsabilidades**: Use Cases solo lógica de negocio
- **Eventos automáticos**: Domain Events publicados post-commit automáticamente

---

## 📚 Referencias Rápidas

**Documentación**:
- [Design Document](docs/design-document.md) - Especificación técnica completa
- [Project Structure](docs/project-structure.md) - Organización del código
- [API Reference](docs/API.md) - Endpoints y schemas
- [Runbook](docs/RUNBOOK.md) - Deploy y operaciones
- [ADRs](docs/architecture/decisions/) - Decisiones arquitectónicas (el "por qué")

**ADRs Críticos**:
- [ADR-001](docs/architecture/decisions/ADR-001-clean-architecture.md) - Clean Architecture
- [ADR-002](docs/architecture/decisions/ADR-002-value-objects.md) - Value Objects
- [ADR-005](docs/architecture/decisions/ADR-005-repository-pattern.md) - Repository Pattern
- [ADR-006](docs/architecture/decisions/ADR-006-unit-of-work-pattern.md) - Unit of Work
- [ADR-007](docs/architecture/decisions/ADR-007-domain-events-pattern.md) - Domain Events
- [ADR-013](docs/architecture/decisions/ADR-013-external-services-pattern.md) - External Services
- [ADR-014](docs/architecture/decisions/ADR-014-handicap-management-system.md) - Handicap System
- [ADR-015](docs/architecture/decisions/ADR-015-session-management-progressive-strategy.md) - Session Management

---

## 🎓 Notas para Claude Code

**Al empezar una sesión**:
1. Ya conozco la arquitectura (Clean Architecture + DDD)
2. User module + Auth está completo (360 tests), Tournament en desarrollo
3. Usar patrones establecidos (Repository, UoW, Events, VOs)
4. Domain no depende de nada (regla crítica)
5. Tests SIEMPRE con >90% cobertura
6. Session Management en Fase 1 (client-side logout, ver ADR-015)

**Cuando agregue features**:
1. Seguir estructura de módulos existente
2. Crear ADR solo si hay decisión arquitectónica importante
3. Value Objects para conceptos de dominio importantes
4. Domain Events para auditoría y comunicación desacoplada
5. External Services Pattern para integraciones externas

**Testing**:
1. Usar `python dev_tests.py` (no pytest directo)
2. InMemoryRepository o mocks para unit tests
3. Integration tests con BD real
4. MockHandicapService para evitar llamadas RFEG en tests

**Unit of Work Pattern (IMPORTANTE)**:
1. NUNCA usar `await uow.commit()` explícito en Use Cases
2. Context manager maneja automáticamente: `async with uow:`
3. Commit en éxito, rollback en excepción (automático)
4. Domain Events se publican automáticamente post-commit

**No hacer**:
- ❌ Dependencias de Domain hacia Application o Infrastructure
- ❌ Lógica de negocio en Application o Infrastructure
- ❌ Modificar BD sin migrations de Alembic
- ❌ Commits sin tests
- ❌ Tests sin usar el optimized test runner (`dev_tests.py`)
- ❌ **`await uow.commit()` explícito en Use Cases** (violación Clean Architecture)
