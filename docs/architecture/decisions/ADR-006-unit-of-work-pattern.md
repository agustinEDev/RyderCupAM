# ADR-006: Unit of Work Pattern for Transaction Management

## Status
**ACCEPTED** - 1 Noviembre 2025

## Context
Con el patrón Repository implementado, necesitamos una forma de coordinar múltiples operaciones de repositorio dentro de una transacción atómica. El patrón Unit of Work nos permite mantener la consistencia de datos y garantizar que todas las operaciones se completen exitosamente o se reviertan completamente.

### Problemas Identificados
1. **Transacciones complejas**: Operaciones que involucran múltiples repositorios
2. **Consistencia de datos**: Garantizar atomicidad en operaciones de negocio
3. **Gestión manual**: Evitar commit/rollback manual en cada caso de uso
4. **Performance**: Optimizar el número de conexiones a base de datos

### Casos de Uso Ejemplo
```python
# Registro de usuario (ejemplo)
async def register_user(email: str, password: str):
    # Múltiples operaciones que deben ser atómicas:
    # 1. Verificar que email no existe
    # 2. Crear usuario
    # 3. Registrar evento de auditoría
    # 4. Enviar email de bienvenida (futuro)
```

### Alternativas Consideradas
1. **Gestión manual de transacciones**: En cada caso de uso
   - ❌ Código repetitivo
   - ❌ Propenso a errores (olvidar rollback)
   - ❌ Viola DRY principle

2. **Transacciones en repositorios**: Cada repositorio maneja su transacción
   - ❌ No garantiza atomicidad entre repositorios
   - ❌ Dificil coordinación

3. **Unit of Work Pattern**: Coordinador central de transacciones
   - ✅ Gestión automática de commit/rollback
   - ✅ Atomicidad garantizada
   - ✅ Context manager para gestión de recursos

## Decision
Implementaremos el **patrón Unit of Work** con soporte async y context manager para gestión automática de transacciones.

### Arquitectura de Interfaces

#### Base Interface
```python
@abstractmethod
class UnitOfWorkInterface(ABC):
    async def __aenter__(self) -> 'UnitOfWorkInterface': ...
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None: ...
    
    @abstractmethod
    async def commit(self) -> None: ...
    
    @abstractmethod
    async def rollback(self) -> None: ...
    
    @abstractmethod
    async def flush(self) -> None: ...
    
    @abstractmethod
    def is_active(self) -> bool: ...
```

#### Module-Specific Interface
```python
@abstractmethod
class UserUnitOfWorkInterface(UnitOfWorkInterface):
    @property
    @abstractmethod
    def users(self) -> UserRepositoryInterface: ...
```

### Características Implementadas

**Core Features**:
1. **Async Context Manager**: Gestión automática con `async with`
2. **Type Safety**: Interfaces tipadas para mejor desarrollo
3. **Module-Specific**: UoW específicas para cada módulo
4. **Exception Handling**: Rollback automático en caso de error

**Evolution (9 Nov 2025)** - Clean Architecture Enhancement:
5. **Fully Automatic Transactions**: Context manager handles all commit/rollback
6. **Domain Events Publication**: Automatic event publishing post-commit  
7. **Zero Transaction Code in Use Cases**: Complete separation of concerns
8. **Robust Error Handling**: Guaranteed rollback on any exception

### Patrón de Uso

**Versión Inicial (1 Nov 2025)**:
```python
async def execute_use_case(command: Command, uow: UserUnitOfWorkInterface):
    async with uow:  # Inicia transacción
        # Operaciones con repositorios
        user = await User.create(...)
        await uow.users.save(user)
        
        # Commit explícito
        await uow.commit()
    # Si hay excepción, rollback automático en __aexit__
```

**Versión Actual (9 Nov 2025)** - Evolucionado para Clean Architecture:
```python
async def execute_use_case(command: Command, uow: UserUnitOfWorkInterface):
    async with uow:  # Context manager maneja TODO automáticamente
        # Solo lógica de negocio - Use Case no conoce transacciones
        user = await User.create(...)
        await uow.users.save(user)
        
        # NO más commit explícito - violaba Clean Architecture
    # Commit automático en __aexit__ (éxito) o rollback (excepción)
```

## Consequences

### Beneficios
- ✅ **Atomicidad garantizada**: Todas las operaciones exitosas o ninguna
- ✅ **Gestión automática**: Context manager maneja commit/rollback
- ✅ **Consistencia**: Estado coherente de datos garantizado
- ✅ **Testabilidad**: Fácil mockear para tests unitarios
- ✅ **Performance**: Una conexión por transacción
- ✅ **Clean Code**: Casos de uso más legibles y mantenibles

### Desafíos
- ⚠️ **Complejidad inicial**: Conceptos avanzados de transacciones
- ⚠️ **Async complexity**: Manejo correcto de async context managers
- ⚠️ **Memory management**: Correcta limpieza de recursos

### Impacto Técnico
- **Testing**: 18 tests específicos para Unit of Work interfaces
- **Architecture**: Capa adicional de coordinación transaccional
- **Performance**: Optimización de conexiones de base de datos
- **Error Handling**: Gestión automática de rollback en excepciones

## Implementation Details

### Jerarquía de Interfaces
```
UnitOfWorkInterface (Base)
    ├── UserUnitOfWorkInterface
    ├── CompetitionUnitOfWorkInterface (Futuro)
    └── TeamUnitOfWorkInterface (Futuro)
```

### Context Manager Implementation
- **__aenter__**: Inicia sesión/transacción
- **__aexit__**: Commit (éxito) o rollback (excepción) automático
- **commit()**: Confirma cambios explícitamente
- **rollback()**: Revierte cambios explícitamente
- **flush()**: Sincroniza sin commitear
- **is_active()**: Estado de la transacción

## Implementation Status

**Fase 1 (1 Nov 2025)**:
- ✅ **Base UnitOfWorkInterface**: Definición completa con async context manager
- ✅ **UserUnitOfWorkInterface**: Específica para módulo de usuarios  
- ✅ **Tests unitarios**: 18 tests verificando comportamiento de interfaces
- ✅ **Documentation**: Integración completa en Design Document

**Fase 2 (9 Nov 2025)** - Evolución hacia Clean Architecture:
- ✅ **SQLAlchemy Implementation**: Implementación concreta con PostgreSQL
- ✅ **Automatic Transaction Management**: Context manager maneja commit/rollback completamente
- ✅ **Domain Events Integration**: Publicación automática de eventos post-commit
- ✅ **Clean Architecture Compliance**: Use Cases no manejan aspectos técnicos
- ✅ **360 Tests Passing**: Validación completa del patrón evolucionado

## Performance Considerations
- **Connection pooling**: Una conexión por UoW
- **Lazy loading**: Repositorios se crean bajo demanda
- **Resource cleanup**: Gestión automática de limpieza
- **Transaction scope**: Delimitación clara de límites transaccionales

## Related ADRs
- **ADR-001**: Clean Architecture - Framework arquitectónico base
- **ADR-005**: Repository Pattern - Complementa con abstracción de datos
- **ADR-003**: Testing Strategy - Define testing de transacciones

## Future Considerations
- **Distributed Transactions**: Para comunicación entre microservicios (futuro)
- **Event Sourcing**: Integración con eventos de dominio (futuro)
- **Saga Pattern**: Para transacciones de larga duración (futuro)

## Notes
Este patrón es fundamental para mantener la integridad de datos y proporcionar una base sólida para operaciones complejas de negocio. La implementación async permite escalabilidad en aplicaciones web modernas.