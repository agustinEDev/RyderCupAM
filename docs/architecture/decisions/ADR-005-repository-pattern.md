# ADR-005: Repository Pattern Implementation

## Status
**ACCEPTED** - 1 Noviembre 2025

## Context
Tras implementar la capa de dominio con Clean Architecture, necesitamos definir contratos claros para la persistencia de datos. El patrón Repository nos permite abstraer el acceso a datos y mantener la independencia de la lógica de negocio respecto a las tecnologías de persistencia específicas.

### Problemas Identificados
1. **Acoplamiento directo**: Los casos de uso no deben depender de implementaciones concretas de bases de datos
2. **Testabilidad**: Necesitamos poder mockear fácilmente el acceso a datos en tests unitarios
3. **Flexibilidad**: El sistema debe permitir cambios de base de datos sin afectar la lógica de negocio
4. **Principio de Inversión de Dependencias**: Las capas superiores deben depender de abstracciones, no de implementaciones

### Alternativas Consideradas
1. **Active Record**: Lógica de persistencia en las entidades
   - ❌ Viola Single Responsibility Principle
   - ❌ Acopla entidades con tecnología de BD

2. **Data Mapper directo**: Usar ORM directamente en casos de uso
   - ❌ Viola Dependency Inversion Principle
   - ❌ Dificulta testing unitario

3. **Repository Pattern**: Interfaces de repositorio con implementaciones concretas
   - ✅ Desacoplamiento total
   - ✅ Fácil testing con mocks
   - ✅ Cumple principios SOLID

## Decision
Implementaremos el **patrón Repository** con interfaces en la capa de dominio e implementaciones en la capa de infraestructura.

### Estructura de Interfaces
```python
# Domain Layer - Interfaces
@abstractmethod
class UserRepositoryInterface(ABC):
    async def save(self, user: User) -> None: ...
    async def find_by_id(self, user_id: UserId) -> Optional[User]: ...
    async def find_by_email(self, email: Email) -> Optional[User]: ...
    async def delete(self, user: User) -> None: ...
    async def list_all(self) -> List[User]: ...
    async def exists_by_email(self, email: Email) -> bool: ...
    async def count(self) -> int: ...
    async def update(self, user: User) -> None: ...
```

### Principios Aplicados
1. **Métodos async**: Soporte nativo para operaciones asíncronas
2. **Type Safety**: Type hints completos para mejor desarrollo
3. **Domain Objects**: Parámetros y retornos usan objetos de dominio
4. **Single Responsibility**: Cada método tiene una responsabilidad específica

## Consequences

### Beneficios
- ✅ **Testabilidad mejorada**: Mocks simples con interfaces claras
- ✅ **Desacoplamiento**: Lógica de negocio independiente de tecnología de BD
- ✅ **Flexibilidad**: Cambio de base de datos sin afectar casos de uso
- ✅ **Principios SOLID**: Cumplimiento completo de Dependency Inversion
- ✅ **Consistencia**: API uniforme para todas las operaciones de persistencia

### Desafíos
- ⚠️ **Complejidad inicial**: Más código boilerplate
- ⚠️ **Curva de aprendizaje**: Requiere entendimiento de Clean Architecture
- ⚠️ **Múltiples archivos**: Separación entre interfaces e implementaciones

### Impacto en el Proyecto
- **Testing**: 31 tests específicos para interfaces de repositorio
- **Arquitectura**: Separación clara entre capas
- **Desarrollo futuro**: Base sólida para implementaciones con diferentes tecnologías

## Implementation Status
- ✅ **UserRepositoryInterface**: 8 métodos async completamente definidos
- ✅ **Tests unitarios**: 31 tests verificando contratos de interfaces
- ✅ **Documentation**: Documentación completa en Design Document
- ⏳ **Implementaciones concretas**: Pendiente para fase de Infrastructure

## Related ADRs
- **ADR-001**: Clean Architecture - Establece la base arquitectónica
- **ADR-006**: Unit of Work Pattern - Complementa con gestión transaccional
- **ADR-003**: Testing Strategy - Define como testear las interfaces

## Notes
Esta decisión establece la base para la implementación de la capa de infraestructura y garantiza que el proyecto mantenga los principios de Clean Architecture a medida que crezca.