# 🧪 Estrategia de Testing del Ryder Cup Manager

Este documento describe la filosofía, estructura y herramientas utilizadas para el testing automatizado en el proyecto, asegurando la calidad y fiabilidad de la API.

## 🎯 Filosofía

Nos adherimos a una estricta política de **Test-Driven Development (TDD)**. Un conjunto de tests robusto es fundamental para:

-   **Garantizar la Calidad**: Asegurar que la lógica de negocio funciona como se espera.
-   **Prevenir Regresiones**: Detectar errores introducidos por nuevos cambios.
-   **Facilitar el Refactoring**: Permitir la mejora del código con la confianza de que no se ha roto nada.
-   **Servir como Documentación Viva**: Los tests son el mejor ejemplo de cómo debe usarse el código.

## 🏗️ Estructura de Directorios

La carpeta `tests/` refleja la estructura de `src/` y los principios de la Clean Architecture, separando los tests por su alcance y propósito.

```
tests/
├── reports/          # 📊 Reportes generados por el script de tests
│   ├── test_report.json
│   ├── test_summary.md
│   └── warnings.txt
│
├── unit/             # 🔬 Tests Unitarios (553 tests - rápidos y aislados)
│   ├── modules/
│   │   └── user/
│   │       └── domain/
│   │           ├── entities/
│   │           ├── errors/
│   │           ├── repositories/ (interfaces)
│   │           └── value_objects/
│   └── shared/
│       └── domain/
│           ├── events/
│           └── repositories/ (interfaces)
│
└── integration/      # 🔗 Tests de Integración (119 tests - requieren entorno Docker)
    ├── api/          # -> Prueban los endpoints de FastAPI
    └── modules/
        └── user/
            └── infrastructure/
                └── persistence/
                    └── sqlalchemy/ # -> Prueban la capa de persistencia
```

-   **`tests/unit/`**: Contiene tests que verifican pequeños componentes de forma **aislada**. Se centran en la **Capa de Dominio** (entidades, `ValueObjects`, interfaces de repositorios) y no tienen dependencias externas como bases de datos o APIs. Son extremadamente rápidos.

-   **`tests/integration/`**: Verifica que varios componentes colaboran correctamente. Por ejemplo, que el `SQLAlchemyUserRepository` puede guardar y recuperar un `User` de la base de datos. Estos tests son más lentos y **requieren que el entorno Docker esté funcionando**.

## 🚀 Cómo Ejecutar los Tests

La forma principal y recomendada de ejecutar la suite de tests es a través de nuestro script personalizado `dev_tests.py`.

### Uso Principal: `dev_tests.py`

Este script orquesta `pytest` para proporcionar una experiencia de testing mejorada.

1.  **Asegúrate de que tu entorno virtual está activado**:
    ```bash
    source .venv/bin/activate
    ```

2.  **Ejecuta el script desde la raíz del proyecto**:
    ```bash
    python dev_tests.py
    ```

**Ventajas de usar `dev_tests.py`:**
-   **Paralelización Automática**: Usa `pytest-xdist` para ejecutar tests en paralelo, reduciendo drásticamente el tiempo de ejecución.
-   **Salida Organizada**: Presenta los resultados agrupados por capa y módulo, facilitando la identificación de problemas.
-   **Generación de Reportes**: Crea automáticamente los reportes en el directorio `tests/reports/`.

### Ejecución Directa con `pytest`

Para depurar un fichero o un test específico, puedes usar `pytest` directamente:
```bash
# Ejecutar todos los tests en un fichero
pytest tests/unit/modules/user/domain/value_objects/test_user_id.py

# Ejecutar un test específico por su nombre
pytest tests/unit/modules/user/domain/entities/test_user.py::TestUserCreation::test_create_user_with_valid_data
```

## �️ Configuración Clave

La configuración de nuestro entorno de pruebas se basa en varios ficheros y convenciones importantes.

### 1. `pytest.ini`

Este fichero es **esencial** y no debe ser eliminado. Contiene dos configuraciones críticas:

-   `asyncio_mode = auto`: Le indica a `pytest-asyncio` que ejecute automáticamente todas las funciones de prueba marcadas como `async def`. Esto nos ahorra tener que añadir el decorador `@pytest.mark.asyncio` a cada test asíncrono.
-   `markers`: Registra marcadores personalizados como `integration` para que podamos categorizar y filtrar pruebas sin generar advertencias.

### 2. `tests/conftest.py`

Este es el corazón de nuestra configuración de `pytest`. Define fixtures y hooks globales que son cruciales para el funcionamiento de las pruebas.

#### Hooks Globales

-   `pytest_configure(config)`: Se asegura de que los **mappers de SQLAlchemy** se inicialicen una sola vez por sesión de prueba, incluso cuando se ejecutan en paralelo con `pytest-xdist`. Esto previene condiciones de carrera y errores de inicialización.

#### Fixtures Principales

-   `client()`: Es la fixture principal para los **tests de integración de la API**. Proporciona un `AsyncClient` de `httpx` para realizar peticiones a la aplicación FastAPI. Su característica más importante es el **aislamiento total de la base de datos**:
    -   Crea una **base de datos de prueba única para cada proceso trabajador** de `pytest-xdist` (ej. `test_db_gw0`, `test_db_gw1`).
    -   Crea todo el esquema de tablas antes de cada test.
    -   Destruye la base de datos de prueba completa después de cada test.
    -   Esto garantiza que las pruebas paralelas no interfieran entre sí y que cada test se ejecute en un entorno limpio.

-   `db_session()`: Proporciona una **sesión de base de datos (`AsyncSession`) aislada** para tests que interactúan directamente con la capa de persistencia (por ejemplo, para probar un repositorio). Al igual que la fixture `client`, crea y destruye el esquema de la base de datos para cada test.

-   **Fixtures de Datos** (`sample_user_data`, `multiple_users_data`, etc.): Proveen datos consistentes y reutilizables para las pruebas unitarias y de integración, facilitando la escritura y lectura de los tests.

## �📊 Interpretación de los Reportes

Después de cada ejecución de `dev_tests.py`, encontrarás tres reportes en la carpeta `tests/reports/`:

1.  **`test_report.json`**:
    -   **Propósito**: Fichero de datos crudos generado por `pytest-json-report`.
    -   **Uso**: Ideal para integraciones con sistemas de CI/CD, dashboards o cualquier análisis programático de los resultados de los tests.

2.  **`test_summary.md`**:
    -   **Propósito**: Un reporte en formato Markdown, legible para humanos, generado por nuestro script.
    -   **Contenido**:
        -   Resumen global con estadísticas (tests pasados, fallados, tasa de éxito, **warnings**).
        -   Sección dedicada de warnings con detalles completos.
        -   Lista de los 3 tests más lentos para identificar cuellos de botella.
        -   Detalle de cada test fallado, incluyendo el `traceback` completo del error.
    -   **Uso**: Es la forma más rápida de analizar los resultados de una ejecución y entender por qué ha fallado un test.

3.  **`warnings.txt`**:
    -   **Propósito**: Captura todos los warnings emitidos por pytest durante la ejecución.
    -   **Contenido**: Lista completa de warnings con ubicación del archivo y línea.
    -   **Uso**: Identificar deprecaciones, configuraciones faltantes o problemas potenciales en el código o dependencias.
