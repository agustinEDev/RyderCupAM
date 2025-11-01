# Ryder Cup Amateur Manager - Design Document

**Versión**: 1.0  
**Fecha**: 31 de octubre de 2025  
**Autor**: Equipo de Desarrollo  
**Estado**: En desarrollo

---

## 📋 Tabla de Contenidos

1. [Visión General](#-visión-general)
2. [Objetivos del Sistema](#-objetivos-del-sistema)
3. [Arquitectura del Sistema](#-arquitectura-del-sistema)
4. [Decisiones Técnicas](#-decisiones-técnicas)
5. [Módulos del Sistema](#-módulos-del-sistema)
6. [Modelos de Datos](#-modelos-de-datos)
7. [API Design](#-api-design)
8. [Seguridad](#-seguridad)
9. [Testing Strategy](#-testing-strategy)
10. [Deployment](#-deployment)
11. [Roadmap](#-roadmap)

---

## 🎯 Visión General

El **Ryder Cup Amateur Manager** es un sistema completo de gestión de torneos de golf amateur que simula el formato de la prestigiosa Ryder Cup profesional. El sistema permite organizar competiciones entre equipos, gestionar jugadores, calcular handicaps y administrar resultados en tiempo real.

### Características Principales

- 🏌️ **Gestión de Torneos**: Creación y administración de competiciones formato Ryder Cup
- 👥 **Gestión de Equipos**: Formación de equipos Europa vs Estados Unidos
- 🎯 **Sistema de Handicaps**: Cálculo automático y ajuste de handicaps
- 📊 **Seguimiento en Tiempo Real**: Resultados y estadísticas actualizadas
- 🏆 **Gestión de Resultados**: Registro y validación de scores
- 📱 **Interface Responsiva**: Acceso desde dispositivos móviles y desktop

---

## 🎯 Objetivos del Sistema

### Objetivos Funcionales

1. **Simplicidad de Uso**: Interface intuitiva para organizadores y jugadores
2. **Precisión**: Cálculos exactos de handicaps y resultados
3. **Flexibilidad**: Adaptable a diferentes formatos de torneo
4. **Transparencia**: Información clara y accesible para todos los participantes
5. **Escalabilidad**: Soporte para múltiples torneos simultáneos

### Objetivos No Funcionales

- **Performance**: Respuesta < 200ms en operaciones críticas
- **Disponibilidad**: 99.9% uptime durante torneos
- **Seguridad**: Protección de datos personales y resultados
- **Mantenibilidad**: Código limpio y bien documentado
- **Usabilidad**: Interface responsive y accesible

---

## 🏗️ Arquitectura del Sistema

### Clean Architecture

El sistema implementa **Clean Architecture** con 3 capas principales:

```
┌─────────────────────────────────────┐
│           🌐 Infrastructure         │
│  (FastAPI, SQLAlchemy, PostgreSQL) │
├─────────────────────────────────────┤
│           📋 Application            │
│    (Use Cases, Services, DTOs)     │
├─────────────────────────────────────┤
│            🎯 Domain               │
│   (Entities, Value Objects, Rules) │
└─────────────────────────────────────┘
```

#### Capas Detalladas

**🎯 Domain Layer** (Centro de la aplicación)
- **Entities**: User, Tournament, Team, Match, Score
- **Value Objects**: UserId, Email, Password, Handicap
- **Domain Services**: Password hashing, handicap calculations
- **Repository Interfaces**: Contratos para persistencia

**📋 Application Layer** (Orquestación)
- **Use Cases**: RegisterUser, CreateTournament, CalculateScore
- **DTOs**: Request/Response objects
- **Application Services**: Token management, notifications
- **Unit of Work**: Gestión de transacciones

**🌐 Infrastructure Layer** (Detalles técnicos)
- **Web Framework**: FastAPI con automatic OpenAPI
- **Database**: PostgreSQL con SQLAlchemy ORM
- **Authentication**: JWT tokens con bcrypt hashing
- **Repository Implementations**: Concrete database access

### Principios Arquitectónicos

1. **Dependency Inversion**: Dependencies point inward
2. **Single Responsibility**: Each class has one reason to change
3. **Open/Closed**: Open for extension, closed for modification
4. **Interface Segregation**: Small, specific interfaces
5. **Liskov Substitution**: Subtypes must be substitutable

---

## 🔧 Decisiones Técnicas

### Tech Stack

| Componente | Tecnología | Versión | Justificación |
|------------|------------|---------|---------------|
| **Backend** | Python | 3.12+ | Type hints avanzados, performance |
| **Web Framework** | FastAPI | 0.115+ | Async, automatic docs, validation |
| **Database** | PostgreSQL | 15+ | ACID, extensibilidad, performance |
| **ORM** | SQLAlchemy | 2.0+ | Async support, type safety |
| **Authentication** | JWT + bcrypt | - | Stateless, secure hashing |
| **Testing** | pytest + pytest-xdist + pytest-asyncio | 8.3+ | Parallel execution, async support |
| **API Docs** | OpenAPI/Swagger | Auto | Generación automática |

### Decisiones Clave

**📚 Para detalles completos, consultar los ADRs en `docs/architecture/decisions/`**

1. **ADR-001**: Clean Architecture para mantenibilidad y testabilidad
2. **ADR-002**: Value Objects para encapsulación y validación
3. **ADR-003**: Testing strategy con optimizaciones de performance
4. **ADR-004**: Tech stack moderno con FastAPI y PostgreSQL
5. **ADR-005**: Repository Pattern para abstracción de datos *(Implementado)*
6. **ADR-006**: Unit of Work para gestión transaccional *(Implementado)*
7. **ADR-007**: Domain Events para arquitectura event-driven *(Planificado)*

---

## 📦 Módulos del Sistema

### 1. User Management Module

**Responsabilidades:**
- Registro y autenticación de usuarios
- Gestión de perfiles y preferencias
- Control de acceso basado en roles

**Componentes Principales:**
```python
# Domain
User(Entity)
UserId(ValueObject)
Email(ValueObject)  
Password(ValueObject)

# Application
RegisterUserUseCase
LoginUserUseCase
UpdateProfileUseCase

# Infrastructure
UserRepository
UserRepositoryInterface
UserUnitOfWork
UserUnitOfWorkInterface
TokenService
```

### 2. Tournament Management Module *(Planeado)*

**Responsabilidades:**
- Creación y configuración de torneos
- Gestión de formatos y reglas
- Programación de partidos

### 3. Team Management Module *(Planeado)*

**Responsabilidades:**
- Formación de equipos Europa/USA
- Asignación de jugadores
- Gestión de capitanes

### 4. Handicap Management Module *(Planeado)*

**Responsabilidades:**
- Cálculo automático de handicaps
- Ajustes por condiciones del campo
- Historial de evolución

### 5. Scoring Module *(Planeado)*

**Responsabilidades:**
- Registro de scores en tiempo real
- Validación de resultados
- Cálculo de puntos por formato

---

## 📊 Modelos de Datos

### Core Entities

#### User Entity
```python
@dataclass
class User:
    id: UserId
    email: Email
    password: Password
    first_name: str
    last_name: str
    handicap: Optional[Handicap]
    created_at: datetime
    updated_at: datetime
```

#### Tournament Entity *(Diseño)*
```python
@dataclass
class Tournament:
    id: TournamentId
    name: str
    format: TournamentFormat
    start_date: date
    end_date: date
    status: TournamentStatus
    teams: List[Team]
```

### Value Objects

#### Email Value Object
```python
@dataclass(frozen=True)
class Email:
    value: str
    
    def __post_init__(self):
        if not self._is_valid_email(self.value):
            raise InvalidEmailError(f"Invalid email: {self.value}")
```

#### Password Value Object
```python
@dataclass(frozen=True)
class Password:
    hashed_value: str
    
    @classmethod
    def create(cls, plain_password: str) -> 'Password':
        # bcrypt hashing with environment-based rounds
```

---

## 🏗️ Repository Pattern

### Interfaces de Repositorio

Los repositorios definen contratos claros para la persistencia de datos siguiendo los principios de Clean Architecture:

#### UserRepositoryInterface
```python
@abstractmethod
class UserRepositoryInterface(ABC):
    async def save(self, user: User) -> None:
        """Persiste un usuario en el almacén de datos."""
        pass

    async def find_by_id(self, user_id: UserId) -> Optional[User]:
        """Busca un usuario por su ID único."""
        pass

    async def find_by_email(self, email: Email) -> Optional[User]:
        """Busca un usuario por su email."""
        pass

    async def delete(self, user: User) -> None:
        """Elimina un usuario del almacén de datos."""
        pass

    async def list_all(self) -> List[User]:
        """Retorna todos los usuarios."""
        pass

    async def exists_by_email(self, email: Email) -> bool:
        """Verifica si existe un usuario con el email dado."""
        pass

    async def count(self) -> int:
        """Cuenta el total de usuarios."""
        pass

    async def update(self, user: User) -> None:
        """Actualiza un usuario existente."""
        pass
```

### Beneficios del Patrón Repository

- **Testabilidad**: Fácil creación de mocks para pruebas unitarias
- **Desacoplamiento**: La lógica de dominio no depende de tecnologías específicas
- **Flexibilidad**: Cambios de base de datos sin afectar la lógica de negocio
- **Principio de Inversión de Dependencias**: Las capas superiores dependen de abstracciones

---

## 🔄 Unit of Work Pattern

### Gestión de Transacciones

El patrón Unit of Work coordina múltiples repositorios y garantiza la consistencia transaccional:

#### UnitOfWorkInterface (Base)
```python
@abstractmethod
class UnitOfWorkInterface(ABC):
    async def __aenter__(self) -> 'UnitOfWorkInterface':
        """Inicia el contexto de la unidad de trabajo."""
        pass

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Finaliza el contexto, haciendo rollback si hay errores."""
        pass

    @abstractmethod
    async def commit(self) -> None:
        """Confirma todos los cambios de la transacción."""
        pass

    @abstractmethod
    async def rollback(self) -> None:
        """Revierte todos los cambios de la transacción."""
        pass

    @abstractmethod
    async def flush(self) -> None:
        """Sincroniza los cambios sin confirmar la transacción."""
        pass

    @abstractmethod
    def is_active(self) -> bool:
        """Indica si la unidad de trabajo está activa."""
        pass
```

#### UserUnitOfWorkInterface
```python
@abstractmethod
class UserUnitOfWorkInterface(UnitOfWorkInterface):
    @property
    @abstractmethod
    def users(self) -> UserRepositoryInterface:
        """Acceso al repositorio de usuarios."""
        pass
```

### Uso del Unit of Work

```python
# Caso de uso con transacciones
async def register_user_use_case(
    email: str, 
    password: str,
    uow: UserUnitOfWorkInterface
) -> User:
    async with uow:
        # Validar que el email no existe
        if await uow.users.exists_by_email(Email(email)):
            raise UserAlreadyExistsError()
        
        # Crear y guardar usuario
        user = User.create(email, password)
        await uow.users.save(user)
        
        # Commit automático al salir del contexto
        await uow.commit()
        return user
```

### Beneficios del Unit of Work

- **Atomicidad**: Garantiza que todas las operaciones se completen o fallen juntas
- **Consistencia**: Mantiene la integridad de los datos a través de múltiples repositorios
- **Gestión Automática**: Context manager que maneja commit/rollback automáticamente
- **Claridad**: Delimita claramente los límites transaccionales

---

## 🔄 Domain Events Pattern

### Comunicación Event-Driven

Los eventos de dominio permiten desacoplar efectos secundarios de la lógica principal de negocio, especialmente útil en un sistema de torneos donde múltiples acciones ocurren en respuesta a eventos específicos.

#### DomainEvent Base Class
```python
@dataclass(frozen=True)
class DomainEvent(ABC):
    """Evento de dominio base."""
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    occurred_on: datetime = field(default_factory=datetime.now)
    aggregate_id: str
    event_version: int = 1

@dataclass(frozen=True)
class UserRegisteredEvent(DomainEvent):
    """Usuario registrado exitosamente."""
    user_id: str
    email: str
    full_name: str
    registration_source: str = "web"
```

#### Event Collection en Entidades
```python
class User:
    def __init__(self, ...):
        self._domain_events: List[DomainEvent] = []
    
    @classmethod
    def create(cls, ...) -> 'User':
        user = cls(...)
        user.add_domain_event(UserRegisteredEvent(
            aggregate_id=str(user.id),
            user_id=str(user.id),
            email=str(user.email),
            full_name=user.get_full_name()
        ))
        return user
    
    def add_domain_event(self, event: DomainEvent) -> None:
        """Añade evento para publicar después del commit."""
        self._domain_events.append(event)
```

#### Event Bus & Handlers
```python
class EventBus(ABC):
    @abstractmethod
    async def publish(self, event: DomainEvent) -> None:
        """Publica evento a todos sus handlers."""
        pass

class EventHandler(ABC):
    @abstractmethod
    async def handle(self, event: DomainEvent) -> None:
        """Maneja un evento específico."""
        pass

# Handler específico
class WelcomeEmailEventHandler(EventHandler):
    async def handle(self, event: UserRegisteredEvent) -> None:
        await self._email_service.send_welcome_email(
            email=event.email,
            full_name=event.full_name
        )
```

### Casos de Uso de Eventos en Ryder Cup

#### User Management Events
- **UserRegisteredEvent**: Email bienvenida, auditoría, métricas
- **UserLoggedInEvent**: Actualizar última conexión, detectar actividad sospechosa

#### Tournament Management Events  
- **TournamentCreatedEvent**: Enviar invitaciones, notificar administradores
- **PlayerJoinedTournamentEvent**: Actualizar equipos, recalcular handicaps
- **MatchStartedEvent**: Notificar jugadores, activar sistema de scoring

#### Scoring Events
- **MatchCompletedEvent**: Actualizar leaderboard, notificar resultados
- **TournamentFinishedEvent**: Generar reportes, actualizar estadísticas

### Integration con Unit of Work

```python
class RegisterUserUseCase:
    async def execute(self, command: RegisterUserCommand) -> UserResponse:
        async with self._uow:
            # Lógica de negocio limpia - sin efectos secundarios
            user = User.create(...)  # Genera eventos automáticamente
            await self._uow.users.save(user)
            await self._uow.commit()
            
            # Publicar eventos después del commit exitoso
            await self._uow.publish_events(self._event_bus)
        
        return UserResponse(...)
```

### Beneficios de Domain Events

- **Single Responsibility**: Use cases enfocados solo en lógica de negocio principal
- **Desacoplamiento**: Efectos secundarios manejados por handlers independientes
- **Extensibilidad**: Nueva funcionalidad = nuevo handler, sin modificar código existente
- **Testabilidad**: Tests aislados para use cases y handlers por separado
- **Auditoría**: Trazabilidad completa de eventos de negocio importantes
- **Performance**: Procesamiento asíncrono de efectos secundarios

---

## 🔌 API Design

### RESTful Endpoints

#### Authentication
```
POST   /api/v1/auth/register     # User registration
POST   /api/v1/auth/login        # User login
POST   /api/v1/auth/logout       # User logout
POST   /api/v1/auth/refresh      # Token refresh
```

#### Users
```
GET    /api/v1/users/profile     # Get current user profile
PUT    /api/v1/users/profile     # Update user profile
GET    /api/v1/users/{user_id}   # Get user by ID
```

#### Tournaments *(Planeado)*
```
GET    /api/v1/tournaments       # List tournaments
POST   /api/v1/tournaments       # Create tournament
GET    /api/v1/tournaments/{id}  # Get tournament details
PUT    /api/v1/tournaments/{id}  # Update tournament
DELETE /api/v1/tournaments/{id}  # Delete tournament
```

### API Response Format

```json
{
  "success": true,
  "data": {
    "id": "user_123",
    "email": "player@example.com",
    "first_name": "John",
    "last_name": "Doe"
  },
  "message": "Operation completed successfully",
  "timestamp": "2025-10-31T10:30:00Z"
}
```

### Error Response Format

```json
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid email format",
    "details": {
      "field": "email",
      "value": "invalid-email"
    }
  },
  "timestamp": "2025-10-31T10:30:00Z"
}
```

---

## 🔐 Seguridad

### Autenticación y Autorización

1. **JWT Tokens**: Stateless authentication
2. **bcrypt Hashing**: Secure password storage (12 rounds production)
3. **Role-Based Access**: Admin, Captain, Player roles
4. **Rate Limiting**: Protection against brute force
5. **HTTPS Only**: Encrypted communication

### Data Protection

- **Input Validation**: All inputs validated at domain level
- **SQL Injection Protection**: Parameterized queries via ORM
- **XSS Protection**: Output encoding and CSP headers
- **CORS Configuration**: Restricted cross-origin requests

### Security Headers

```python
# FastAPI middleware configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://ryderclub.com"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)
```

---

## 🧪 Testing Strategy

### Test Pyramid

```
     ┌─────────────────┐
     │   🌐 E2E Tests   │  (Pocos, lentos, alta confianza)
     │      (5%)        │
  ┌──┴─────────────────┴──┐
  │  🔄 Integration Tests │  (Algunos, medios, confianza media)
  │       (15%)           │
┌─┴───────────────────────┴─┐
│     🔧 Unit Tests         │  (Muchos, rápidos, baja confianza)
│        (80%)              │
└───────────────────────────┘
```

### Configuración Actual

- **Framework**: pytest 8.3.0 con pytest-xdist 3.8.0
- **Paralelización**: 7 workers (cores disponibles - 1)
- **Performance**: 80 tests ejecutados en 0.54 segundos
- **Cobertura**: Objetivo del 90% en código de dominio

### Optimizaciones Implementadas

1. **bcrypt Rounds**: 4 rounds en testing vs 12 en producción
2. **Parallel Execution**: pytest-xdist con multiprocessing
3. **Test Categorization**: Organizados por capa y objeto
4. **Fast Feedback**: Script dev_tests.py con categorización visual

### Test Organization

```python
# Categorización automática por capas
tests/
├── domain/           # Tests de lógica de negocio
├── application/      # Tests de casos de uso
├── infrastructure/   # Tests de persistencia
└── integration/      # Tests de integración
```

---

## 🚀 Deployment

### Environments

| Environment | Purpose | URL | Database |
|-------------|---------|-----|----------|
| **Development** | Local development | localhost:8000 | SQLite |
| **Testing** | CI/CD pipeline | - | PostgreSQL (Docker) |
| **Staging** | Pre-production | staging.ryderclub.com | PostgreSQL |
| **Production** | Live system | app.ryderclub.com | PostgreSQL (HA) |

### Container Configuration

```dockerfile
# Multi-stage build for optimization
FROM python:3.12-slim as builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

FROM python:3.12-slim
WORKDIR /app
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY src/ ./src/
EXPOSE 8000
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Health Checks

```python
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow(),
        "version": "1.0.0",
        "database": await check_database_connection()
    }
```

---

## 🗺️ Roadmap

### Fase 1: Foundation ✅ (Completada)
- ✅ Clean Architecture setup
- ✅ User management básico
- ✅ Authentication con JWT
- ✅ Value Objects implementation
- ✅ Testing framework optimizado
- ✅ Comprehensive documentation

### Fase 2: Core Features 🚧 (En progreso)
- 🔄 Repository interfaces
- 🔄 Unit of Work pattern
- ⏳ Tournament creation
- ⏳ Team management
- ⏳ Basic scoring

### Fase 3: Advanced Features ⏳ (Planeado)
- ⏳ Handicap calculation system
- ⏳ Real-time scoring updates
- ⏳ Match format configurations
- ⏳ Tournament brackets
- ⏳ Statistics dashboard

### Fase 4: Enhancement ⏳ (Planeado)
- ⏳ Mobile app companion
- ⏳ Advanced analytics
- ⏳ Tournament history
- ⏳ Social features
- ⏳ Integration with golf associations

### Fase 5: Production ⏳ (Futuro)
- ⏳ Load balancing setup
- ⏳ Monitoring and alerting
- ⏳ Backup and disaster recovery
- ⏳ Performance optimization
- ⏳ Multi-language support

---

## 📚 Referencias

### Documentation
- **Architecture Decisions**: [`docs/architecture/decisions/`](./architecture/decisions/)
- **Module Documentation**: [`docs/modules/`](./modules/)
- **Project Structure**: [`docs/project-structure.md`](./project-structure.md)

### External Resources
- [Clean Architecture - Robert C. Martin](https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Domain-Driven Design](https://martinfowler.com/tags/domain%20driven%20design.html)
- [Test Pyramid](https://martinfowler.com/articles/practical-test-pyramid.html)

### Code Quality
- **Style Guide**: PEP 8 + Black formatter
- **Type Checking**: mypy strict mode
- **Documentation**: Google docstring style
- **Testing**: pytest best practices

---

## 📞 Contacto y Soporte

**Equipo de Desarrollo**
- **Lead Developer**: [Agustín Estévez](mailto:agustin@ryderclub.com)
- **Architecture Review**: Internal team
- **Documentation**: Living document, updated continuously

**Repository**
- **GitHub**: [agustinEDev/RyderCupAM](https://github.com/agustinEDev/RyderCupAM)
- **Branch**: `develop` (active development)
- **Issues**: GitHub Issues para bugs y features

---

*Documento actualizado: 31 de octubre de 2025*  
*Próxima revisión: Con cada milestone completado*