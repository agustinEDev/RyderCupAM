# ADR-009: Uso de Docker para el Entorno de Desarrollo

- **Estado**: Aceptado
- **Fecha**: 2025-11-04

## Contexto

A medida que el proyecto evoluciona, introduce dependencias de servicios externos, siendo la primera y más crítica una base de datos PostgreSQL. Para desarrollar y probar la aplicación de manera fiable, necesitamos una forma de gestionar estas dependencias que sea consistente, reproducible y aislada del sistema operativo del desarrollador.

Las alternativas a la gestión de estas dependencias incluyen:
1.  **Instalación local**: Cada desarrollador instala y configura PostgreSQL manualmente en su máquina.
2.  **Base de datos compartida en la nube**: Todos los desarrolladores apuntan a una única base de datos remota.
3.  **Contenerización**: Se utiliza una tecnología de contenedores para empaquetar los servicios y ejecutarlos localmente.

## Decisión

Se ha decidido adoptar **Docker** y **Docker Compose** como la herramienta estándar para gestionar el entorno de desarrollo local.

Esto implica:
-   Un `Dockerfile` que define la imagen de nuestra aplicación Python/FastAPI.
-   Un `docker-compose.yml` que orquesta el levantamiento de los servicios necesarios: la aplicación (`app`) y la base de datos PostgreSQL (`db`).
-   El uso de un fichero `.env` para gestionar las credenciales y la configuración, manteniéndolas fuera del control de versiones.

## Justificación

Esta decisión se basa en las siguientes ventajas clave:

1.  **Consistencia del Entorno**: Garantiza que todos los desarrolladores, así como los sistemas de integración continua, ejecuten la aplicación y sus dependencias (como la versión exacta de PostgreSQL) en un entorno idéntico. Esto elimina por completo los problemas del tipo "en mi máquina funciona".

2.  **Aislamiento**: Los servicios se ejecutan en contenedores aislados, lo que evita conflictos con otras bases de datos u otras versiones de servicios que un desarrollador pueda tener instaladas localmente para otros proyectos.

3.  **Facilidad de Configuración (Onboarding)**: Un nuevo desarrollador puede tener todo el entorno de desarrollo funcionando con un único comando (`docker-compose up`). Esto reduce drásticamente el tiempo y la complejidad de la configuración inicial.

4.  **Paridad Desarrollo-Producción**: Nos permite desarrollar en un entorno que se asemeja mucho al entorno de producción final, siguiendo las mejores prácticas de DevOps.

5.  **Portabilidad**: La configuración es completamente portable entre diferentes sistemas operativos (macOS, Windows, Linux) sin necesidad de cambios.

## Consecuencias

-   **Positivas**:
    -   Mayor fiabilidad y reproducibilidad de los builds.
    -   Simplificación del proceso de onboarding para nuevos miembros del equipo.
    -   Entorno de desarrollo limpio y sin conflictos.

-   **Negativas**:
    -   Introduce una dependencia de Docker Desktop, que debe ser instalado por cada desarrollador.
    -   Ligera sobrecarga en el uso de recursos (CPU/RAM) en comparación con la ejecución nativa, aunque es marginal en el hardware moderno.