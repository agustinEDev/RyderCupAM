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
│   ├── modules/
│   │   └── user/
│   │       ├── application/
│   │       │   ├── dto/ # - Data Transfer Objects (user_dto.py)
│   │       │   └── use_cases/ # - Casos de Uso (register_user.py)
│   │       ├── domain/
│   │       │   ├── entities/
│   │       │   ├── errors/ # - Excepciones de dominio (user_errors.py)
│   │       │   ├── services/ # - Servicios de dominio (user_finder.py)
│   │       │   └── value_objects/
│   │       └── infrastructure/
│   │           └── persistence/
│   │               ├── in_memory/ # - Implementaciones para tests unitarios
│   │               └── sqlalchemy/ # - Implementaciones para producción/integración
│   └── shared/
│       ├── domain/
│       └── infrastructure/
├── tests/
│   ├── integration/
│   └── unit/
│       └── modules/
│           └── user/
│               └── application/
│                   └── use_cases/ # - Tests para los casos de uso
├── .env
├── alembic.ini
├── docker-compose.yml
├── Dockerfile
├── main.py
├── PROGRESS_LOG.md
├── README.md
└── requirements.txt
```

## 🔬 Descripción Detallada de Componentes Clave

### `src/` - El Corazón de la Aplicación

-   **`src/modules/user/`**: Contiene todo el código relacionado con la gestión de usuarios, organizado por capas:
    -   `domain/`: Lógica de negocio pura. Aquí viven las entidades (`User`), `ValueObjects`, **interfaces** de repositorios, y ahora también los `services` (como `UserFinder`) y `errors` específicos del dominio.
    -   `application/`: Orquesta la lógica de dominio para realizar acciones concretas.
        -   `dto/`: Define los contratos de datos (`RegisterUserRequestDTO`, `UserResponseDTO`) para la comunicación con los casos de uso.
        -   `use_cases/`: Contiene la implementación de los casos de uso, como `RegisterUserUseCase`.
    -   `infrastructure/persistence/`: Implementa los contratos del dominio.
        -   `sqlalchemy/`: Implementación real con base de datos.
        -   `in_memory/`: Implementación de "dobles de prueba" para los tests unitarios, permitiendo una ejecución rápida y aislada.

### `tests/` - Garantía de Calidad

-   **`tests/unit/modules/user/application/use_cases/`**: Nueva sección dedicada a los tests unitarios de los casos de uso. Estos tests utilizan la persistencia `in_memory` para validar la lógica de la aplicación sin tocar la base de datos.
-   **`tests/integration/`**: Tests que verifican la colaboración entre varias partes del sistema, como un endpoint de la API llamando a un caso de uso que interactúa con la base de datos real (en Docker).

## 🗺️ Visión a Futuro

A medida que el proyecto crezca, esta estructura se expandirá:

-   **Nuevos Módulos**: Se crearán directorios como `src/modules/tournament/`, cada uno con sus capas `domain`, `application`, e `infrastructure`.
-   **Casos de Uso**: La capa `application/` se poblará con los casos de uso (Use Cases) que orquestan la lógica de dominio para realizar acciones concretas.
-   **Capa de Presentación**: La capa `infrastructure/` contendrá los endpoints de FastAPI que exponen los casos de uso a través de la API REST.

Esta estructura modular nos permite añadir nuevas funcionalidades de forma aislada y organizada, manteniendo la complejidad bajo control.