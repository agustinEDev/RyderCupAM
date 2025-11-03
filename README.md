# Ryder Cup Manager

Aplicación para crear y gestionar competiciones tipo Ryder Cup entre amigos.

## 🎯 Visión del Proyecto

Una plataforma que permite a grupos de amigos organizar torneos de golf al estilo Ryder Cup, con equipos, emparejamientos, diferentes formatos de juego y seguimiento de puntuaciones.

## 🎉 Logros Destacados

### ✅ **Domain Layer Complete** (31 Oct 2025)
- **Clean Architecture**: Implementación completa con 3 capas separadas
- **Value Objects**: UserId, Email, Password con validación robusta
- **Type Safety**: 100% type hints con validación en tiempo de compilación
- **Error Handling**: Sistema completo de excepciones de dominio

### 🚀 **Performance Optimized Testing**
- **90% Speed Improvement**: De 5+ segundos a 0.54 segundos
- **Parallel Execution**: pytest-xdist con 7 workers
- **80 Tests**: Cobertura completa de la capa de dominio
- **Smart Categorization**: Organización automática por capas y objetos

### 📚 **Professional Documentation**
- **4 ADRs Complete**: Decisiones arquitectónicas documentadas
- **Design Document**: Visión completa del sistema
- **Development Tools**: Scripts optimizados para desarrollo rápido

## 🏗️ Arquitectura

**Monolito Modular con Clean Architecture**

### Principios Arquitectónicos

- **Independencia de Frameworks**: La lógica de negocio no depende de frameworks específicos
- **Testeable**: La lógica de negocio puede testearse sin UI, BD, o servicios externos
- **Independencia de UI**: La UI puede cambiar sin modificar la lógica de negocio
- **Independencia de Base de Datos**: Podemos cambiar la BD sin afectar las reglas de negocio
- **Independencia de Agentes Externos**: La lógica de negocio no conoce el mundo exterior

### Capas de la Arquitectura

```
┌─────────────────────────────────────────┐
│         Presentation Layer              │
│    (Schemas, Validators, Mappers)       │
└─────────────────────────────────────────┘
                  ↓
┌─────────────────────────────────────────┐
│        Application Layer                │
│  (Use Cases, Application Services)      │
│         + Unit of Work                  │
└─────────────────────────────────────────┘
                  ↓
┌─────────────────────────────────────────┐
│           Domain Layer                  │
│   (Entities, Value Objects, Rules)      │
│      + Repository Interfaces            │
└─────────────────────────────────────────┘
                  ↑
┌─────────────────────────────────────────┐
│       Infrastructure Layer              │
│  (DB, External APIs, Implementations)   │
│    + Unit of Work Implementation        │
└─────────────────────────────────────────┘
```

## 📦 Módulos del Sistema

### Módulo: User Management ✅ (Implementado)
Gestión completa de usuarios, autenticación y autorización.

**🎯 Domain Layer Completado:**
- ✅ **Entities**: User entity con validaciones completas
- ✅ **Value Objects**: UserId, Email, Password con encapsulación total
- ✅ **Domain Services**: Password hashing con bcrypt optimizado
- ✅ **Repository Interfaces**: Contratos definidos para persistencia

**📋 Application Layer:**
- 🔄 **Use Cases**: RegisterUser, LoginUser (en desarrollo)
- 🔄 **Unit of Work**: Patrón implementado para transacciones
- ⏳ **DTOs**: Request/Response objects

**🌐 Infrastructure Layer:**
- ⏳ **Repository Implementations**: Concrete database access
- ⏳ **Database Adapters**: SQLAlchemy integration

### Módulo: Competition Management (Futuro)
Creación y gestión de competiciones.

### Módulo: Team Management (Futuro)
Gestión de equipos y jugadores.

### Módulo: Match Management (Futuro)
Gestión de partidos y formatos de juego.

### Módulo: Scoring (Futuro)
Sistema de puntuación y resultados.

## 🚀 Roadmap

### Fase 1: Foundation ✅ (Completada - 31 Oct 2025)
- ✅ **Clean Architecture**: 3-layer separation implementada
- ✅ **Domain Layer**: Entities y Value Objects completamente implementados
- ✅ **User Management**: Sistema completo de validación y hashing
- ✅ **Testing Framework**: 80 tests con optimización de performance (0.54s)
- ✅ **Documentation**: ADRs completos y Design Document
- ✅ **Code Quality**: Type hints, validaciones, y error handling

### Fase 2: Repository & Transactions ✅ (Completada - 1 Nov 2025)
- ✅ **Repository Interfaces**: Contratos completos para persistencia (31 tests)
- ✅ **Unit of Work Pattern**: Gestión de transacciones implementada (18 tests)
- ✅ **Domain Exceptions**: Jerarquía completa de errores (21 tests)
- ✅ **Testing Excellence**: 150 tests en 0.59s con categorización profesional

### Fase 3: Application Layer 🚧 (Siguiente)
- ⏳ **Use Cases**: RegisterUser, LoginUser implementation
- ⏳ **Application Services**: Token management, validation
- ⏳ **DTOs**: Request/Response objects
- ⏳ **Domain Events**: Event-driven communication between modules
- ⏳ **Infrastructure Layer**: SQLAlchemy integration

### Fase 4: Gestión de Competiciones
- [ ] Crear competición
- [ ] Configurar formato
- [ ] Invitar participantes

### Fase 5: Gestión de Equipos
- [ ] Crear equipos
- [ ] Asignar jugadores
- [ ] Capitanes de equipo

### Fase 6: Gestión de Partidos
- [ ] Crear emparejamientos
- [ ] Formatos de juego (Foursome, Fourball, Singles)
- [ ] Calendario de partidos

### Fase 7: Sistema de Puntuación
- [ ] Registro de resultados
- [ ] Cálculo de puntos
- [ ] Clasificación en tiempo real

## 🛠️ Stack Tecnológico

| Componente | Tecnología | Versión | Status |
|------------|------------|---------|---------|
| **Backend** | Python | 3.12+ | ✅ |
| **Web Framework** | FastAPI | 0.115+ | ✅ |
| **Database** | PostgreSQL | 15+ | 🔄 |
| **ORM** | SQLAlchemy | 2.0+ | 🔄 |
| **Authentication** | JWT + bcrypt | 4.1.2 | ✅ |
| **Testing** | pytest + pytest-xdist | 8.3+ | ✅ |
| **Type Checking** | mypy | Latest | ✅ |
| **Code Quality** | black + ruff | Latest | ✅ |

**🚀 Performance Optimizations:**
- **Parallel Testing**: pytest-xdist con 7 workers
- **bcrypt Optimization**: Environment-based rounds (4 testing / 12 production)
- **Fast Feedback**: Custom test runner con categorización visual

## 📋 Requisitos

- **Python**: 3.12+ (recomendado para type hints avanzados)
- **PostgreSQL**: 15+ (para fase de infraestructura)
- **Dependencias**: Ver `requirements.txt` para lista completa
- **Memory**: 4GB RAM mínimo
- **CPU**: Multi-core recomendado para testing paralelo

## 🚀 Instalación y Configuración

### 1. Clonar el repositorio

```bash
git clone <repo-url>
cd ryder-cup-manager
```

### 2. Crear entorno virtual

```bash
python -m venv venv
source venv/bin/activate  # En Windows: venv\Scripts\activate
```

### 3. Instalar dependencias

```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt  # Para desarrollo
```

### 4. Configurar variables de entorno

```bash
cp .env.example .env
# Editar .env con tus configuraciones
```

### 5. Configurar base de datos

```bash
# Crear base de datos
createdb ryder_cup_manager

# Ejecutar migraciones
alembic upgrade head
```

### 6. Ejecutar la aplicación

```bash
uvicorn src.main:app --reload
```

La API estará disponible en `http://localhost:8000`
Documentación interactiva en `http://localhost:8000/docs`

## 🧪 Testing

### 🚀 Quick Start
```bash
# Ejecutar con script optimizado (recomendado)
python dev_tests.py

# Tests tradicionales
pytest
pytest -n auto  # Parallel execution
```

### 📊 **Testing Metrics (Actual)**
- **Total Tests**: 150 tests (+70 nuevos en nov-2025)
- **Execution Time**: 0.59 seconds (maintained excellence)
- **Parallelization**: 7 workers (pytest-xdist)
- **Coverage Target**: 90% domain + repository interfaces

### 🎯 Test Categories
```bash
# Por capa arquitectónica
pytest tests/domain/           # Domain logic tests
pytest tests/application/      # Use case tests  
pytest tests/infrastructure/   # Database tests

# Por objeto específico
pytest tests/ -k "User"        # All User-related tests
pytest tests/ -k "Email"       # Email value object tests
```

### 🔧 Performance Optimizations
- **bcrypt rounds**: 4 (testing) vs 12 (production)
- **Parallel execution**: Automatic worker detection
- **Fast feedback**: Visual categorization by layers

## 🔍 Linting y Formateo

```bash
# Formatear código
black src tests

# Linting
ruff check src tests

# Type checking
mypy src
```

## 📝 Convenciones de Código

- **Estilo**: PEP 8
- **Nombres de clases**: PascalCase
- **Nombres de funciones/variables**: snake_case
- **Nombres de constantes**: UPPER_SNAKE_CASE
- **Idioma del código**: Inglés
- **Idioma de documentación**: Español
- **Line length**: 100 caracteres

## 🗂️ Estructura del Proyecto

```
src/
├── modules/          # Módulos de negocio
│   └── user/        # Módulo de usuarios
│       ├── domain/          # Lógica de negocio
│       ├── application/     # Casos de uso + UoW
│       ├── infrastructure/  # Implementaciones + UoW Impl
│       └── presentation/    # Schemas y mappers
├── shared/          # Código compartido
│   ├── domain/      # Interfaces compartidas
│   └── infrastructure/  # Unit of Work base
├── config/          # Configuración
└── main.py          # Punto de entrada
```

## 🔄 Patrón Unit of Work

El proyecto implementa el patrón **Unit of Work** para gestionar transacciones y mantener la consistencia de datos.

### Beneficios
- ✅ **Transacciones atómicas**: Commit o rollback de todas las operaciones juntas
- ✅ **Consistencia**: Garantiza la integridad de los datos
- ✅ **Testeable**: Fácil de mockear en tests
- ✅ **Desacoplamiento**: Los casos de uso no dependen de la implementación de BD

### Uso en Casos de Uso

```python
async def execute(self, command: RegisterUserCommand) -> UserResponse:
    async with self._uow:
        # Operaciones con repositorios
        user = await User.create(...)
        await self._uow.users.save(user)
        
        # Commit automático al salir del context manager
        await self._uow.commit()
        
    return UserResponse(...)
```

## 📚 Documentación Completa

### 📖 Core Documentation
- **[Design Document](docs/design-document.md)** - Visión completa del sistema
- **[Project Structure](docs/project-structure.md)** - Organización del código
- **[User Management Module](docs/modules/user-management.md)** - Documentación específica

### 🏗️ Architecture Decision Records (ADRs)
- **[ADR-001](docs/architecture/decisions/ADR-001-clean-architecture.md)** - Clean Architecture adoption
- **[ADR-002](docs/architecture/decisions/ADR-002-value-objects.md)** - Value Objects implementation
- **[ADR-003](docs/architecture/decisions/ADR-003-testing-strategy.md)** - Testing strategy & optimization
- **[ADR-004](docs/architecture/decisions/ADR-004-tech-stack.md)** - Technology stack decisions
- **[ADR-005](docs/architecture/decisions/ADR-005-repository-pattern.md)** - Repository Pattern implementation
- **[ADR-006](docs/architecture/decisions/ADR-006-unit-of-work-pattern.md)** - Unit of Work for transaction management
- **[ADR-007](docs/architecture/decisions/ADR-007-domain-events-pattern.md)** - Domain Events for event-driven architecture

### 📋 Progress Tracking
- **[Progress Log](PROGRESS_LOG.md)** - Detailed development timeline

## 🔐 Variables de Entorno

```bash
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/ryder_cup_manager

# JWT
SECRET_KEY=your-secret-key-here
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# Application
DEBUG=True
ENVIRONMENT=development
```

## � Quick Development Start

```bash
# 1. Setup environment
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# 2. Run optimized tests
python dev_tests.py

# 3. Start development (when ready)
uvicorn src.main:app --reload
```

## �📊 API Endpoints

### 🔐 Authentication (Planned)
- `POST /api/v1/auth/register` - User registration
- `POST /api/v1/auth/login` - User login
- `POST /api/v1/auth/refresh` - Token refresh

### 👥 Users (Planned)  
- `GET /api/v1/users/profile` - Get current user profile
- `PUT /api/v1/users/profile` - Update user profile

**📖 Documentation**: Available at `/docs` (Swagger UI) when server is running

## 🤝 Contribución

1. Fork el proyecto
2. Crea una rama para tu feature (`git checkout -b feature/AmazingFeature`)
3. Commit tus cambios (`git commit -m 'Add some AmazingFeature'`)
4. Push a la rama (`git push origin feature/AmazingFeature`)
5. Abre un Pull Request

## 📄 Licencia

Este proyecto es de uso privado.

## 👥 Autores

Tu equipo de desarrollo