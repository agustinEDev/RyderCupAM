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
│   └── test_summary.md
│
├── unit/             # 🔬 Tests Unitarios (rápidos y aislados)
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
└── integration/      # 🔗 Tests de Integración (requieren entorno Docker)
    ├── api/          # -> Prueban los endpoints de FastAPI
    ├── domain_events/ # -> Prueban el flujo completo de eventos
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

## 📊 Interpretación de los Reportes

Después de cada ejecución de `dev_tests.py`, encontrarás dos reportes en la carpeta `tests/reports/`:

1.  **`test_report.json`**:
    -   **Propósito**: Fichero de datos crudos generado por `pytest-json-report`.
    -   **Uso**: Ideal para integraciones con sistemas de CI/CD, dashboards o cualquier análisis programático de los resultados de los tests.

2.  **`test_summary.md`**:
    -   **Propósito**: Un reporte en formato Markdown, legible para humanos, generado por nuestro script.
    -   **Contenido**:
        -   Resumen global con estadísticas (tests pasados, fallados, tasa de éxito).
        -   Lista de los 3 tests más lentos para identificar cuellos de botella.
        -   Detalle de cada test fallado, incluyendo el `traceback` completo del error.
    -   **Uso**: Es la forma más rápida de analizar los resultados de una ejecución y entender por qué ha fallado un test.
