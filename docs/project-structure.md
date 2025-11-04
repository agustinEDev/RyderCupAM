# 📂 Estructura del Proyecto

Este documento describe la organización de carpetas y ficheros del proyecto Ryder Cup Manager API. La estructura sigue los principios de **Clean Architecture** y **Monolito Modular**, separando el código por responsabilidades (capas) y por funcionalidades de negocio (módulos).

## 🌳 Estructura de Directorios Detallada

El siguiente árbol representa la estructura completa y actual del proyecto.

```
.
├── alembic/ # 📜 Scripts y configuración de migraciones de base de datos
│ └── versions/ # - Ficheros de migración versionados
├── docs/ # 📚 Documentación del proyecto
│ ├── architecture/
│ │ └── decisions/ # - Architecture Decision Records (ADRs)
│ └── project-structure.md
├── src/ # 🐍 Código fuente de la aplicación
│ ├── config/ # - Configuración de infraestructura (ej: conexión a BD)
│ │ └── database.py
│ ├── modules/ # - Módulos de negocio (ej: user)
│ │ └── user/
│ │ ├── application/ # - Casos de uso y lógica de aplicación
│ │ │ └── handlers/ # - Manejadores de eventos de dominio
│ │ ├── domain/ # - Lógica y reglas de negocio puras (entidades, VOs)
│ │ └── infrastructure/ # - Implementación técnica (repositorios, mappers)
│ │ └── persistence/
│ │ └── sqlalchemy/
│ └── shared/ # - Código compartido entre módulos
│ ├── domain/ # - Abstracciones de dominio (Eventos, UoW, etc.)
│ └── infrastructure/ # - Implementaciones compartidas (EventBus, Logging)
├── tests/ # 🧪 Tests automatizados
│ ├── integration/ # - Tests que verifican la colaboración entre componentes
│ │ ├── api/
│ │ ├── domain_events/
│ │ └── modules/
│ └── unit/ # - Tests que verifican componentes de forma aislada
│ ├── modules/
│ └── shared/
├── .env # - Fichero de variables de entorno (ignorado por Git)
├── .gitignore # - Ficheros y carpetas ignorados por Git
├── alembic.ini # - Fichero de configuración principal de Alembic
├── docker-compose.yml # - Orquestación de los contenedores de desarrollo (app + db)
├── Dockerfile # - "Receta" para construir la imagen Docker de la aplicación
├── main.py # - Punto de entrada de la aplicación FastAPI
├── PROGRESS_LOG.md # - Bitácora de progreso y decisiones de la sesión
├── README.md # - Portada y resumen general del proyecto
└── requirements.txt # - Dependencias de Python del proyecto
```

## 🔬 Descripción Detallada de Componentes Clave

### `src/` - El Corazón de la Aplicación

-   **`src/config/database.py`**: Configura la conexión a la base de datos con SQLAlchemy y registra adaptadores para nuestros `ValueObjects`.
-   **`src/modules/user/`**: Contiene todo el código relacionado con la gestión de usuarios, organizado por capas:
    -   `domain/`: Lógica de negocio pura. Aquí viven las entidades (`User`), `ValueObjects` (`UserId`, `Email`), y las **interfaces** de los repositorios y del `Unit of Work`.
    -   `application/handlers/`: Implementaciones concretas de los manejadores de eventos. Orquestan acciones en respuesta a eventos de dominio (ej: enviar un email cuando un usuario se registra).
    -   `infrastructure/persistence/sqlalchemy/`: Implementa los contratos del dominio usando SQLAlchemy.
        -   `mappers.py`: Define cómo la entidad `User` se mapea a la tabla `users`. Utiliza `TypeDecorator` y `composite` para manejar los `ValueObjects`.
        -   `user_repository.py`: Implementación del `UserRepositoryInterface`.
        -   `unit_of_work.py`: Implementación del `UserUnitOfWorkInterface`.
-   **`src/shared/`**: Código agnóstico al dominio de negocio, pero fundamental para la arquitectura.
    -   `domain/`: Interfaces genéricas como `UnitOfWorkInterface`, `DomainEvent`, `EventHandler`.
    -   `infrastructure/`: Implementaciones concretas como `InMemoryEventBus` y el sistema de `Logging`.

### `tests/` - Garantía de Calidad

-   **`tests/unit/`**: Tests rápidos y aislados que no tocan la base de datos ni la red. Su estructura refleja la de `src/`, probando la lógica de dominio y las interfaces de forma pura.
-   **`tests/integration/`**: Tests que verifican la colaboración entre varias partes del sistema. Requieren que el entorno Docker (`docker-compose up`) esté activo.
    -   `api/`: Prueban los endpoints de FastAPI.
    -   `domain_events/`: Verifican el flujo completo desde que se genera un evento hasta que su manejador lo procesa.
    -   `modules/.../persistence/`: Prueban que la capa de persistencia funciona correctamente contra una base de datos real.

## 🗺️ Visión a Futuro

A medida que el proyecto crezca, esta estructura se expandirá:

-   **Nuevos Módulos**: Se crearán directorios como `src/modules/tournament/`, cada uno con sus capas `domain`, `application`, e `infrastructure`.
-   **Casos de Uso**: La capa `application/` se poblará con los casos de uso (Use Cases) que orquestan la lógica de dominio para realizar acciones concretas.
-   **Capa de Presentación**: La capa `infrastructure/` contendrá los endpoints de FastAPI que exponen los casos de uso a través de la API REST.

Esta estructura modular nos permite añadir nuevas funcionalidades de forma aislada y organizada, manteniendo la complejidad bajo control.