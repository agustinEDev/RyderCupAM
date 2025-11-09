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

## Casos de Uso Implementados

### Módulo User

#### 1. RegisterUserUseCase
- **Propósito**: Registrar un nuevo usuario en el sistema
- **Entrada**: `RegisterUserRequestDTO` (first_name, last_name, email, password)
- **Salida**: `UserResponseDTO`
- **Flujo**:
  1. Verifica que el email no exista
  2. Crea entidad User con factory method
  3. Guarda en repositorio
  4. Commit de transacción
  5. Publica UserRegisteredEvent
- **Tests**: Cobertura completa con casos exitosos y de error

#### 2. UpdateUserHandicapUseCase (Nuevo - 9 Nov 2025)
- **Propósito**: Actualizar hándicap de usuario consultando RFEG
- **Entrada**: `UserId`, `Optional[manual_handicap]`
- **Salida**: `Optional[UserResponseDTO]`
- **Dependencias**: `UnitOfWork`, `HandicapService` (RFEG o Mock)
- **Flujo**:
  1. Busca usuario por ID
  2. Consulta HandicapService con nombre completo
  3. Si encuentra handicap en RFEG, actualiza
  4. Si no encuentra pero hay manual_handicap, usa ese
  5. Commit genera HandicapUpdatedEvent
- **Características**:
  - ✅ Integración con servicio externo (RFEG)
  - ✅ Fallback a valor manual
  - ✅ No bloqueante (retorna None si no encuentra usuario)
  - ✅ Emite evento de dominio para auditoría

#### 3. UpdateUserHandicapManuallyUseCase (Nuevo - 9 Nov 2025)
- **Propósito**: Actualizar hándicap directamente sin consultar RFEG
- **Entrada**: `UserId`, `handicap: float`
- **Salida**: `Optional[UserResponseDTO]`
- **Dependencias**: Solo `UnitOfWork`
- **Flujo**:
  1. Busca usuario por ID
  2. Actualiza hándicap con valor proporcionado
  3. Validación automática por Handicap VO
  4. Commit genera HandicapUpdatedEvent
- **Uso**: Administradores o jugadores no federados
- **Validación**: ValueError si handicap fuera de rango (-10.0 a 54.0)

#### 4. UpdateMultipleHandicapsUseCase (Nuevo - 9 Nov 2025)
- **Propósito**: Actualizar hándicaps de múltiples usuarios en batch
- **Entrada**: `List[UserId]`
- **Salida**: `dict` con estadísticas (total, updated, not_found, no_handicap_found, errors)
- **Dependencias**: `UnitOfWork`, `HandicapService`
- **Flujo**:
  1. Itera sobre lista de user_ids
  2. Por cada usuario:
     - Busca usuario
     - Consulta RFEG
     - Actualiza si encuentra
  3. Acumula estadísticas
  4. Single commit para todo el batch
  5. Publica todos los eventos
- **Características**:
  - ✅ Procesamiento batch eficiente
  - ✅ Resiliente: continúa aunque algunos fallen
  - ✅ Transacción única (all-or-nothing)
  - ✅ Estadísticas detalladas para reporting

#### 5. FindUserUseCase (Nuevo - 9 Nov 2025)
- **Propósito**: Buscar usuario por email o nombre completo
- **Entrada**: `FindUserRequestDTO` (email o full_name)
- **Salida**: `FindUserResponseDTO`
- **Flujo**:
  1. Valida que al menos un criterio esté presente
  2. Busca por email o nombre en repositorio
  3. Retorna datos del usuario si existe
- **Uso**: Búsqueda antes de actualizar handicap, integración con otros sistemas

### Patrones en Casos de Uso

#### Gestión Transaccional Consistente
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

#### Integración con Servicios Externos
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

#### Manejo de Errores
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

## Métricas (Actualizado 9 Nov 2025)

- **Casos de Uso Implementados**: 5 (RegisterUser + 4 de Handicap)
- **Tests de Use Cases**: 9 tests específicos
- **Tests Totales**: 330 (100% passing)
- **Cobertura**: 100% en lógica de casos de uso

## Referencias

- [ADR-001: Clean Architecture](./ADR-001-clean-architecture.md)
- [ADR-006: Unit of Work](./ADR-006-unit-of-work-pattern.md)
- [ADR-007: Domain Events](./ADR-007-domain-events-pattern.md)
- [ADR-012: Composition Root](./ADR-012-composition-root.md)
- [ADR-013: External Services Pattern](./ADR-013-external-services-pattern.md)
- [ADR-014: Handicap Management System](./ADR-014-handicap-management-system.md)
