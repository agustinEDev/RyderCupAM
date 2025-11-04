# ADR-010: Uso de Alembic para Migraciones de Base de Datos

- **Estado**: Aceptado
- **Fecha**: 2025-11-04

## Contexto

Con la introducción de una base de datos persistente (PostgreSQL) gestionada por SQLAlchemy, necesitamos una forma sistemática y controlada de gestionar los cambios en el esquema de la base de datos a lo largo del tiempo. A medida que la aplicación evolucione, necesitaremos añadir nuevas tablas, modificar columnas o crear índices.

Gestionar estos cambios manualmente (ejecutando scripts SQL a mano) es propenso a errores, difícil de versionar y no es reproducible entre diferentes entornos (desarrollo, testing, producción).

## Decisión

Se ha decidido adoptar **Alembic** como la herramienta para gestionar las migraciones de la base de datos.

Alembic se integrará con SQLAlchemy para:
1.  **Autogenerar scripts de migración**: Comparará los modelos de SQLAlchemy definidos en nuestro código con el estado actual de la base de datos para generar automáticamente los cambios necesarios.
2.  **Versionar el esquema**: Cada cambio en el esquema se guardará en un fichero de migración versionado, creando un historial auditable de la evolución de la base de datos.
3.  **Aplicar y revertir migraciones**: Proporcionará comandos (`upgrade`, `downgrade`) para aplicar los cambios de forma segura y predecible en cualquier entorno.

## Justificación

1.  **Control de Versiones para la Base de Datos**: Trata el esquema de la base de datos como código, permitiéndonos guardarlo en Git junto con el resto de la aplicación. Esto asegura que una versión específica del código siempre se corresponda con una versión específica del esquema de la base de datos.

2.  **Automatización y Fiabilidad**: El proceso de `autogenerate` reduce drásticamente el riesgo de errores humanos al escribir SQL para DDL (Data Definition Language). Los comandos `upgrade` y `downgrade` hacen que la aplicación de cambios sea un proceso repetible y fiable.

3.  **Facilidad de Despliegue**: Simplifica enormemente el proceso de despliegue. Al desplegar una nueva versión de la aplicación, simplemente se ejecuta `alembic upgrade head` para llevar la base de datos de producción al estado requerido por el nuevo código.

4.  **Integración con SQLAlchemy**: Alembic es el estándar de facto para migraciones en el ecosistema de SQLAlchemy, lo que garantiza una integración perfecta y un amplio soporte de la comunidad.

## Consecuencias

-   **Positivas**:
    -   Proceso de gestión de cambios de la base de datos robusto y auditable.
    -   Despliegues más seguros y predecibles.
    -   Facilita la colaboración en equipo, ya que todos los cambios de esquema están en el control de versiones.

-   **Negativas**:
    -   Añade una nueva herramienta y una capa de complejidad al proyecto que el equipo debe aprender y mantener.
    -   Requiere una configuración inicial cuidadosa para integrarse correctamente con la estructura del proyecto (como hemos visto con la configuración del `PYTHONPATH`).