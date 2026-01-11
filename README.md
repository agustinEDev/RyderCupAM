# 🏆 Ryder Cup Amateur Manager - Backend API

> REST API para gestión de torneos de golf amateur formato Ryder Cup

[![Tests](https://img.shields.io/badge/tests-1021%20passing-success)](.)
[![Python](https://img.shields.io/badge/python-3.11--3.12-blue)](.)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.125-009688)](.)
[![Architecture](https://img.shields.io/badge/architecture-Clean%20Architecture-green)](.)
[![CI/CD](https://img.shields.io/badge/CI%2FCD-GitHub%20Actions-2088FF)](.)
[![Security](https://img.shields.io/badge/security-9.2%2F10-success)](.)
[![OWASP](https://img.shields.io/badge/OWASP-ASVS%20V2.1-blue)](https://owasp.org/www-project-application-security-verification-standard/)

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
- ✅ **Security** (v1.13.0) - httpOnly cookies, session timeout, account lockout, CSRF protection, password history, **device fingerprinting con auto-registro**, security logging, Sentry monitoring
- ✅ **Handicap System** - Integración RFEG, actualización manual y batch
- ✅ **Competition Module** - CRUD completo, state transitions, enrollment system (20 endpoints)
- ✅ **Countries** - 166 países con 614 relaciones de fronteras, soporte multilenguaje
- ⏳ **RAG Chatbot** - Asistente de reglamento de golf (v1.15.0 planeado)
- ⏳ **Real-time Scoring** - Resultados en vivo (planeado)

## 🏗️ Arquitectura

**Clean Architecture** con 3 capas:
- **Domain**: Entities, Value Objects, Events, Repository interfaces
- **Application**: Use Cases, DTOs, Event Handlers
- **Infrastructure**: FastAPI, SQLAlchemy, External Services

**Patrones**: Repository + UoW, Domain Events, Value Objects, External Services

## 🧪 Testing

```bash
python dev_tests.py          # Full suite (1021 tests, ~61s con paralelización)
pytest tests/unit/           # Unit tests (800+ tests)
pytest tests/integration/    # Integration tests (180+ tests)
pytest tests/security/       # Security tests (40+ tests)
pytest --cov=src             # Con cobertura
```

**Estadísticas**:
- **1021 tests** pasando (100% ✅) en ~61 segundos ⭐ Actualizado (10 Ene 2026)
- **Competition Module**: 174 tests completos (domain, application, infrastructure)
- **User Module**: 680+ tests (incluye password policy + session timeout + account lockout + device fingerprinting)
- **Security Tests**: 45+ tests (rate limiting + CSRF + account lockout + XSS + SQL injection + auth bypass)
- **Cobertura**: >90% en lógica de negocio
- **Fix de paralelización**: UUID único por BD de test (pytest-xdist)

## 🔐 Seguridad

**Puntuación OWASP Top 10 2021**: 9.2/10 ✅ (+2.0 tras v1.8.0-v1.13.0)

**Protecciones Implementadas (v1.13.0)**:
- ✅ **httpOnly Cookies** (dual support) - Previene XSS en tokens (A01, A02)
  - Cookies httpOnly para access_token y refresh_token
  - Compatibilidad transitoria con Authorization header
  - Middleware dual con prioridad a cookies
- ✅ **Session Timeout** - Tokens de corta duración (A01, A02, A07)
  - Access token: 15 minutos (reducido de 60min)
  - Refresh token: 7 días con revocación
  - Logout revoca todos los refresh tokens
- ✅ **Security Logging** - Audit trail completo (A09)
  - 8 tipos de eventos de seguridad en JSON
  - Archivo dedicado security_audit.log con rotación
  - Correlation IDs para trazabilidad
- ✅ **Sentry Integration** - Error tracking y APM (A09)
  - Performance monitoring (10% traces)
  - Profiling de código (5% profiles)
  - Alertas configurables
- ✅ **Password Policy** (OWASP ASVS V2.1) - Contraseñas robustas (A07)
  - Mínimo 12 caracteres (ASVS V2.1.1)
  - Complejidad completa: mayúsculas + minúsculas + dígitos + símbolos (ASVS V2.1.2)
  - Blacklist de contraseñas comunes (ASVS V2.1.7)
  - bcrypt con 12 rounds (4 rounds en tests)
- ✅ **Rate Limiting** (SlowAPI) - Previene brute force, DoS (A04, A07)
  - Login: 5/min, Register: 3/hour, API externa: 5/hour
- ✅ **Security Headers HTTP** (secure) - Previene XSS, clickjacking, MITM (A02, A03, A04, A05, A07)
  - HSTS, X-Frame-Options, X-Content-Type-Options, Referrer-Policy, Cache-Control
- ✅ **Input Validation & Sanitization** - Previene XSS e inyecciones (A03)
  - Sanitización HTML con bleach
  - Validadores Pydantic estrictos con límites de longitud
- ✅ **CORS Configuration** - Whitelist estricta (A05, A01)
- ✅ **HTTPS** obligatorio en producción (Render.com)
- ✅ **SQL Injection Protection** (SQLAlchemy ORM parameterizado)
- ✅ **JWT Authentication** con tokens seguros
- ✅ **Account Lockout** (v1.13.0) - Bloqueo tras 10 intentos fallidos, auto-desbloqueo 30min (A07)
- ✅ **CSRF Protection** (v1.13.0) - Triple capa: header + cookie + SameSite (A01)
- ✅ **Password History** (v1.13.0) - Previene reutilización últimas 5 contraseñas (A07)
- ✅ **Device Fingerprinting** (v1.13.0) - Auto-registro en login/refresh, gestión dispositivos (A01)

**Pendiente**:
- ⏳ 2FA/MFA (no crítico, OWASP score ya 9.2/10)

Ver [docs/SECURITY_IMPLEMENTATION.md](docs/SECURITY_IMPLEMENTATION.md) para detalles completos.

## 🔄 CI/CD Pipeline

GitHub Actions ejecuta automáticamente en cada push:
- ✅ **Unit Tests** (Python 3.11, 3.12 en paralelo)
- ✅ **Integration Tests** (con PostgreSQL)
- ✅ **Security Checks**
  - Dependency Audit (safety + pip-audit) - **Pipeline falla si encuentra CVEs**
  - Gitleaks (detección de secretos)
  - Bandit (security linting)
- ✅ **Code Quality** (Ruff linting)
- ✅ **Type Checking** (Mypy)
- ✅ **Database Migrations** (Alembic validation)

**Pipeline duration**: ~3 minutos | **Jobs**: 7 paralelos | **Reports**: 30 días retención

Ver [ADR-021](docs/architecture/decisions/ADR-021-github-actions-ci-cd-pipeline.md) para decisiones técnicas.

### Endpoints API Disponibles

**30+ endpoints REST** organizados en módulos:
- **Auth** (5): registro, login, logout, verificación email, refresh token
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
