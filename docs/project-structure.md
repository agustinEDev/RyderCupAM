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
│       │   ├── entities/        # User (with login/logout methods)
│       │   ├── value_objects/   # UserId, Email, Password, Handicap
│       │   ├── events/          # UserRegistered, HandicapUpdated, 
│       │   │                    # UserLoggedIn, UserLoggedOut
│       │   ├── repositories/    # Interfaces (UserRepository, UnitOfWork)
│       │   ├── services/        # Domain services (interfaces)
│       │   └── errors/          # Domain exceptions
│       │
│       ├── application/
│       │   ├── use_cases/       # RegisterUser, LoginUser, LogoutUser,
│       │   │                    # UpdateHandicap, FindUser
│       │   ├── dto/             # Request/Response DTOs (Login, Logout)
│       │   └── handlers/        # Event handlers
│       │
│       └── infrastructure/
│           ├── api/v1/          # FastAPI routes (auth_routes, handicap_routes)
│           ├── persistence/     # SQLAlchemy repos + UnitOfWork impl
│           └── external/        # RFEG service, mocks
│
└── shared/
    ├── domain/         # Base classes (DomainEvent, Entity)
    └── infrastructure/ # Shared utilities (JWT handler, EventBus)

tests/
├── unit/               # Tests aislados
│   └── modules/user/
│       ├── domain/     # Entities, VOs, Events
│       ├── application/# Use Cases, DTOs  
│       └── infrastructure/ # Repos, External services
│
└── integration/        # Tests con BD/API
    ├── api/v1/         # Auth routes, handicap routes
    ├── domain_events/  # Event integration
    └── modules/user/   # Application integration
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
