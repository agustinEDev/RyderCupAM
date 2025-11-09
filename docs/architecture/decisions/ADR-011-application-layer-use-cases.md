# ADR-011: Implementación de la Capa de Aplicación con Casos de Uso

**Fecha**: 2025-11-05  
**Estado**: Aceptado

## Contexto

Con la capa de dominio y la de infraestructura de persistencia ya establecidas, la aplicación necesita una capa intermedia que orqueste la lógica de negocio sin acoplar la API a los detalles del dominio. Esta capa debe manejar las interacciones del usuario (o de otros sistemas), ejecutar las reglas de negocio y coordinar la persistencia de los datos de forma transaccional.

## Decisión

Se ha decidido implementar una **Capa de Aplicación** explícita, cuyo principal componente serán los **Casos de Uso (Use Cases)**.

Cada caso de uso representará una única acción o funcionalidad que el sistema puede realizar, como `RegisterUserUseCase`, `UpdateUserHandicapUseCase` o `CreateTournamentUseCase`.

### Responsabilidades de un Caso de Uso:

1.  **Orquestación**: Un caso de uso no contiene lógica de negocio en sí mismo. Su función es orquestar los objetos de dominio (Entidades, Value Objects, Servicios de Dominio) para que realicen el trabajo.
2.  **Gestión Transaccional**: El caso de uso controlará los límites de la transacción a través de la interfaz `UnitOfWork`. Iniciará la transacción, coordinará las operaciones y confirmará (`commit`) o revertirá (`rollback`) los cambios.
3.  **Desacoplamiento**: Dependerá únicamente de las abstracciones (interfaces) definidas en la capa de dominio (ej: `UserRepositoryInterface`, `UnitOfWorkInterface`), nunca de implementaciones concretas.
4.  **Contratos de Datos (DTOs)**: Recibirá los datos de entrada a través de un DTO de Petición (Request DTO) y devolverá los datos de salida a través de un DTO de Respuesta (Response DTO).

### Ejemplo de Flujo (`RegisterUserUseCase`):

1.  Recibe un `RegisterUserRequestDTO`.
2.  Inicia una transacción con `async with uow:`.
3.  Utiliza un Servicio de Dominio (`UserFinder`) para verificar si el usuario ya existe.
4.  Llama al factory `User.create()` para crear la entidad.
5.  Guarda la nueva entidad usando `uow.users.save(user)`.
6.  Confirma la transacción con `uow.commit()`.
7.  Devuelve un `UserResponseDTO`.

## Consecuencias

### Positivas:

-   **Principio de Responsabilidad Única (SRP)**: La lógica de la aplicación está claramente separada de la lógica de dominio y de la infraestructura.
-   **Testabilidad**: Los casos de uso son extremadamente fáciles de testear unitariamente, ya que se les pueden inyectar dependencias falsas (`InMemoryUnitOfWork`).
-   **Reutilización**: La misma lógica de caso de uso puede ser invocada desde diferentes puntos de entrada (una API REST, un CLI, un worker de colas) sin cambios.
-   **Claridad**: El código se vuelve muy expresivo y fácil de seguir, ya que cada fichero representa una acción de negocio clara.

### Negativas:

-   **Verbosity**: Puede parecer que añade más ficheros (DTOs, Use Cases), pero esta "verbosidad" es en realidad una organización explícita que se agradece a medida que el proyecto crece.

## Patrones en Casos de Uso

### Gestión Transaccional Consistente
```python
async with self._uow:
    # Operaciones de dominio
    user = await self._uow.users.find_by_id(user_id)
    user.update_handicap(new_handicap)

    # Persistencia
    await self._uow.users.update(user)

    # Commit (publica eventos automáticamente)
    await self._uow.commit()
```

### Integración con Servicios Externos
```python
class UpdateUserHandicapUseCase:
    def __init__(
        self,
        uow: UserUnitOfWorkInterface,
        handicap_service: HandicapService  # ← Inyección de abstracción
    ):
        self._uow = uow
        self._handicap_service = handicap_service
```

### Manejo de Errores
```python
# Retornar None para "not found"
if not user:
    return None

# ValueError para validaciones de negocio
try:
    user.update_handicap(handicap)
except ValueError as e:
    raise  # Se maneja en el endpoint HTTP
```

## Referencias

- [ADR-001: Clean Architecture](./ADR-001-clean-architecture.md)
- [ADR-006: Unit of Work](./ADR-006-unit-of-work-pattern.md)
- [ADR-007: Domain Events](./ADR-007-domain-events-pattern.md)
- [ADR-012: Composition Root](./ADR-012-composition-root.md)
- [ADR-013: External Services Pattern](./ADR-013-external-services-pattern.md)
- [ADR-014: Handicap Management System](./ADR-014-handicap-management-system.md)
- [Design Document](../design-document.md) - Ver sección Métricas para Use Cases implementados
