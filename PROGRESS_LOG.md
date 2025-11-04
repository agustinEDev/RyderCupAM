# 📋 Ryder Cup Manager API - Progress Log

**Proyecto**: API REST para la gestión de torneos de golf estilo Ryder Cup.  
**Arquitectura**: Clean Architecture, Event-Driven, FastAPI.  
**Creación**: 31 de octubre de 2025  
**Última Actualización**: 4 de noviembre de 2025

---

## 🤝 **METODOLOGÍA DE COLABORACIÓN**

Estas son las directrices para nuestra forma de trabajar en este proyecto:

#### **Mi Rol (Asistente IA)**
- 👨‍🏫 **Perfil Didáctico**: Mi objetivo principal es guiarte y enseñarte. Explicaré el *porqué* de cada decisión, los patrones de diseño utilizados y las mejores prácticas recomendadas.
- 🤔 **Proponente, no Implementador**: Te propondré los cambios, la estructura de los ficheros y los fragmentos de código. Sin embargo, **tú serás quien los escriba o los añada al proyecto**.
- ❓ **Guía a través de Preguntas**: Te guiaré paso a paso, haciendo preguntas para asegurar que entiendes el proceso y estás de acuerdo con la dirección que tomamos. No crearé ficheros completos de una sola vez.
- ✅ **Validador**: Una vez que hayas implementado un paso, lo revisaré y te daré feedback si es necesario.

#### **Tu Rol (Desarrollador)**
- ⌨️ **Implementador Activo**: Eres el responsable de escribir el código y aplicar los cambios en los ficheros.
- 👍 **Revisor y Aprobador**: Tienes la última palabra. Cada paso del desarrollo requiere tu revisión y aprobación antes de continuar.

#### **Nuestro Flujo de Trabajo**
1.  **Definir el Objetivo**: Acordamos juntos la meta de la sesión (ej: "Implementar el caso de uso de registro").
2.  **Desglose Paso a Paso**: Desglosaré la tarea en pasos pequeños y manejables.
3.  **Proponer y Explicar**: Para cada paso, te daré el contexto y el código sugerido.
4.  **Tu Implementas**: Tú añades el código al proyecto.
5.  **Tú Confirmas**: Me das tu visto bueno para continuar.
6.  **Iterar**: Repetimos el proceso hasta completar el objetivo.

---

## 📊 **ESTADO ACTUAL DEL PROYECTO**

### 🏆 Hitos Alcanzados
- ✅ **Capa de Dominio Completa**: Modelado robusto de entidades y reglas de negocio.
- ✅ **Infraestructura de Persistencia Real**: Entorno Dockerizado con PostgreSQL, SQLAlchemy y Alembic.
- ✅ **Testing Exhaustivo**: Cobertura total en la lógica de negocio crítica.
- ✅ **Documentación Arquitectónica**: Decisiones clave registradas en ADRs.

### 📈 **Métricas Clave**
- **Tests Totales**: **215/215** pasando.
- **Cobertura de Código**: **100%** en la capa de dominio e infraestructura crítica.
- **Rendimiento de Tests**: Ejecución completa en < 2 segundos (paralelizado).

---

## 🏗️ **ARQUITECTURA Y PROGRESO IMPLEMENTADO**

### I. **Fundamentos del Proyecto y Tooling**
- **Framework**: FastAPI con servidor Uvicorn.
- **Entorno**: Gestión de dependencias con `requirements.txt` y `.venv`.
- **Testing**: `pytest` con `pytest-xdist` para ejecución paralela (7 workers).
- **Seguridad**: `bcrypt` para hashing de contraseñas, optimizado para tests.

### II. **Capa de Dominio (`src/modules/user/domain`)**
- **Entidades**:
  - `User`: Entidad principal con lógica de negocio, factory method `create()` y recolección de eventos de dominio.
- **Value Objects**:
  - `UserId`: UUID v4 inmutable y autovalidado.
  - `Email`: Normalización automática y validación con regex estricta.
  - `Password`: Hashing con bcrypt y validación de fortaleza.
- **Patrones**:
  - **Repository Pattern**: Interfaces definidas (`UserRepository`).
  - **Unit of Work**: Interfaz `UnitOfWork` para gestionar la consistencia transaccional.

### III. **Capa de Infraestructura (`src/shared/infrastructure`)**
- **Persistencia (En Memoria)**:
  - `InMemoryUserRepository`: Implementación para testing y desarrollo temprano.
  - `InMemoryUnitOfWork`: Implementación para gestionar el "commit" en memoria.
- **Sistema de Eventos de Dominio**:
  - `DomainEvent`: Clase base para todos los eventos.
  - `EventBus` y `InMemoryEventBus`: Sistema de publicación/suscripción de eventos.
  - `UserRegisteredEvent`: Ejemplo de evento de dominio concreto.
- **Sistema de Logging Avanzado**:
  - `Logger` Interface y `LoggerFactory` para la creación de loggers.
  - `LogConfig` para configuración por entornos (DEV, PROD).
  - **Formatters**: `TextFormatter`, `JsonFormatter` y `StructuredFormatter`.
  - **Integración**: `EventLoggingHandler` para loggear automáticamente eventos de dominio.
  - **Trazabilidad**: Soporte para `correlation_id` a través de contextos.

### IV. **Capa de Aplicación (`src/modules/user/application`)**
- ⏳ **PENDIENTE**: Este es el siguiente hito a desarrollar.

### V. **Capa de Presentación (API)**
- **Endpoints**:
  - `GET /health`: Endpoint de salud para verificar el estado del servicio.

---

## 🧪 **ESTRATEGIA DE TESTING**

El proyecto se basa en una pirámide de testing robusta, con un fuerte énfasis en los tests unitarios para la lógica de negocio.

- **Tests Unitarios**:
  - **Ubicación**: `tests/unit/`
  - **Foco**: Validan entidades, value objects, y servicios de dominio de forma aislada.
  - **Métricas**: ~90% del total de tests.
- **Tests de Integración**:
  - **Ubicación**: `tests/integration/`
  - **Foco**: Verifican la correcta colaboración entre componentes (ej: EventBus con Handlers, Repositorios con UoW).
  - **API Endpoints**: Se testean con un cliente HTTP (`httpx`).

---

## 📚 **DOCUMENTACIÓN**

Las decisiones arquitectónicas importantes se registran en **ADRs (Architecture Decision Records)** en la carpeta `docs/architecture/decisions/`.

- **ADR-001**: Elección de Clean Architecture.
- **ADR-002**: Elección de FastAPI.
- **ADR-003**: Estructura de Módulos.
- **ADR-004**: Value Objects.
- **ADR-005**: Repository y Unit of Work Patterns.
- **ADR-006**: Estrategia de Testing.
- **ADR-007**: Domain Events Pattern.
- **ADR-008**: Sistema de Logging Avanzado.

---

## 🎯 PRÓXIMO HITO: IMPLEMENTACIÓN DE LA CAPA DE APLICACIÓN

**Objetivo**: Desarrollar los casos de uso y servicios que orquestan la lógica de dominio, usando la infraestructura de persistencia que hemos creado.

**Plan de Acción**:
1.  **Crear Estructura**:
    - `src/users/application/use_cases/`
    - `src/users/application/services/`
    - `src/users/application/dto/`
2.  **Implementar Caso de Uso `RegisterUserUseCase`**:
    - Orquestará la creación del `User`.
    - Usará el `SQLAlchemyUnitOfWork` para garantizar la consistencia.
    - Guardará el usuario a través del `uow.users`.
    - Publicará el evento `UserRegisteredEvent` a través del `EventBus`.
3.  **Crear DTOs (Data Transfer Objects)**:
    - Definir `RegisterUserCommand` (entrada) y `UserResponse` (salida).
4.  **Escribir Tests de Aplicación**:
    - Tests unitarios para el caso de uso, mockeando el UoW.
    - Tests de integración que usen la base de datos real en Docker.
