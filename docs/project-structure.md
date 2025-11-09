# 📂 Estructura del Proyecto

## Convenciones

- **Módulos**: snake_case (`user_management/`)
- **Clases**: PascalCase (`UserRepository`)
- **Funciones/Variables**: snake_case (`get_user_by_id`)
- **Constantes**: UPPER_SNAKE_CASE (`MAX_LOGIN_ATTEMPTS`)
- **Tests**: `test_<nombre>.py`

## Árbol de Directorios

```
src/
├── config/              # Configuración global
│   ├── database.py     # DB setup
│   ├── dependencies.py # Composition Root (DI)
│   └── settings.py     # Environment vars
│
├── modules/            # Módulos de negocio
│   └── user/
│       ├── domain/
│       │   ├── entities/        # User
│       │   ├── value_objects/   # UserId, Email, Password, Handicap
│       │   ├── events/          # UserRegistered, HandicapUpdated
│       │   ├── repositories/    # Interfaces
│       │   ├── services/        # Domain services (interfaces)
│       │   └── errors/          # Domain exceptions
│       │
│       ├── application/
│       │   ├── use_cases/       # RegisterUser, UpdateHandicap
│       │   ├── dto/             # Request/Response DTOs
│       │   └── handlers/        # Event handlers
│       │
│       └── infrastructure/
│           ├── api/v1/          # FastAPI routes
│           ├── persistence/     # SQLAlchemy repos
│           └── external/        # RFEG service, mocks
│
└── shared/
    ├── domain/         # Base classes (DomainEvent, Entity)
    └── infrastructure/ # Shared utilities

tests/
├── unit/               # Tests aislados (90%)
│   └── modules/user/
│       ├── domain/
│       ├── application/
│       └── infrastructure/
│
└── integration/        # Tests con BD/API (10%)
    └── api/v1/
```

## Separación de Responsabilidades

### Domain Layer
- ❌ NO depende de nada externo
- ✅ SÍ contiene lógica de negocio pura
- Tests: Unitarios, sin mocks de BD

### Application Layer
- ❌ NO contiene lógica de negocio
- ✅ SÍ orquesta domain + infra
- Tests: Unitarios con mocks

### Infrastructure Layer
- ❌ NO contiene lógica de negocio
- ✅ SÍ implementa interfaces del domain
- Tests: Integración con BD real

## Archivos de Configuración

- `alembic.ini`: Config de migraciones
- `pytest.ini`: Config de tests (`asyncio_mode = auto`)
- `docker-compose.yml`: Servicios (app + postgres)
- `.env`: Variables de entorno (no commitear)
- `requirements.txt`: Dependencias Python
- `main.py`: Entry point de la aplicación
