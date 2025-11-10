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
- **Desarrollo**: Permite `http://localhost:5173`, `http://127.0.0.1:5173`
- **Producción**: Configurado dinámicamente desde variable `FRONTEND_ORIGINS`
- **Middleware**: `CORSMiddleware` con credenciales habilitadas
- **Implementación**: `main.py:100-130` (lectura dinámica según `ENVIRONMENT`)

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

## 🚀 Deployment en Render (Producción)

### URLs de Producción

**Backend API**: https://rydercup-api.onrender.com
**Frontend Web**: https://www.rydercupfriends.com

**Repositorios**:
- Backend: `github.com/agustinEDev/RyderCupAm` (rama `develop`)
- Frontend: `github.com/agustinEDev/RyderCupWeb` (rama `develop`)

### Configuración de Render

**Backend - Web Service**:
- **Service Name**: `rydercup-api`
- **Runtime**: Docker
- **Branch**: `develop`
- **Dockerfile**: `Dockerfile` en root del proyecto
- **Entrypoint**: `entrypoint.sh` (migraciones + app start)
- **Region**: Frankfurt (eu-central)
- **Plan**: Free
- **Auto-Deploy**: Activado (git push → deploy automático)

**Base de Datos - PostgreSQL**:
- **Service Name**: `rydercup-db`
- **Database**: `ryderclub`
- **PostgreSQL Version**: 15
- **Region**: Frankfurt (eu-central)
- **Plan**: Free (1GB storage)
- **Connection**: Internal Database URL

### Variables de Entorno en Render

**Web Service (Backend) - Environment Variables**:

```env
# Frontend CORS Configuration
FRONTEND_ORIGINS=https://www.rydercupfriends.com

# Database (Internal Database URL de Render PostgreSQL)
# ⚠️ IMPORTANTE: Cambiar 'postgresql://' por 'postgresql+asyncpg://'
DATABASE_URL=postgresql+asyncpg://user:pass@host.frankfurt-postgres.render.com/ryderclub

# JWT Security
SECRET_KEY=<generated-secure-key-32-chars>
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60

# API Documentation Protection (HTTP Basic Auth)
DOCS_USERNAME=admin
DOCS_PASSWORD=<secure-password>

# Application Configuration
PORT=10000
ENVIRONMENT=production

# Optional: RFEG Integration
RFEG_TIMEOUT=10
```

**Generar SECRET_KEY segura**:
```bash
# Opción 1: Python
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Opción 2: OpenSSL
openssl rand -base64 32
```

### Dockerfile y Entrypoint

El proyecto usa **Docker** para deployment en Render:

**Dockerfile** (multi-stage build):
- Stage 1: Builder (instala dependencias)
- Stage 2: Runtime (copia solo lo necesario)
- Base: `python:3.12-slim`
- Expone: Puerto 10000 (puerto de Render por defecto)

**entrypoint.sh**:
1. **Wait for PostgreSQL**: Espera hasta que DB esté disponible
2. **Run Migrations**: `alembic upgrade head` (automático)
3. **Start App**: `uvicorn main:app --host 0.0.0.0 --port $PORT`

### CORS Configuration Dinámica

Implementación en `main.py:100-130`:

```python
# Leer orígenes desde variable de entorno
FRONTEND_ORIGINS = os.getenv("FRONTEND_ORIGINS", "")
allowed_origins = [origin.strip() for origin in FRONTEND_ORIGINS.split(",")]

# Incluir localhost solo en desarrollo
ENV = os.getenv("ENVIRONMENT", "development").lower()
if ENV != "production":
    allowed_origins.extend([
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ])

# Si no hay orígenes configurados, modo seguro (solo localhost)
if not allowed_origins:
    allowed_origins = ["http://localhost:5173", "http://127.0.0.1:5173"]

print(f"🔒 CORS allowed_origins: {allowed_origins}")
```

**Desarrollo** (`ENVIRONMENT=development`):
- Permite: `localhost:5173`, `127.0.0.1:5173`

**Producción** (`ENVIRONMENT=production`):
- Permite: Solo URLs en `FRONTEND_ORIGINS`
- Ejemplo: `https://www.rydercupfriends.com`
- **NO incluye localhost** (seguridad)

### Proceso de Deploy

**Automático** (recomendado):
```bash
# 1. Hacer cambios y probar localmente
python dev_tests.py  # Verificar que todos los tests pasen
uvicorn main:app --reload  # Probar app localmente

# 2. Commit y push a develop → auto-deploy
git add .
git commit -m "feat: descripción del cambio"
git push origin develop

# Render detecta el push y:
# - Clona repositorio
# - Build Docker image (Dockerfile)
# - Run entrypoint.sh:
#   1. Wait for PostgreSQL
#   2. Run migrations (alembic upgrade head)
#   3. Start FastAPI app
#
# Deploy time: ~3-5 minutos (incluye migraciones)
```

**Manual** (desde Render Dashboard):
1. Dashboard → `rydercup-api` → `Manual Deploy`
2. Seleccionar `Deploy latest commit`
3. Ver logs en tiempo real

### Verificar Deployment

**Health Check** (endpoint público):
```bash
curl https://rydercup-api.onrender.com/

# Respuesta esperada:
{
  "message": "Ryder Cup Manager API",
  "version": "1.0.0",
  "status": "running",
  "docs": "Visita /docs para la documentacion interactiva",
  "description": "API para gestion de torneos tipo Ryder Cup entre amigos"
}
```

**API Documentation** (protegida con HTTP Basic Auth):
```bash
# Acceder desde navegador:
https://rydercup-api.onrender.com/docs

# Se solicitará:
# Username: (ver variable DOCS_USERNAME)
# Password: (ver variable DOCS_PASSWORD)
```

**Ver logs en Render**:
```
Dashboard → rydercup-api → Logs

# Buscar líneas clave:
🚀 Iniciando Ryder Cup Manager API...
✅ PostgreSQL está disponible
🔄 Ejecutando migraciones de base de datos...
✅ Migraciones completadas exitosamente
🔒 CORS allowed_origins: ['https://www.rydercupfriends.com']
🎯 Iniciando aplicación FastAPI en puerto 10000...
INFO: Started server process
```

### Database Migrations en Producción

**Automático** (entrypoint.sh):
- Migraciones se ejecutan automáticamente en cada deploy
- Comando: `alembic upgrade head`
- Si falla: Deploy se detiene (seguridad)

**Manual** (Shell de Render):
```bash
# Acceder a Shell del servicio
Dashboard → rydercup-api → Shell

# Ejecutar migraciones manualmente
alembic upgrade head

# Ver historial de migraciones
alembic history

# Ver estado actual
alembic current
```

**Crear nueva migración**:
```bash
# En desarrollo local:
alembic revision --autogenerate -m "add_new_table"

# Commit y push → deploy automático aplicará migración
git add migrations/
git commit -m "db: add new table migration"
git push origin develop
```

### Logs y Monitoreo

**Logs en Tiempo Real**:
1. Dashboard → `rydercup-api` → `Logs`
2. Útil para:
   - Debugging de errores
   - Ver CORS origins cargados
   - Verificar migraciones exitosas
   - Monitorear requests

**Métricas**:
- Dashboard → `Metrics`
- CPU, Memoria, Network
- Request rate, Response times

**Eventos**:
- Dashboard → `Events`
- Historial de deploys
- Estado de cada deploy

### Limitaciones del Plan Free

**Cold Starts**:
- Servicio se "duerme" tras **15 minutos de inactividad**
- Primera petición después de sleep: **30-60 segundos**
  - Incluye: start container + run migrations + start app
- Peticiones siguientes: respuesta normal (50-200ms)

**Impacto**:
- Frontend puede mostrar error de timeout en primera petición
- Usuario debe esperar o reintentar

**Solución** (si es problema crítico):
- Upgrade a plan Starter ($7/mes) → sin sleep
- Keep-alive requests cada 10-15 min (temporal)

**Database**:
- PostgreSQL: 1GB storage
- Expira tras 90 días sin uso
- Sin backups automáticos (plan Free)

**Build minutes**:
- 750 horas/mes de runtime
- Suficiente para desarrollo/testing

### Troubleshooting en Producción

**❌ CORS Error desde frontend**:

**Causa**: Backend no permite origen del frontend

**Solución**:
1. Verificar logs del backend: buscar línea `🔒 CORS allowed_origins: [...]`
2. Debe incluir: `https://www.rydercupfriends.com`
3. Verificar variables de entorno:
   ```
   FRONTEND_ORIGINS=https://www.rydercupfriends.com
   ENVIRONMENT=production
   ```
4. Re-deploy si se cambió variable:
   ```bash
   Dashboard → rydercup-api → Manual Deploy
   ```

**❌ Database connection error**:

**Causa**: `DATABASE_URL` incorrecta

**Solución**:
1. Ir a PostgreSQL service → `Connections`
2. Copiar **Internal Database URL**
3. **IMPORTANTE**: Cambiar `postgresql://` → `postgresql+asyncpg://`
   ```
   # Render da:
   postgresql://user:pass@host/db

   # Debe ser:
   postgresql+asyncpg://user:pass@host/db
   ```
4. Actualizar variable en Web Service
5. Re-deploy

**❌ Migrations failed**:

**Causa**: Error en migración o BD inconsistente

**Solución**:
1. Ver logs del deploy: buscar error específico
2. Acceder a Shell del servicio:
   ```bash
   alembic current  # Ver estado actual
   alembic history  # Ver historial

   # Intentar aplicar manualmente:
   alembic upgrade head
   ```
3. Si persiste: revisar migration files localmente
4. Opción drástica (solo en desarrollo):
   ```bash
   # Borrar y recrear BD (PIERDE DATOS)
   alembic downgrade base
   alembic upgrade head
   ```

**❌ API devuelve 500 Internal Server Error**:

**Causa**: Error en código o configuración

**Solución**:
1. **Ver logs detallados**:
   ```
   Dashboard → Logs → buscar traceback completo
   ```
2. Causas comunes:
   - Variable de entorno faltante o incorrecta
   - Error en migración de BD
   - Dependencia faltante en `requirements.txt`
3. Reproducir localmente:
   ```bash
   # Usar mismas variables de entorno
   export ENVIRONMENT=production
   export DATABASE_URL=postgresql+asyncpg://...
   uvicorn main:app --reload
   ```

**❌ JWT tokens inválidos después de redeploy**:

**Causa**: `SECRET_KEY` cambió

**Solución**:
1. Verificar que `SECRET_KEY` sea la misma
2. Si cambió: usuarios deben hacer logout/login
3. **IMPORTANTE**: NO cambiar `SECRET_KEY` en producción sin avisar

**❌ RFEG service timeout**:

**Causa**: RFEG website puede ser lento o estar caído

**Solución**:
- Es comportamiento esperado (servicio externo)
- Frontend debe mostrar mensaje claro al usuario
- Usuario puede usar "Update Manual" como fallback

**❌ Cold start muy lento (>60s)**:

**Causa**: Plan Free duerme servicio

**Solución temporal**:
- Hacer peticiones periódicas (keep-alive)
- Avisar a usuarios que primera carga puede tardar

**Solución permanente**:
- Upgrade a plan Starter ($7/mes)

### API Documentation Security

**Protección HTTP Basic Auth** implementada en `main.py:152-162`:

```python
@app.get("/docs", include_in_schema=False)
async def get_documentation(username: str = Depends(verify_docs_credentials)):
    return get_swagger_ui_html(openapi_url="/openapi.json", title="API Docs")
```

**Acceso**:
1. Ir a: https://rydercup-api.onrender.com/docs
2. Navegador solicita credenciales HTTP Basic
3. Usar: `DOCS_USERNAME` y `DOCS_PASSWORD` configuradas en variables de entorno

**Endpoints protegidos**:
- `/docs` - Swagger UI
- `/redoc` - ReDoc UI

**Endpoint público** (sin auth):
- `/` - Health check

### Rollback en Producción

**Si deploy falla o introduce bugs**:

**Opción 1: Revert commit y push**:
```bash
git revert HEAD
git push origin develop
# Auto-deploy del commit revertido
```

**Opción 2: Desde Render Dashboard**:
1. Dashboard → `rydercup-api` → `Events`
2. Buscar último deploy exitoso
3. Click en "Redeploy" de ese commit específico

**Opción 3: Rollback de migración**:
```bash
# Si el problema es una migración de BD
Dashboard → Shell

# Ver historial
alembic history

# Bajar una versión
alembic downgrade -1

# O bajar a versión específica
alembic downgrade <revision_id>
```

### Entornos: Desarrollo vs Producción

| Aspecto | Desarrollo | Producción |
|---------|-----------|------------|
| **Database** | Docker PostgreSQL (local) | Render PostgreSQL (Frankfurt) |
| **CORS** | localhost:5173 | www.rydercupfriends.com |
| **PORT** | 8000 | 10000 (Render default) |
| **ENVIRONMENT** | development | production |
| **Migrations** | Manual (`alembic upgrade head`) | Automáticas (entrypoint.sh) |
| **Logs** | Terminal | Render Dashboard |
| **Docs** | Sin auth (localhost:8000/docs) | HTTP Basic Auth |
| **RFEG** | Puede usar Mock | Servicio real |
| **Branch** | local | develop |

### Checklist Pre-Deploy

Antes de push a `develop`:

- [ ] Todos los tests pasan: `python dev_tests.py`
- [ ] App funciona localmente: `uvicorn main:app --reload`
- [ ] Migraciones aplicadas localmente: `alembic upgrade head`
- [ ] Variables de entorno verificadas en Render
- [ ] Commit message descriptivo
- [ ] CORS origins incluyen frontend correcto
- [ ] No hay `print()` sensible (passwords, secrets)

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

### Aplicación (Desarrollo Local)
```bash
# Run (local)
uvicorn main:app --reload

# Run (Docker - simula producción)
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
# Crear nueva migración
alembic revision --autogenerate -m "description"

# Aplicar migraciones
alembic upgrade head

# Revertir migración
alembic downgrade -1

# Ver historial
alembic history

# Ver estado actual
alembic current
```

### Deployment a Producción

**Automático** (recomendado):
```bash
# 1. Probar cambios localmente
python dev_tests.py  # Todos los tests deben pasar
uvicorn main:app --reload  # Verificar funcionamiento

# 2. Aplicar migraciones localmente (si hay)
alembic upgrade head

# 3. Commit y push a develop → auto-deploy
git add .
git commit -m "feat: descripción del cambio"
git push origin develop

# Render detecta el push y redeploya automáticamente
# Ver progreso en: https://dashboard.render.com
# Deploy time: ~3-5 minutos (incluye build Docker + migrations)
```

**Verificar deployment**:
```bash
# Health check
curl https://rydercup-api.onrender.com/
# Esperado: {"message": "Ryder Cup Manager API", ...}

# Ver logs en tiempo real
# Dashboard → rydercup-api → Logs
```

**Rollback** (si algo sale mal):
```bash
# Opción 1: Revertir commit y push
git revert HEAD
git push origin develop

# Opción 2: Desde Render Dashboard
# → rydercup-api → Events → "Redeploy" de commit anterior
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

### Desarrollo Local

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

**CORS errors con frontend local**:
- Verificar `ENVIRONMENT=development` (permite localhost)
- Backend debe estar corriendo en puerto 8000
- Frontend debe estar en puerto 5173

### Producción (Render)

**Ver sección completa**: [🚀 Deployment en Render](#-deployment-en-render-producción) → Troubleshooting en Producción

**Problemas comunes**:
- **CORS errors**: Verificar `FRONTEND_ORIGINS=https://www.rydercupfriends.com` y `ENVIRONMENT=production`
- **Database connection**: Verificar `DATABASE_URL` usa `postgresql+asyncpg://` (no `postgresql://`)
- **Migrations failed**: Ver logs, ejecutar manualmente desde Shell si es necesario
- **500 errors**: Revisar logs en Dashboard, verificar variables de entorno
- **Cold starts lentos**: Plan Free duerme tras 15min (30-60s primera petición)
- **JWT tokens inválidos**: Verificar SECRET_KEY no haya cambiado

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

**Documentación del Proyecto**:
- [Design Document](docs/design-document.md) - Especificación técnica completa
- [Project Structure](docs/project-structure.md) - Organización del código
- [API Reference](docs/API.md) - Endpoints y schemas
- [Runbook](docs/RUNBOOK.md) - Deploy y operaciones
- [ADRs](docs/architecture/decisions/) - Decisiones arquitectónicas (el "por qué")
- [Render Deployment](RENDER_DEPLOYMENT.md) - Guía completa de deployment

**URLs del Proyecto**:
- **Backend Dev**: http://localhost:8000
- **Backend Prod**: https://rydercup-api.onrender.com
- **Frontend Dev**: http://localhost:5173
- **Frontend Prod**: https://www.rydercupfriends.com
- **API Docs Dev**: http://localhost:8000/docs (sin auth)
- **API Docs Prod**: https://rydercup-api.onrender.com/docs (HTTP Basic Auth)
- **GitHub Backend**: https://github.com/agustinEDev/RyderCupAm
- **GitHub Frontend**: https://github.com/agustinEDev/RyderCupWeb
- **Render Dashboard**: https://dashboard.render.com

**ADRs Críticos**:
- [ADR-001](docs/architecture/decisions/ADR-001-clean-architecture.md) - Clean Architecture
- [ADR-002](docs/architecture/decisions/ADR-002-value-objects.md) - Value Objects
- [ADR-005](docs/architecture/decisions/ADR-005-repository-pattern.md) - Repository Pattern
- [ADR-006](docs/architecture/decisions/ADR-006-unit-of-work-pattern.md) - Unit of Work
- [ADR-007](docs/architecture/decisions/ADR-007-domain-events-pattern.md) - Domain Events
- [ADR-013](docs/architecture/decisions/ADR-013-external-services-pattern.md) - External Services
- [ADR-014](docs/architecture/decisions/ADR-014-handicap-management-system.md) - Handicap System
- [ADR-015](docs/architecture/decisions/ADR-015-session-management-progressive-strategy.md) - Session Management
- [ADR-016](docs/architecture/decisions/ADR-016-render-deployment-strategy.md) - Render Deployment ⭐ NUEVO
- [ADR-017](docs/architecture/decisions/ADR-017-dynamic-cors-configuration.md) - Dynamic CORS ⭐ NUEVO
- [ADR-018](docs/architecture/decisions/ADR-018-automated-database-migrations.md) - Automated Migrations ⭐ NUEVO

**External Documentation**:
- [FastAPI Docs](https://fastapi.tiangolo.com/)
- [SQLAlchemy 2.0 Docs](https://docs.sqlalchemy.org/en/20/)
- [Alembic Docs](https://alembic.sqlalchemy.org/)
- [Render Docs](https://render.com/docs)

---

## 🎓 Notas para Claude Code

**Al empezar una sesión**:
1. Ya conozco la arquitectura (Clean Architecture + DDD)
2. User module + Auth está completo (360 tests), Tournament en desarrollo
3. Usar patrones establecidos (Repository, UoW, Events, VOs)
4. Domain no depende de nada (regla crítica)
5. Tests SIEMPRE con >90% cobertura
6. Session Management en Fase 1 (client-side logout, ver ADR-015)
7. **Deployment**: Backend en Render (Frankfurt), rama `develop`, auto-deploy activado
8. **CORS**: Configurado dinámicamente según `ENVIRONMENT` (localhost en dev, dominio custom en prod)

**Cuando agregue features**:
1. Seguir estructura de módulos existente
2. Crear ADR solo si hay decisión arquitectónica importante
3. Value Objects para conceptos de dominio importantes
4. Domain Events para auditoría y comunicación desacoplada
5. External Services Pattern para integraciones externas
6. **Probar localmente antes de push** (auto-deploy a producción)

**Testing**:
1. Usar `python dev_tests.py` (no pytest directo)
2. InMemoryRepository o mocks para unit tests
3. Integration tests con BD real
4. MockHandicapService para evitar llamadas RFEG en tests
5. **IMPORTANTE**: Todos los tests deben pasar antes de push a develop

**Unit of Work Pattern (IMPORTANTE)**:
1. NUNCA usar `await uow.commit()` explícito en Use Cases
2. Context manager maneja automáticamente: `async with uow:`
3. Commit en éxito, rollback en excepción (automático)
4. Domain Events se publican automáticamente post-commit

**Database Migrations**:
1. Siempre usar Alembic (nunca modificar BD manualmente)
2. Crear migración: `alembic revision --autogenerate -m "description"`
3. Aplicar localmente: `alembic upgrade head`
4. Commit migration files y push → se aplican automáticamente en producción
5. En producción: ejecutadas automáticamente por `entrypoint.sh` en cada deploy

**No hacer**:
- ❌ Dependencias de Domain hacia Application o Infrastructure
- ❌ Lógica de negocio en Application o Infrastructure
- ❌ Modificar BD sin migrations de Alembic
- ❌ Commits sin tests (100% passing)
- ❌ Tests sin usar el optimized test runner (`dev_tests.py`)
- ❌ **`await uow.commit()` explícito en Use Cases** (violación Clean Architecture)
- ❌ **Push a `develop` sin testing local** (auto-deploy directo a producción)
- ❌ Cambiar `SECRET_KEY` en producción sin avisar (invalida todos los JWT)

**Entornos**:

| Aspecto | Desarrollo | Producción |
|---------|-----------|------------|
| **Database** | Docker PostgreSQL (local) | Render PostgreSQL (Frankfurt) |
| **CORS** | localhost:5173, 127.0.0.1:5173 | www.rydercupfriends.com |
| **PORT** | 8000 | 10000 |
| **ENVIRONMENT** | development | production |
| **Migrations** | Manual | Automáticas (entrypoint.sh) |
| **Logs** | Terminal | Render Dashboard |
| **Docs Auth** | Sin auth | HTTP Basic Auth |
| **Branch** | local | develop |

**Variables de entorno críticas**:
- **ENVIRONMENT**: Controla comportamiento de CORS y otros settings
- **FRONTEND_ORIGINS**: Lista de orígenes permitidos para CORS (solo en prod)
- **DATABASE_URL**: Debe usar `postgresql+asyncpg://` (no `postgresql://`)
- **SECRET_KEY**: NO cambiar en producción sin coordinación (invalida tokens)
- **DOCS_USERNAME/PASSWORD**: Protegen documentación API en producción
