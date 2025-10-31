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
│   │   │   │   └── __init__.py
│   │   │   │
│   │   │   ├── infrastructure/         # Capa de infraestructura
│   │   │   │   ├── persistence/
│   │   │   │   │   ├── __init__.py
│   │   │   │   │   ├── user_repository_impl.py
│   │   │   │   │   └── user_model.py
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
│   │   │   └── result.py
│   │   │
│   │   ├── infrastructure/
│   │   │   ├── database/
│   │   │   │   ├── __init__.py
│   │   │   │   └── database.py
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
│   │           └── test_login_use_case.py
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

### Infrastructure Layer
- **Persistence**: Implementación de repositorios con SQLAlchemy
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
│        Application             │  ← Usa Domain
└────────────────┬───────────────┘
                 ↓
┌────────────────────────────────┐
│          Domain                │  ← No depende de nada
└────────────────────────────────┘
```

**Reglas:**
1. Domain no depende de ninguna capa (solo stdlib de Python)
2. Application solo depende de Domain
3. Infrastructure y Presentation pueden usar Application y Domain
4. Las dependencias siempre apuntan hacia el dominio

## 🔄 Flujo de una Petición

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
Repository Protocol (Domain) ← Entity (Domain)
    ↓
Repository Implementation (Infrastructure)
    ↓
SQLAlchemy ORM
    ↓
Database
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
from src.shared.application.use_case import UseCase  # Shared
```

**Orden de imports:**
1. Standard library
2. Third-party packages
3. Domain layer
4. Application layer
5. Infrastructure layer
6. Shared

## 🗃️ Base de Datos

### SQLAlchemy Models vs Domain Entities
- **Models** (Infrastructure): Clases SQLAlchemy para ORM
- **Entities** (Domain): POPOs (Plain Old Python Objects)
- **Mapper**: Convierte entre Model ↔ Entity

### Migraciones con Alembic
```bash
# Crear migración
alembic revision --autogenerate -m "create users table"

# Aplicar migraciones
alembic upgrade head

# Rollback
alembic downgrade -1
```