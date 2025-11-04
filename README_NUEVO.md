# 🏆 Ryder Cup Amateur Manager

<div align="center">

![Badge-Python](https://img.shields.io/badge/Python-3.12+-3776ab?style=for-the-badge&logo=python&logoColor=white)
![Badge-FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![Badge-PostgreSQL](https://img.shields.io/badge/PostgreSQL-15+-336791?style=for-the-badge&logo=postgresql&logoColor=white)
![Badge-SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0+-red?style=for-the-badge&logo=python&logoColor=white)
![Badge-Docker](https://img.shields.io/badge/Docker-Ready-2496ed?style=for-the-badge&logo=docker&logoColor=white)

**Un sistema completo de gestión de torneos de golf amateur siguiendo el prestigioso formato Ryder Cup**

*Arquitectura limpia • Domain-Driven Design • Testing exhaustivo • Documentación completa*

---

[🚀 **Inicio Rápido**](#-inicio-rápido) • [📖 **Documentación**](#-documentación) • [🏗️ **Arquitectura**](#️-arquitectura) • [🧪 **Testing**](#-testing-strategy) • [📊 **Estado del Proyecto**](#-estado-del-proyecto)

---

</div>

## 🎯 Visión del Proyecto

El **Ryder Cup Amateur Manager** es una aplicación de gestión de torneos de golf que replica el emocionante formato de equipos de la prestigiosa Ryder Cup profesional. Diseñado para organizar competiciones amateur entre equipos Europa vs Estados Unidos, el sistema ofrece gestión completa de jugadores, cálculo automático de handicaps y seguimiento en tiempo real de resultados.

### ✨ Características Principales

- 🏌️ **Gestión de Torneos** - Creación y administración de competiciones formato Ryder Cup
- 👥 **Equipos Europa vs USA** - Formación automática de equipos con balance competitivo
- 🎯 **Sistema de Handicaps** - Cálculo automático y ajuste por condiciones del campo
- 📊 **Scoring en Tiempo Real** - Resultados y estadísticas actualizadas instantáneamente
- 🏆 **Gestión de Formatos** - Soporte para fourball, foursomes y singles
- 📱 **Interface Responsiva** - Acceso optimizado desde cualquier dispositivo
- 🔐 **Seguridad Robusta** - Autenticación JWT con encriptación bcrypt
- 🌐 **API RESTful** - Documentación automática con OpenAPI/Swagger

## 🏗️ Arquitectura

### Clean Architecture + Domain-Driven Design

El proyecto implementa **Clean Architecture** con principios de **Domain-Driven Design**, garantizando mantenibilidad, testabilidad y escalabilidad.

```mermaid
graph TB
    subgraph "🌐 Infrastructure Layer"
        FastAPI[FastAPI Web Framework]
        PostgreSQL[(PostgreSQL Database)]
        SQLAlchemy[SQLAlchemy ORM]
        Docker[Docker Containers]
        JWT[JWT Authentication]
    end
    
    subgraph "📋 Application Layer"
        UseCases[Use Cases]
        DTOs[Data Transfer Objects]
        Handlers[Event Handlers]
        Services[Application Services]
    end
    
    subgraph "🎯 Domain Layer"
        Entities[Domain Entities]
        ValueObjects[Value Objects]
        Events[Domain Events]
        Repositories[Repository Interfaces]
        Rules[Business Rules]
    end
    
    FastAPI --> UseCases
    UseCases --> Entities
    SQLAlchemy --> Repositories
    Handlers --> Events
    Services --> DTOs
    
    classDef infrastructure fill:#e1f5fe
    classDef application fill:#f3e5f5
    classDef domain fill:#e8f5e8
    
    class FastAPI,PostgreSQL,SQLAlchemy,Docker,JWT infrastructure
    class UseCases,DTOs,Handlers,Services application
    class Entities,ValueObjects,Events,Repositories,Rules domain
```

### 📦 Estructura Modular

```mermaid
graph LR
    subgraph "🏗️ Clean Architecture Layers"
        subgraph "Domain"
            User[👤 User Entity]
            Email[📧 Email VO]
            Password[🔐 Password VO]
            Events[📢 Domain Events]
        end
        
        subgraph "Application"
            RegisterUC[📝 Register Use Case]
            LoginUC[🔑 Login Use Case]
            EventHandlers[🎯 Event Handlers]
        end
        
        subgraph "Infrastructure"
            API[🌐 FastAPI]
            DB[🗄️ PostgreSQL]
            Repos[📊 Repositories]
        end
    end
    
    API --> RegisterUC
    RegisterUC --> User
    User --> Events
    Events --> EventHandlers
    Repos --> DB
    
    classDef domain fill:#e8f5e8,stroke:#4caf50,stroke-width:2px
    classDef application fill:#fff3e0,stroke:#ff9800,stroke-width:2px
    classDef infrastructure fill:#e3f2fd,stroke:#2196f3,stroke-width:2px
    
    class User,Email,Password,Events domain
    class RegisterUC,LoginUC,EventHandlers application
    class API,DB,Repos infrastructure
```

### 🔄 Patrones de Diseño Implementados

#### Repository Pattern + Unit of Work

```mermaid
sequenceDiagram
    participant UC as Use Case
    participant UoW as Unit of Work
    participant Repo as Repository
    participant DB as Database
    participant Event as Event Bus
    
    UC->>UoW: async with uow:
    UoW->>Repo: uow.users.save(user)
    Repo->>DB: INSERT/UPDATE
    UC->>UoW: await uow.commit()
    UoW->>Event: publish_events()
    Event->>UC: events handled
    
    Note over UC,Event: Transaccional + Event-Driven
```

#### Domain Events Pattern

```mermaid
graph LR
    subgraph "🎯 Domain Entity"
        User[User.create] --> Event[UserRegisteredEvent]
    end
    
    subgraph "📢 Event Publishing"
        Event --> EventBus[Event Bus]
    end
    
    subgraph "🎯 Event Handlers"
        EventBus --> Welcome[Welcome Email]
        EventBus --> Audit[Audit Log]
        EventBus --> Metrics[User Metrics]
    end
    
    classDef event fill:#fff3e0,stroke:#ff9800,stroke-width:2px
    classDef handler fill:#e8f5e8,stroke:#4caf50,stroke-width:2px
    
    class Event,EventBus event
    class Welcome,Audit,Metrics handler
```

## 🚀 Inicio Rápido

### Prerrequisitos

- **Docker** y **Docker Compose** instalados
- **Python 3.12+** (para desarrollo local)
- **Git** para clonar el repositorio

### 🐳 Configuración con Docker (Recomendado)

```bash
# 1. Clonar el repositorio
git clone https://github.com/agustinEDev/RyderCupAM.git
cd RyderCupAM

# 2. Configurar variables de entorno
cp .env.example .env
# Editar .env con tus configuraciones

# 3. Levantar el entorno completo
docker-compose up -d

# 4. Ejecutar migraciones de base de datos
docker-compose exec app alembic upgrade head

# 5. ¡Listo! La API está disponible en http://localhost:8000
```

### 🔧 Desarrollo Local

```bash
# 1. Crear entorno virtual
python -m venv venv
source venv/bin/activate  # macOS/Linux
# venv\Scripts\activate    # Windows

# 2. Instalar dependencias
pip install -r requirements.txt

# 3. Configurar base de datos (requiere PostgreSQL)
export DATABASE_URL="postgresql://user:pass@localhost:5432/ryderdb"
alembic upgrade head

# 4. Ejecutar servidor de desarrollo
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

### ⚡ Verificación de la Instalación

```bash
# Verificar que la API responde
curl http://localhost:8000/health

# Acceder a la documentación interactiva
open http://localhost:8000/docs
```

## 🧪 Testing Strategy

### 🎯 Test Pyramid Implementado

```mermaid
pyramid
    title Test Strategy
    top "🌐 E2E Tests (5%)"
    middle "🔄 Integration Tests (15%)"
    bottom "🔧 Unit Tests (80%)"
```

### 📊 Estado Actual de Tests

```
📊 Estadísticas de Testing (215 tests total)
├── 🔧 Tests Unitarios: 195/195 (100% éxito)
│   ├── Domain Entities: 73 tests
│   ├── Value Objects: 49 tests  
│   ├── Repository Interfaces: 31 tests
│   ├── Unit of Work: 18 tests
│   ├── Domain Events: 52 tests
│   └── Excepciones: 21 tests
│
├── 🔗 Tests de Integración: 20/20 (100% éxito)
│   ├── API Endpoints: 13 tests
│   └── Domain Events Integration: 7 tests
│
└── ⚡ Performance: 215 tests en ~8 segundos (paralelización)
```

### 🚀 Ejecutar Tests

```bash
# Ejecutar todos los tests con el script optimizado
python dev_tests.py

# Tests específicos
pytest tests/unit/                    # Solo unit tests
pytest tests/integration/             # Solo integration tests
pytest tests/unit/modules/user/       # Tests del módulo user

# Con cobertura
pytest --cov=src --cov-report=html
```

## 📊 Estado del Proyecto

### 🎯 Roadmap de Desarrollo

```mermaid
gantt
    title Desarrollo del Proyecto
    dateFormat  YYYY-MM-DD
    section Fase 1: Foundation ✅
    Clean Architecture Setup    :done, arch, 2024-10-01, 2024-10-15
    User Management            :done, user, 2024-10-15, 2024-10-30
    Authentication & Security  :done, auth, 2024-10-25, 2024-11-05
    Testing Framework         :done, test, 2024-11-01, 2024-11-10
    Documentation            :done, docs, 2024-11-05, 2024-11-15
    
    section Fase 2: Core Features 🚧
    Tournament Management    :active, tour, 2024-11-15, 2024-12-15
    Team Formation          :team, 2024-12-01, 2024-12-30
    Basic Scoring System    :score, 2024-12-15, 2025-01-15
    
    section Fase 3: Advanced Features ⏳
    Handicap Calculation    :handicap, 2025-01-15, 2025-02-15
    Real-time Updates      :realtime, 2025-02-01, 2025-03-01
    Statistics Dashboard   :stats, 2025-02-15, 2025-03-15
    
    section Fase 4: Production 🎯
    Performance Optimization :perf, 2025-03-15, 2025-04-15
    Mobile App Companion    :mobile, 2025-04-01, 2025-05-15
    Advanced Analytics     :analytics, 2025-05-01, 2025-06-01
```

### ✅ Características Implementadas

- **✅ Foundation (100% Complete)**
  - Clean Architecture con Domain-Driven Design
  - User management completo con Value Objects
  - Sistema de autenticación JWT + bcrypt
  - Repository Pattern con Unit of Work
  - Domain Events con Event Bus
  - Testing framework optimizado (215 tests)
  - Documentación completa con ADRs

- **🚧 En Desarrollo**
  - Tournament management system
  - Team formation algorithms
  - Handicap calculation engine

- **⏳ Planificado**
  - Real-time scoring updates
  - Advanced tournament formats
  - Mobile companion app
  - Statistical analytics

## 🛠️ Stack Tecnológico

### Backend Core
- **Python 3.12+** - Lenguaje principal con type hints avanzados
- **FastAPI 0.115+** - Framework web async con documentación automática
- **SQLAlchemy 2.0+** - ORM con soporte async y type safety
- **PostgreSQL 15+** - Base de datos principal con extensiones JSON
- **Alembic** - Manejo de migraciones de base de datos

### Infrastructure & DevOps
- **Docker & Docker Compose** - Containerización y orquestación
- **JWT + bcrypt** - Autenticación stateless y hashing seguro
- **pytest + pytest-xdist** - Testing framework con paralelización
- **Git + GitHub** - Control de versiones y CI/CD

### Architecture Patterns
- **Clean Architecture** - Separación de responsabilidades en capas
- **Domain-Driven Design** - Modelado rico del dominio de negocio
- **Repository Pattern** - Abstracción de la capa de persistencia
- **Unit of Work** - Gestión transaccional
- **Domain Events** - Comunicación desacoplada entre componentes

## 📖 Documentación

### 📚 Documentación Principal

- **[Design Document](docs/design-document.md)** - Diseño completo del sistema
- **[Project Structure](docs/project-structure.md)** - Organización del código
- **[Architecture Decisions](docs/architecture/decisions/)** - ADRs y decisiones técnicas
- **[API Documentation](http://localhost:8000/docs)** - Swagger/OpenAPI interactivo

### 🎯 Guías de Desarrollo

- **[Testing Guide](tests/README.md)** - Estrategias y mejores prácticas de testing
- **[Module Documentation](docs/modules/)** - Documentación específica por módulo
- **[Contributing Guide](CONTRIBUTING.md)** - Guía para contribuidores

### 📋 ADRs (Architecture Decision Records)

| ADR | Decisión | Estado |
|-----|----------|--------|
| [ADR-001](docs/architecture/decisions/ADR-001-clean-architecture.md) | Clean Architecture | ✅ Implementado |
| [ADR-002](docs/architecture/decisions/ADR-002-value-objects.md) | Value Objects | ✅ Implementado |
| [ADR-003](docs/architecture/decisions/ADR-003-testing-strategy.md) | Testing Strategy | ✅ Implementado |
| [ADR-004](docs/architecture/decisions/ADR-004-tech-stack.md) | Tech Stack | ✅ Implementado |
| [ADR-005](docs/architecture/decisions/ADR-005-repository-pattern.md) | Repository Pattern | ✅ Implementado |
| [ADR-006](docs/architecture/decisions/ADR-006-unit-of-work.md) | Unit of Work | ✅ Implementado |
| [ADR-007](docs/architecture/decisions/ADR-007-domain-events.md) | Domain Events | ✅ Implementado |
| [ADR-009](docs/architecture/decisions/ADR-009-docker-environment.md) | Docker Environment | ✅ Implementado |
| [ADR-010](docs/architecture/decisions/ADR-010-alembic-migrations.md) | Alembic Migrations | ✅ Implementado |

## 🔧 API Reference

### 🔐 Authentication Endpoints

```http
POST   /api/v1/auth/register     # User registration
POST   /api/v1/auth/login        # User authentication  
POST   /api/v1/auth/logout       # User logout
POST   /api/v1/auth/refresh      # Token refresh
```

### 👤 User Management

```http
GET    /api/v1/users/profile     # Get current user profile
PUT    /api/v1/users/profile     # Update user profile
GET    /api/v1/users/{user_id}   # Get user by ID
```

### 🏆 Tournament Management (Planned)

```http
GET    /api/v1/tournaments       # List tournaments
POST   /api/v1/tournaments       # Create tournament
GET    /api/v1/tournaments/{id}  # Get tournament details
PUT    /api/v1/tournaments/{id}  # Update tournament
```

### 📊 Health & Monitoring

```http
GET    /health                   # Health check endpoint
GET    /docs                     # Interactive API documentation
GET    /redoc                    # Alternative API documentation
```

## 🤝 Contribución

### 🚀 Proceso de Contribución

1. **Fork** el repositorio
2. **Crear** una rama para tu feature (`git checkout -b feature/amazing-feature`)
3. **Implementar** los cambios siguiendo las convenciones del proyecto
4. **Ejecutar** tests y asegurar 100% de cobertura en nuevos componentes
5. **Commit** tus cambios (`git commit -m 'Add amazing feature'`)
6. **Push** a la rama (`git push origin feature/amazing-feature`)
7. **Abrir** un Pull Request con descripción detallada

### 📋 Estándares de Código

- **Style Guide**: PEP 8 + Black formatter
- **Type Hints**: Obligatorios en todo el código
- **Testing**: Cobertura mínima 90% para nuevas features
- **Documentation**: Docstrings estilo Google para todas las funciones públicas
- **Architecture**: Seguir Clean Architecture y principios DDD

### 🧪 Quality Gates

```bash
# Antes de cada commit
black src/ tests/                # Formateo de código
mypy src/                        # Type checking
pytest --cov=src --cov-fail-under=90  # Tests con cobertura
```

## 📄 Licencia

Este proyecto está bajo la licencia MIT. Ver el archivo [LICENSE](LICENSE) para más detalles.

## 📧 Contacto y Soporte

### 👨‍💻 Equipo de Desarrollo

- **Lead Developer**: [Agustín Estévez](mailto:agustin@ryderclub.com)
- **GitHub**: [@agustinEDev](https://github.com/agustinEDev)
- **Project Repository**: [RyderCupAM](https://github.com/agustinEDev/RyderCupAM)

### 🐛 Reportar Issues

Si encuentras un bug o tienes una sugerencia de mejora:

1. Revisa los [issues existentes](https://github.com/agustinEDev/RyderCupAM/issues)
2. Si no existe, [crea un nuevo issue](https://github.com/agustinEDev/RyderCupAM/issues/new)
3. Proporciona la máxima información posible para reproducir el problema

### 💬 Comunidad

- **Discussions**: [GitHub Discussions](https://github.com/agustinEDev/RyderCupAM/discussions)
- **Updates**: Sigue el proyecto para recibir notificaciones de nuevas releases

---

<div align="center">

**⭐ Si este proyecto te resulta útil, considera darle una estrella en GitHub ⭐**

*Desarrollado con ❤️ para la comunidad de golf amateur*

![Visitors](https://visitor-badge.laobi.icu/badge?page_id=agustinEDev.RyderCupAM)

</div>