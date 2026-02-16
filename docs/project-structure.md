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
│   ├── user/
│       ├── domain/
│       │   ├── entities/        # User, UserOAuthAccount (Sprint 3)
│       │   ├── value_objects/   # UserId, Email, Password, Handicap,
│       │   │                    # OAuthAccountId, OAuthProvider (Sprint 3)
│       │   ├── events/          # UserRegistered, HandicapUpdated,
│       │   │                    # UserLoggedIn, UserLoggedOut,
│       │   │                    # UserProfileUpdated, UserEmailChanged, UserPasswordChanged,
│       │   │                    # EmailVerifiedEvent,
│       │   │                    # GoogleAccountLinkedEvent, GoogleAccountUnlinkedEvent (Sprint 3)
│       │   ├── repositories/    # Interfaces (UserRepository, UnitOfWork,
│       │   │                    # UserOAuthAccountRepository) (Sprint 3)
│       │   ├── services/        # Domain services (interfaces)
│       │   └── errors/          # Domain exceptions
│       │
│       ├── application/
│       │   ├── use_cases/       # RegisterUser, LoginUser, LogoutUser,
│       │   │                    # UpdateProfile, UpdateSecurity,
│       │   │                    # UpdateHandicap, FindUser, VerifyEmail,
│       │   │                    # GoogleLogin, LinkGoogleAccount, UnlinkGoogleAccount (Sprint 3)
│       │   ├── dto/             # Request/Response DTOs (Login, Logout,
│       │   │                    # UpdateProfile, UpdateSecurity, VerifyEmail,
│       │   │                    # OAuth DTOs) (Sprint 3)
│       │   ├── ports/           # IGoogleOAuthService (Sprint 3)
│       │   └── handlers/        # Event handlers
│       │
│       └── infrastructure/
│           ├── api/v1/          # FastAPI routes (auth_routes, user_routes,
│           │                    # handicap_routes, google_auth_routes) (Sprint 3)
│           ├── persistence/     # SQLAlchemy repos + UnitOfWork impl
│           │                    # + UserOAuthAccountRepository (Sprint 3)
│           └── external/        # RFEG service, GoogleOAuthService (Sprint 3)
│   ├── competition/            # Competition module (same structure)
│   ├── golf_course/            # Golf Course module (same structure)
│   └── support/                # Support module ⭐ v2.0.8
│       ├── domain/
│       │   └── value_objects/  # ContactCategory
│       ├── application/
│       │   ├── dto/            # ContactRequestDTO, ContactResponseDTO
│       │   ├── ports/          # IGitHubIssueService
│       │   └── use_cases/      # SubmitContactUseCase
│       └── infrastructure/
│           ├── api/v1/         # support_routes.py
│           └── services/       # GitHubIssueService
│
└── shared/
    ├── domain/         # Base classes (DomainEvent, Entity)
    └── infrastructure/ # Shared utilities (JWT handler, EventBus, EmailService)

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
