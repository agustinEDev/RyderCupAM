# 🏆 Ryder Cup Amateur Manager - Backend API

> REST API para gestión de torneos de golf amateur formato Ryder Cup

[![Tests](https://img.shields.io/badge/tests-679%20passing-success)](.)
[![Python](https://img.shields.io/badge/python-3.11--3.12-blue)](.)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688)](.)
[![Architecture](https://img.shields.io/badge/architecture-Clean%20Architecture-green)](.)
[![CI/CD](https://img.shields.io/badge/CI%2FCD-GitHub%20Actions-2088FF)](.)
[![Security](https://img.shields.io/badge/security-8.0%2F10-success)](.)
[![OWASP](https://img.shields.io/badge/OWASP-Top%2010%202021-blue)](https://owasp.org/Top10/)

## 🌐 Frontend

Este es el **backend API**. Para la aplicación web frontend, visita:
👉 **[RyderCupWeb](https://github.com/agustinEDev/RyderCupWeb)**

## 🚀 Quick Start

### Local (Docker Compose)
```bash
git clone https://github.com/agustinEDev/RyderCupAM.git
cd RyderCupAM

# Iniciar servicios (PostgreSQL + API)
docker-compose up -d

# Ver logs
docker-compose logs -f app

# Acceder
open http://localhost:8000/docs
```

### Producción (Render.com)
```bash
# 1. Crear PostgreSQL Database en Render
# 2. Crear Web Service (Runtime: Docker)
# 3. Configurar variables de entorno:
DATABASE_URL=<internal-database-url>
SECRET_KEY=<random-32-chars>
ENVIRONMENT=production
FRONTEND_ORIGINS=https://www.rydercupfriends.com
# 4. Push a GitHub → Auto-deploy

# Variables de entorno para Mailgun (Email Verification)
MAILGUN_API_KEY=tu-api-key
MAILGUN_DOMAIN=tu-dominio-mailgun
MAILGUN_FROM_EMAIL="Ryder Cup Friends <noreply@rydercupfriends.com>"
MAILGUN_API_URL=https://api.eu.mailgun.net/v3
FRONTEND_URL=https://www.rydercupfriends.com
```
Ver guía completa en [RENDER_DEPLOYMENT.md](RENDER_DEPLOYMENT.md)


## 📚 Documentación

- **[Comandos](CLAUDE.md)** - Desarrollo diario
- **[Estructura](docs/project-structure.md)** - Organización del código
- **[Design Doc](docs/design-document.md)** - Especificación técnica
- **[ADRs - Decisiones Arquitectónicas](docs/architecture/decisions/)** - Registro de decisiones técnicas y cambios relevantes
- **[API](docs/API.md)** - Endpoints
- **[Deploy](docs/RUNBOOK.md)** - Operaciones

## 🛠️ Stack Tecnológico

Python 3.12+ · FastAPI · PostgreSQL 15+ · SQLAlchemy 2.0 · Clean Architecture + DDD

## ✨ Features API

- ✅ **User Management** - Registro, autenticación JWT, gestión de perfil, verificación email (Mailgun)
- ✅ **Handicap System** - Integración RFEG, actualización manual y batch
- ✅ **Competition Module** - CRUD completo, state transitions, enrollment system (20 endpoints)
- ✅ **Countries** - 166 países con 614 relaciones de fronteras, soporte multilenguaje
- ⏳ **RAG Chatbot** - Asistente de reglamento de golf (v1.11.0 planeado)
- ⏳ **Real-time Scoring** - Resultados en vivo (planeado)

## 🏗️ Arquitectura

**Clean Architecture** con 3 capas:
- **Domain**: Entities, Value Objects, Events, Repository interfaces
- **Application**: Use Cases, DTOs, Event Handlers
- **Infrastructure**: FastAPI, SQLAlchemy, External Services

**Patrones**: Repository + UoW, Domain Events, Value Objects, External Services

## 🧪 Testing

```bash
python dev_tests.py          # Full suite (679 tests, ~50s con paralelización)
pytest tests/unit/           # Unit tests (553 tests)
pytest tests/integration/    # Integration tests (126 tests)
pytest --cov=src             # Con cobertura
```

**Estadísticas**:
- **679 tests** pasando (100% ✅)
- **Competition Module**: 174 tests completos (domain, application, infrastructure)
- **Security Tests**: 12 tests (rate limiting + security headers)
- **Cobertura**: >90% en lógica de negocio

## 🔐 Seguridad

**Puntuación OWASP Top 10 2021**: 8.0/10 ✅

**Protecciones Implementadas**:
- ✅ **Rate Limiting** (SlowAPI) - Previene brute force, DoS (A04, A07)
  - Login: 5/min, Register: 3/hour, API externa: 5/hour
- ✅ **Security Headers HTTP** (secure) - Previene XSS, clickjacking, MITM (A02, A03, A04, A05, A07)
  - HSTS, X-Frame-Options, X-Content-Type-Options, Referrer-Policy, Cache-Control
- ✅ **HTTPS** obligatorio en producción (Render.com)
- ✅ **SQL Injection Protection** (SQLAlchemy ORM parameterizado)
- ✅ **JWT Authentication** con tokens seguros
- ✅ **Input Validation** (Pydantic schemas)
- ✅ **Password Hashing** (bcrypt)

**Pendiente**:
- ⏳ httpOnly Cookies (v1.8.0 próximo)
- ⏳ Password Policy Enforcement
- ⏳ Session Timeout + Refresh Tokens

Ver [docs/SECURITY_IMPLEMENTATION.md](docs/SECURITY_IMPLEMENTATION.md) para detalles completos.

## 🔄 CI/CD Pipeline

GitHub Actions ejecuta automáticamente en cada push:
- ✅ **Unit Tests** (Python 3.11, 3.12 en paralelo)
- ✅ **Integration Tests** (con PostgreSQL)
- ✅ **Security Scan** (Gitleaks - detección de secretos)
- ✅ **Code Quality** (Ruff linting)
- ✅ **Type Checking** (Mypy)
- ✅ **Database Migrations** (Alembic validation)

**Pipeline duration**: ~3 minutos | **Jobs**: 7 paralelos

Ver [ADR-021](docs/architecture/decisions/ADR-021-github-actions-ci-cd-pipeline.md) para decisiones técnicas.

### Endpoints API Disponibles

**30+ endpoints REST** organizados en módulos:
- **Auth** (4): registro, login, logout, verificación email
- **Users**: perfil, búsqueda, gestión
- **Handicaps** (3): actualización RFEG, manual, batch
- **Competitions** (10): CRUD + state transitions (activate, start, complete, etc.)
- **Enrollments** (8): solicitudes, aprobaciones, custom handicap
- **Countries** (2): listado, países adyacentes

**Documentación completa**:
- Swagger UI: `http://localhost:8000/docs`
- API Reference: [docs/API.md](docs/API.md)
- Frontend Examples: [docs/frontend-examples/](docs/frontend-examples/)

## 💻 Desarrollo

```bash
# Run app
uvicorn main:app --reload

# Database migrations
alembic revision --autogenerate -m "description"
alembic upgrade head

# Code quality (ejecutado en CI/CD)
ruff check src/ tests/        # Linting
mypy src/                     # Type checking
gitleaks detect --verbose     # Security scan
```

## 📊 Estado del Proyecto

**Fase 1: Foundation** ✅ Completado (16 Nov 2025)
- Clean Architecture + DDD completo
- User management + JWT authentication
- **Email Verification** con Mailgun (bilingüe)
- Login/Logout con Domain Events
- Session Management (Fase 1)
- Handicap system (RFEG integration + batch)
- **Dependency Injection refactoring** (DIP compliance)
- **440 tests** (100% passing, 0 warnings)
- 8 endpoints API funcionales

**Fase 2: Core Features** ✅ Completado (30 Nov 2025)
- **Competition Module - COMPLETO** ✅
  - Domain Layer: 2 entidades, 9 Value Objects, 11 Domain Events
  - Application Layer: 18 DTOs, 17 Use Cases
  - Infrastructure Layer: Repositorios SQLAlchemy, migraciones Alembic
  - API Layer: 20 endpoints REST (Competition + Enrollment + Countries)
  - 174 tests (97.6% passing)
- **CI/CD Pipeline** ✅ Implementado
  - GitHub Actions con 7 jobs paralelos
  - Tests automáticos (Python 3.11, 3.12)
  - Security scanning (Gitleaks)
  - Code quality (Ruff + Mypy)
  - Database migrations validation
- **Frontend Web Application** → [RyderCupWeb](https://github.com/agustinEDev/RyderCupWeb)

**Fase 3: Advanced** ⏳ Planeado
- Real-time updates (WebSockets)
- Statistics dashboard
- Mobile companion app
- Admin panel

## 🤝 Contribuir

```bash
# 1. Fork & clone
git checkout -b feature/amazing-feature

# 2. Desarrollar
# - Seguir Clean Architecture
# - Tests con >90% cobertura
# - Format con black

# 3. Tests
python dev_tests.py

# 4. PR
git push origin feature/amazing-feature
```

Ver convenciones en [docs/project-structure.md](docs/project-structure.md)

## 📄 Licencia

MIT License - ver [LICENSE](LICENSE)

## 👨‍💻 Contacto

- **Developer**: [Agustín Estévez](https://github.com/agustinEDev)
- **Repository**: [RyderCupAM](https://github.com/agustinEDev/RyderCupAM)
- **Issues**: [GitHub Issues](https://github.com/agustinEDev/RyderCupAM/issues)

---

⭐ Si te resulta útil, dale una estrella en GitHub
