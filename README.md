# 🏆 Ryder Cup Amateur Manager - Backend API

> REST API para gestión de torneos de golf amateur formato Ryder Cup

[![Tests](https://img.shields.io/badge/tests-360%20passing-success)](.)
[![Python](https://img.shields.io/badge/python-3.12+-blue)](.)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688)](.)
[![Architecture](https://img.shields.io/badge/architecture-Clean%20Architecture-green)](.)

## 🌐 Frontend

Este es el **backend API**. Para la aplicación web frontend, visita:
👉 **[RyderCupAm-Web](https://github.com/agustinEDev/RyderCupAm-Web)** *(próximamente)*

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
```

Ver guía completa en [RENDER_DEPLOYMENT.md](RENDER_DEPLOYMENT.md)

## 📚 Documentación

- **[Comandos](CLAUDE.md)** - Desarrollo diario
- **[Estructura](docs/project-structure.md)** - Organización del código
- **[Design Doc](docs/design-document.md)** - Especificación técnica
- **[ADRs](docs/architecture/decisions/)** - Decisiones arquitectónicas
- **[API](docs/API.md)** - Endpoints
- **[Deploy](docs/RUNBOOK.md)** - Operaciones

## 🛠️ Stack Tecnológico

Python 3.12+ · FastAPI · PostgreSQL 15+ · SQLAlchemy 2.0 · Clean Architecture + DDD

## ✨ Features API

- ✅ **User Management** - Registro, autenticación JWT, gestión de perfil
- ✅ **Authentication** - Login/Logout con tokens JWT + Domain Events
- ✅ **Handicap System** - Integración RFEG, actualización automática y batch
- ✅ **Session Management** - Estrategia progresiva (Fase 1 implementada)
- 🚧 **Tournament Management** - Creación y gestión de torneos (próximamente)
- ⏳ **Real-time Scoring** - Resultados en vivo (planeado)

## 🏗️ Arquitectura

**Clean Architecture** con 3 capas:
- **Domain**: Entities, Value Objects, Events, Repository interfaces
- **Application**: Use Cases, DTOs, Event Handlers
- **Infrastructure**: FastAPI, SQLAlchemy, External Services

**Patrones**: Repository + UoW, Domain Events, Value Objects, External Services

## 🧪 Testing

```bash
python dev_tests.py          # Full suite (360 tests, ~12s)
pytest tests/unit/           # Unit tests (313)
pytest tests/integration/    # Integration tests (47)
pytest --cov=src             # Con cobertura
```

**Cobertura**: >90% en lógica de negocio

### Endpoints API Disponibles

```bash
# Authentication
POST   /api/v1/auth/register         # User registration
POST   /api/v1/auth/login            # JWT authentication
POST   /api/v1/auth/logout           # Logout with audit

# Handicap Management
POST   /api/v1/handicaps/update              # RFEG lookup + fallback
POST   /api/v1/handicaps/update-manual       # Manual update
POST   /api/v1/handicaps/update-multiple     # Batch processing

# User Management
GET    /api/v1/users/search          # Search by email/name
```

**Documentación completa**: `http://localhost:8000/docs` (Swagger UI)

## 💻 Desarrollo

```bash
# Run app
uvicorn main:app --reload

# Database migrations
alembic revision --autogenerate -m "description"
alembic upgrade head

# Code quality
black src/ tests/
mypy src/
```

## 📊 Estado del Proyecto

**Fase 1: Foundation** ✅ Completado (9 Nov 2025)
- Clean Architecture + DDD completo
- User management + JWT authentication
- Login/Logout con Domain Events
- Session Management (Fase 1)
- Handicap system (RFEG integration + batch)
- 360 tests (100% passing)
- 7 endpoints API funcionales

**Fase 2: Core Features** 🚧 En desarrollo
- Tournament CRUD operations
- Team formation algorithms
- Basic scoring system
- **Frontend Web Application** → [RyderCupAm-Web](https://github.com/agustinEDev/RyderCupAm-Web)

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
