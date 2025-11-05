# ADR-012: Patrón Composition Root para Inyección de Dependencias

**Fecha**: 2025-11-05  
**Estado**: Aceptado

## Contexto

A medida que implementamos los Casos de Uso, surge la necesidad de "construirlos" y proporcionarles sus dependencias (como el `UnitOfWork`). La capa de presentación (API con FastAPI) necesita una instancia de un caso de uso para poder ejecutarlo, pero no debería ser responsable de su construcción.

Si el endpoint de la API crea manualmente el `UnitOfWork` y el `UseCase`, se acoplaría fuertemente a los detalles de implementación de la capa de persistencia, violando la Clean Architecture.

## Decisión

Se ha decidido adoptar el patrón **Composition Root**. Este será el único lugar en la aplicación donde se compondrá el grafo de dependencias de los objetos.

El Composition Root será una capa muy fina de código, ubicada cerca del punto de entrada de la aplicación (`main.py`), que actuará como una "fábrica" o "ensamblador".

### Implementación con FastAPI:

Utilizaremos el sistema de **Inyección de Dependencias** de FastAPI (`Depends`) para implementar este patrón de forma elegante.

1.  **Crearemos "proveedores" (providers)**: Funciones simples que saben cómo construir una dependencia. Por ejemplo, una función `get_db_session` que crea y gestiona una sesión de SQLAlchemy.
2.  **Compondremos las dependencias en cadena**:
    -   Una función `get_uow` dependerá de `get_db_session` para crear una instancia de `SQLAlchemyUnitOfWork`.
    -   Una función `get_register_user_use_case` dependerá de `get_uow` para crear una instancia de `RegisterUserUseCase`.
3.  **Inyectaremos el Caso de Uso en el Endpoint**: El endpoint de la API simplemente declarará su necesidad del caso de uso a través de `Depends`:

    ```python
    @router.post("/register")
    async def register_user(
        use_case: RegisterUserUseCase = Depends(get_register_user_use_case)
    ):
        # ... usar el use_case ...
    ```

## Consecuencias

### Positivas:

-   **Desacoplamiento Máximo**: La capa de API queda completamente desacoplada de la creación de sus dependencias. Solo conoce la interfaz del caso de uso.
-   **Configuración Centralizada**: Toda la lógica de "cableado" de la aplicación reside en un único lugar. Si necesitamos cambiar una implementación (ej: de `SQLAlchemyUnitOfWork` a otra), solo lo cambiamos en el Composition Root.
-   **Facilita el Testing de Integración**: FastAPI permite sobreescribir dependencias durante los tests (`app.dependency_overrides`), lo que facilita enormemente el reemplazo de dependencias reales por dobles de prueba.
-   **Código Limpio en la API**: Los endpoints se mantienen delgados y enfocados en su tarea de manejar la petición HTTP, delegando todo el trabajo al caso de uso inyectado.

### Negativas:

-   **Curva de Aprendizaje**: El concepto de inyección de dependencias puede ser nuevo para algunos desarrolladores, pero el sistema de FastAPI lo hace muy intuitivo.
-   **Gestión de Dependencias**: A medida que la aplicación crezca, el Composition Root puede volverse más complejo, pero existen librerías de inyección de dependencias más avanzadas si fuera necesario.
