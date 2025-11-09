# 📂 Estructura del Proyecto

Este documento describe la organización de carpetas y ficheros del proyecto Ryder Cup Manager API. La estructura sigue los principios de **Clean Architecture** y **Monolito Modular**, separando el código por responsabilidades (capas) y por funcionalidades de negocio (módulos).

## 🌳 Estructura de Directorios Detallada

El siguiente árbol representa la estructura completa y actual del proyecto.

```
.
├── alembic/
├── docs/
│   └── architecture/
│       └── decisions/ # - ADRs: ADR-001 a ADR-012
├── src/
│   ├── config/
│   │   ├── database.py
│   │   ├── dependencies.py # - Composition Root
│   │   └── mappers.py
│   ├── modules/
│   │   └── user/
│   │       ├── application/
│   │       │   ├── dto/
│   │       │   ├── handlers/
│   │       │   └── use_cases/
│   │       ├── domain/
│   │       │   ├── entities/        # User entity
│   │       │   ├── events/          # UserRegisteredEvent, HandicapUpdatedEvent
│   │       │   ├── errors/          # User y Handicap errors
│   │       │   ├── repositories/    # Interfaces de Repositorios
│   │       │   ├── services/        # PasswordHasher, HandicapService (interfaces)
│   │       │   └── value_objects/   # UserId, Email, Password, Handicap
│   │       └── infrastructure/
│   │           ├── api/
│   │           │   └── v1/          # auth_routes.py, handicap_routes.py
│   │           ├── external/        # RFEGHandicapService, MockHandicapService
│   │           └── persistence/
│   │               └── sqlalchemy/  # Implementaciones de Repositorios
│   └── shared/
│       ├── domain/
│       └── infrastructure/
├── tests/
│   ├── integration/
│   │   └── api/
│   │       └── v1/
│   └── unit/
├── .env
├── alembic.ini
├── docker-compose.yml
├── Dockerfile
├── main.py
├── README.md
└── requirements.txt
```

## 🔬 Descripción Detallada de Componentes Clave

### `src/` - El Corazón de la Aplicación

-   **`src/config/`**:
    -   `database.py`: Configuración de la conexión a la base de datos.
    -   `dependencies.py`: **Composition Root**. Define cómo se construyen e inyectan las dependencias (casos de uso, UoW) en la aplicación.
    -   `mappers.py`: Inicia el mapeo entre las entidades del dominio y las tablas de la base de datos.

-   **`src/modules/user/`**: Contiene todo el código relacionado con la gestión de usuarios, organizado por capas:
    -   `domain/`: Lógica de negocio pura. Aquí viven las entidades (`User`), `ValueObjects` (`UserId`, `Email`, `Password`, `Handicap`), **interfaces** de repositorios (`repositories/`), servicios de dominio (`services/` - `HandicapService`, `PasswordHasher`), eventos (`UserRegisteredEvent`, `HandicapUpdatedEvent`) y errores.
    -   `application/`: Orquesta la lógica de dominio.
        -   `dto/`: Contratos de datos para la comunicación con los casos de uso.
        -   `use_cases/`: Implementación de los casos de uso (`RegisterUserUseCase`, `UpdateUserHandicapUseCase`, `UpdateMultipleHandicapsUseCase`).
        -   `handlers/`: Event handlers (`UserRegisteredEventHandler`).
    -   `infrastructure/`: Implementaciones concretas.
        -   `api/v1/`: Endpoints de FastAPI (`auth_routes.py`, `handicap_routes.py`).
        -   `external/`: Servicios externos (`RFEGHandicapService`, `MockHandicapService`).
        -   `persistence/sqlalchemy/`: Implementación del `UserRepository` con SQLAlchemy.

### `tests/` - Garantía de Calidad

-   **`tests/unit/`**: Tests aislados, rápidos y centrados en la lógica de negocio.
-   **`tests/integration/`**: Tests que verifican la colaboración entre componentes, incluyendo la base de datos y la API.
    -   `api/v1/`: Contiene los tests para los endpoints de la API, como el registro de usuarios.

## 🗺️ Visión a Futuro

A medida que el proyecto crezca, esta estructura se expandirá:

-   **Nuevos Módulos**: Se crearán directorios como `src/modules/tournament/`.
-   **Capa de Presentación**: La capa `infrastructure/api/` contendrá los endpoints de FastAPI que exponen los casos de uso.

Esta estructura modular nos permite añadir nuevas funcionalidades de forma aislada y organizada, manteniendo la complejidad bajo control.