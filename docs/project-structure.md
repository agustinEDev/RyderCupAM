# Estructura del Proyecto

## 📁 Organización de Carpetas

```
ryder-cup-manager/
│
├── src/
│   ├── modules/                        # Módulos del sistema
│   │   ├── user/                       # Módulo de usuarios
│   │   │   ├── domain/                 # Capa de dominio
│   │   │   │   ├── entities/
│   │   │   │   │   ├── __init__.py
│   │   │   │   │   └── user.py
│   │   │   │   ├── value_objects/
│   │   │   │   │   ├── __init__.py
│   │   │   │   │   ├── email.py
│   │   │   │   │   ├── password.py
│   │   │   │   │   └── user_id.py
│   │   │   │   ├── repositories/       # Interfaces de repositorios
│   │   │   │   │   ├── __init__.py
│   │   │   │   │   └── user_repository.py
│   │   │   │   ├── services/           # Servicios de dominio
│   │   │   │   │   ├── __init__.py
│   │   │   │   │   └── password_hasher.py
│   │   │   │   ├── errors/
│   │   │   │   │   ├── __init__.py
│   │   │   │   │   └── user_errors.py
│   │   │   │   └── __init__.py
│   │   │   │
│   │   │   ├── application/            # Capa de aplicación
│   │   │   │   ├── use_cases/
│   │   │   │   │   ├── __init__.py
│   │   │   │   │   ├── register_user/
│   │   │   │   │   │   ├── __init__.py
│   │   │   │   │   │   ├── register_user_use_case.py
│   │   │   │   │   │   └── register_user_dto.py
│   │   │   │   │   └── login_user/
│   │   │   │   │       ├── __init__.py
│   │   │   │   │       ├── login_user_use_case.py
│   │   │   │   │       └── login_user_dto.py
│   │   │   │   ├── services/           # Servicios de aplicación
│   │   │   │   │   ├── __init__.py
│   │   │   │   │   └── token_service.py
│   │   │   │   ├── ports/              # Interfaces (Unit of Work)
│   │   │   │   │   ├── __init__.py
│   │   │   │   │   └── user_unit_of_work.py
│   │   │   │   └── __init__.py
│   │   │   │
│   │   │   ├── infrastructure/         # Capa de infraestructura
│   │   │   │   ├── persistence/
│   │   │   │   │   ├── __init__.py
│   │   │   │   │   ├── user_repository_impl.py
│   │   │   │   │   ├── user_model.py
│   │   │   │   │   └── user_unit_of_work_impl.py  # Implementación UoW
│   │   │   │   ├── security/
│   │   │   │   │   ├── __init__.py
│   │   │   │   │   ├── bcrypt_password_hasher.py
│   │   │   │   │   └── jwt_token_service.py
│   │   │   │   ├── http/
│   │   │   │   │   ├── __init__.py
│   │   │   │   │   └── user_controller.py
│   │   │   │   └── __init__.py
│   │   │   │
│   │   │   ├── presentation/           # Capa de presentación
│   │   │   │   ├── schemas/
│   │   │   │   │   ├── __init__.py
│   │   │   │   │   ├── register_request.py
│   │   │   │   │   ├── login_request.py
│   │   │   │   │   └── user_response.py
│   │   │   │   ├── mappers/
│   │   │   │   │   ├── __init__.py
│   │   │   │   │   └── user_mapper.py
│   │   │   │   └── __init__.py
│   │   │   │
│   │   │   └── __init__.py
│   │   │
│   │   ├── competition/                # Módulo de competiciones (futuro)
│   │   ├── team/                       # Módulo de equipos (futuro)
│   │   ├── match/                      # Módulo de partidos (futuro)
│   │   ├── scoring/                    # Módulo de puntuación (futuro)
│   │   └── __init__.py
│   │
│   ├── shared/                         # Código compartido
│   │   ├── domain/
│   │   │   ├── value_objects/
│   │   │   │   ├── __init__.py
│   │   │   │   └── base_id.py
│   │   │   ├── entities/
│   │   │   │   ├── __init__.py
│   │   │   │   └── base_entity.py
│   │   │   ├── errors/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── domain_error.py
│   │   │   │   └── not_found_error.py
│   │   │   └── __init__.py
│   │   │
│   │   ├── application/
│   │   │   ├── __init__.py
│   │   │   ├── use_case.py
│   │   │   ├── result.py
│   │   │   └── unit_of_work.py         # Interfaz base UoW
│   │   │
│   │   ├── infrastructure/
│   │   │   ├── database/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── database.py
│   │   │   │   └── sqlalchemy_unit_of_work.py  # UoW base SQLAlchemy
│   │   │   ├── http/
│   │   │   │   ├── __init__.py
│   │   │   │   └── exception_handlers.py
│   │   │   └── __init__.py
│   │   │
│   │   └── __init__.py
│   │
│   ├── config/                         # Configuración
│   │   ├── __init__.py
│   │   ├── database.py
│   │   ├── auth.py
│   │   └── settings.py
│   │
│   └── main.py                         # Punto de entrada
│
├── tests/                              # Tests
│   ├── unit/
│   │   ├── __init__.py
│   │   └── modules/
│   │       └── user/
│   │           ├── __init__.py
│   │           ├── test_user_entity.py
│   │           ├── test_email_vo.py
│   │           └── test_password_vo.py
│   ├── integration/
│   │   ├── __init__.py
│   │   └── modules/
│   │       └── user/
│   │           ├── __init__.py
│   │           ├── test_register_use_case.py
│   │           ├── test_login_use_case.py
│   │           └── test_user_unit_of_work.py
│   └── e2e/
│       ├── __init__.py
│       └── test_user_endpoints.py
│
├── alembic/                            # Migraciones de BD
│   ├── versions/
│   └── env.py
│
├── docs/                               # Documentación
│   ├── architecture/
│   │   ├── decisions/                  # ADRs
│   │   └── diagrams/
│   ├── patterns/
│   │   └── unit-of-work.md            # Documentación del patrón
│   └── modules/
│       └── user-management.md
│
├── scripts/                            # Scripts útiles
│   └── setup_database.sh
│
├── .env.example
├── .gitignore
├── requirements.txt
├── requirements-dev.txt
├── pyproject.toml
├── alembic.ini
└── README.md
```

## 🎯 Explicación de las Capas

### Domain Layer (Núcleo)
- **Entities**: Clases de negocio con identidad única
- **Value Objects**: Clases inmutables usando `@dataclass(frozen=True)`
- **Repository Interfaces**: Protocolos (ABC) para persistencia
- **Domain Services**: Lógica de negocio que no pertenece a una entidad
- **Domain Errors**: Excepciones personalizadas del dominio

### Application Layer
- **Use Cases**: Orquestación de casos de uso usando patrón Command
- **DTOs**: Dataclasses para transferencia entre capas
- **Application Services**: Servicios auxiliares (tokens, emails, etc.)
- **Ports (Unit of Work)**: Interfaces para gestión de transacciones

### Infrastructure Layer
- **Persistence**: Implementación de repositorios con SQLAlchemy
- **Unit of Work Implementation**: Implementación concreta del UoW con SQLAlchemy
- **External Services**: APIs externas, librerías de terceros
- **Security**: Implementación de seguridad (bcrypt, JWT)
- **HTTP**: Controllers usando FastAPI routers

### Presentation Layer
- **Schemas**: Pydantic models para validación de API
- **Mappers**: Conversión entre schemas y entidades
- **Validators**: Validación de entrada con Pydantic

## 📋 Reglas de Dependencia

```
┌──────────────────────────────────┐
│   Infrastructure & Presentation  │  ← Puede usar todo
└────────────────┬─────────────────┘
                 ↓
┌────────────────────────────────┐
│        Application             │  ← Usa Domain + UoW Interface
└────────────────┬───────────────┘
                 ↓
┌────────────────────────────────┐
│          Domain                │  ← No depende de nada
└────────────────────────────────┘
```

**Reglas:**
1. Domain no depende de ninguna capa (solo stdlib de Python)
2. Application solo depende de Domain e interfaces (ports)
3. Infrastructure implementa las interfaces definidas en Application
4. Infrastructure y Presentation pueden usar Application y Domain
5. Las dependencias siempre apuntan hacia el dominio

## 🔄 Flujo de una Petición con Unit of Work

```
HTTP Request (FastAPI)
    ↓
Router → Controller (Infrastructure)
    ↓
Pydantic Schema Validation (Presentation)
    ↓
Mapper (Presentation) → DTO
    ↓
Use Case (Application)
    ↓
┌─────────────────────────────────────┐
│      Unit of Work (UoW)             │
│  ┌───────────────────────────────┐  │
│  │ async with uow:               │  │
│  │   await uow.users.save(user)  │  │
│  │   await uow.commit()          │  │
│  └───────────────────────────────┘  │
│         ↓                            │
│  Repository Implementation          │
│         ↓                            │
│  SQLAlchemy Session                 │
└─────────────────────────────────────┘
    ↓
Database
```

## 🏗️ Patrón Unit of Work

### Interfaz Base (Shared)

**Ubicación**: `src/shared/application/unit_of_work.py`

```python
from abc import ABC, abstractmethod
from typing import Protocol

class UnitOfWork(ABC):
    """Interfaz base para Unit of Work."""
    
    @abstractmethod
    async def __aenter__(self):
        """Inicia una transacción."""
        pass
    
    @abstractmethod
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Finaliza una transacción (commit o rollback)."""
        pass
    
    @abstractmethod
    async def commit(self) -> None:
        """Confirma los cambios."""
        pass
    
    @abstractmethod
    async def rollback(self) -> None:
        """Revierte los cambios."""
        pass
```

### Implementación SQLAlchemy (Shared)

**Ubicación**: `src/shared/infrastructure/database/sqlalchemy_unit_of_work.py`

```python
from sqlalchemy.ext.asyncio import AsyncSession

class SQLAlchemyUnitOfWork(UnitOfWork):
    """Implementación base de UoW con SQLAlchemy."""
    
    def __init__(self, session_factory):
        self._session_factory = session_factory
        self._session: AsyncSession | None = None
    
    async def __aenter__(self):
        self._session = self._session_factory()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            await self.rollback()
        await self._session.close()
    
    async def commit(self) -> None:
        await self._session.commit()
    
    async def rollback(self) -> None:
        await self._session.rollback()
```

### Interfaz Específica del Módulo (Application)

**Ubicación**: `src/modules/user/application/ports/user_unit_of_work.py`

```python
from abc import abstractmethod
from src.shared.application.unit_of_work import UnitOfWork
from src.modules.user.domain.repositories.user_repository import UserRepository

class UserUnitOfWork(UnitOfWork):
    """Unit of Work para el módulo User."""
    
    @property
    @abstractmethod
    def users(self) -> UserRepository:
        """Repositorio de usuarios."""
        pass
```

### Implementación Concreta (Infrastructure)

**Ubicación**: `src/modules/user/infrastructure/persistence/user_unit_of_work_impl.py`

```python
from src.shared.infrastructure.database.sqlalchemy_unit_of_work import SQLAlchemyUnitOfWork
from src.modules.user.application.ports.user_unit_of_work import UserUnitOfWork
from src.modules.user.infrastructure.persistence.user_repository_impl import UserRepositoryImpl

class UserUnitOfWorkImpl(SQLAlchemyUnitOfWork, UserUnitOfWork):
    """Implementación del UoW para el módulo User."""
    
    @property
    def users(self) -> UserRepository:
        if not hasattr(self, '_users_repo'):
            self._users_repo = UserRepositoryImpl(self._session)
        return self._users_repo
```

### Uso en Cases de Uso

**Ubicación**: `src/modules/user/application/use_cases/register_user/register_user_use_case.py`

```python
class RegisterUserUseCase:
    def __init__(
        self,
        uow: UserUnitOfWork,
        password_hasher: PasswordHasher
    ):
        self._uow = uow
        self._password_hasher = password_hasher
    
    async def execute(self, command: RegisterUserCommand) -> UserResponse:
        async with self._uow:
            # Verificar que el email no existe
            if await self._uow.users.exists_by_email(Email.create(command.email)):
                raise EmailAlreadyExistsError(command.email)
            
            # Crear usuario
            user = await User.create(
                email=Email.create(command.email),
                plain_password=command.password,
                first_name=command.first_name,
                last_name=command.last_name,
                hasher=self._password_hasher
            )
            
            # Guardar usuario
            await self._uow.users.save(user)
            
            # Commit de la transacción
            await self._uow.commit()
        
        return UserResponse(...)
```

## 📝 Convenciones de Nombres

### Python Style Guide (PEP 8)
- **Modules/Packages**: `snake_case` (ej: `user_repository.py`)
- **Classes**: `PascalCase` (ej: `UserRepository`, `RegisterUserUseCase`)
- **Functions/Methods**: `snake_case` (ej: `find_by_email()`)
- **Constants**: `UPPER_SNAKE_CASE` (ej: `MAX_LOGIN_ATTEMPTS`)
- **Private**: Prefijo `_` (ej: `_validate_password()`)

### Sufijos Específicos
- **Entities**: `.py` (ej: `user.py` → clase `User`)
- **Value Objects**: `.py` (ej: `email.py` → clase `Email`)
- **Use Cases**: `_use_case.py` (ej: `register_user_use_case.py`)
- **Repositories**: `_repository.py` (interfaz) / `_repository_impl.py` (implementación)
- **Unit of Work**: `_unit_of_work.py` (interfaz) / `_unit_of_work_impl.py` (implementación)
- **DTOs**: `_dto.py` (ej: `register_user_dto.py`)
- **Tests**: `test_*.py` (ej: `test_user_entity.py`)
- **Schemas**: `_request.py` / `_response.py` (ej: `register_request.py`)

## 🛠️ Dependencias Principales

### requirements.txt
```
fastapi==0.115.0
uvicorn[standard]==0.30.0
sqlalchemy==2.0.35
alembic==1.13.3
pydantic==2.9.0
pydantic-settings==2.5.0
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
python-multipart==0.0.9
psycopg2-binary==2.9.9
```

### requirements-dev.txt
```
pytest==8.3.0
pytest-asyncio==0.24.0
pytest-cov==5.0.0
httpx==0.27.0
faker==30.0.0
black==24.8.0
ruff==0.6.0
mypy==1.11.0
```

## 🏗️ Configuración del Proyecto

### pyproject.toml
```toml
[tool.black]
line-length = 100
target-version = ['py311']

[tool.ruff]
line-length = 100
select = ["E", "F", "I"]

[tool.mypy]
python_version = "3.11"
strict = true
ignore_missing_imports = true

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = "test_*.py"
python_classes = "Test*"
python_functions = "test_*"
```

## 📦 Estructura de Imports

```python
# Ejemplo en un use case
from typing import Protocol  # Standard library
from dataclasses import dataclass  # Standard library

from src.modules.user.domain.entities.user import User  # Domain
from src.modules.user.domain.repositories.user_repository import UserRepository  # Domain
from src.modules.user.domain.errors.user_errors import EmailAlreadyExistsError  # Domain
from src.modules.user.application.ports.user_unit_of_work import UserUnitOfWork  # Application
from src.shared.application.use_case import UseCase  # Shared
```

**Orden de imports:**
1. Standard library
2. Third-party packages
3. Domain layer
4. Application layer (incluyendo ports)
5. Infrastructure layer
6. Shared

## 🗃️ Base de Datos

### SQLAlchemy Models vs Domain Entities
- **Models** (Infrastructure): Clases SQLAlchemy para ORM
- **Entities** (Domain): POPOs (Plain Old Python Objects)
- **Mapper**: Convierte entre Model ↔ Entity
- **Unit of Work**: Gestiona la sesión y transacciones de SQLAlchemy

### Migraciones con Alembic
```bash
# Crear migración
alembic revision --autogenerate -m "create users table"

# Aplicar migraciones
alembic upgrade head

# Rollback
alembic downgrade -1
```

## 🧪 Testing del Unit of Work

### Test de Integración

```python
import pytest
from src.modules.user.application.ports.user_unit_of_work import UserUnitOfWork

@pytest.mark.asyncio
async def test_unit_of_work_commits_changes(uow: UserUnitOfWork):
    """Verifica que el UoW hace commit de los cambios."""
    async with uow:
        user = await User.create(...)
        await uow.users.save(user)
        await uow.commit()
    
    # Verificar que el usuario fue guardado
    async with uow:
        saved_user = await uow.users.find_by_email(user.email)
        assert saved_user is not None

@pytest.mark.asyncio
async def test_unit_of_work_rollbacks_on_error(uow: UserUnitOfWork):
    """Verifica que el UoW hace rollback en caso de error."""
    try:
        async with uow:
            user = await User.create(...)
            await uow.users.save(user)
            raise Exception("Simulated error")
    except Exception:
        pass
    
    # Verificar que el usuario NO fue guardado
    async with uow:
        saved_user = await uow.users.find_by_email(user.email)
        assert saved_user is None
```

## 🎯 Ventajas del Unit of Work

### ✅ Transaccionalidad
- **Atomicidad**: Todas las operaciones se confirman o revierten juntas
- **Consistencia**: Los datos mantienen su integridad
- **Control**: Punto único para gestionar transacciones

### ✅ Testabilidad
- **Mock fácil**: Se puede mockear toda la UoW
- **Tests aislados**: No se necesita BD real para tests unitarios
- **Fixtures**: Fácil crear fixtures para tests

### ✅ Desacoplamiento
- **Independencia**: Casos de uso no dependen de SQLAlchemy
- **Flexibilidad**: Fácil cambiar de ORM o BD
- **Clean Architecture**: Respeta las reglas de dependencia

### ✅ Mantenibilidad
- **Punto único**: Un lugar para lógica de transacciones
- **Reutilización**: Base UoW compartida entre módulos
- **Extensibilidad**: Fácil añadir nuevos repositorios