# 🏆 Ryder Cup Amateur Manager

> Sistema de gestión de torneos de golf amateur formato Ryder Cup

[![Tests](https://img.shields.io/badge/tests-330%20passing-success)](.)
[![Python](https://img.shields.io/badge/python-3.12+-blue)](.)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688)](.)

## 🚀 Quick Start

```bash
# Clone
git clone https://github.com/agustinEDev/RyderCupAM.git
cd RyderCupAM

# Setup con Docker (recomendado)
docker-compose up -d
docker-compose exec app alembic upgrade head

# Acceder
open http://localhost:8000/docs
```

## 📚 Documentación

- **[Comandos](CLAUDE.md)** - Desarrollo diario
- **[Estructura](docs/project-structure.md)** - Organización del código
- **[Design Doc](docs/design-document.md)** - Especificación técnica
- **[ADRs](docs/architecture/decisions/)** - Decisiones arquitectónicas
- **[API](docs/API.md)** - Endpoints
- **[Deploy](docs/RUNBOOK.md)** - Operaciones

## 🛠️ Stack Tecnológico

Python 3.12+ · FastAPI · PostgreSQL 15+ · SQLAlchemy 2.0 · Clean Architecture + DDD

## ✨ Features

- ✅ **User Management** - Registro, autenticación JWT
- ✅ **Handicap System** - Integración RFEG, actualización automática
- 🚧 **Tournament Management** - Creación y gestión de torneos
- ⏳ **Real-time Scoring** - Resultados en vivo

## 🏗️ Arquitectura

**Clean Architecture** con 3 capas:
- **Domain**: Entities, Value Objects, Events, Repository interfaces
- **Application**: Use Cases, DTOs, Event Handlers
- **Infrastructure**: FastAPI, SQLAlchemy, External Services

**Patrones**: Repository + UoW, Domain Events, Value Objects, External Services

## 🧪 Testing

```bash
python dev_tests.py          # Full suite (330 tests, ~8s)
pytest tests/unit/           # Unit tests (302)
pytest tests/integration/    # Integration tests (28)
pytest --cov=src             # Con cobertura
```

**Cobertura**: >90% en lógica de negocio

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

**Fase 1: Foundation** ✅ Completado
- Clean Architecture + DDD
- User management + JWT auth
- Handicap system (RFEG integration)
- 330 tests (100% passing)

**Fase 2: Core Features** 🚧 En desarrollo
- Tournament management
- Team formation algorithms
- Basic scoring system

**Fase 3: Advanced** ⏳ Planeado
- Real-time updates
- Statistics dashboard
- Mobile companion app

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
