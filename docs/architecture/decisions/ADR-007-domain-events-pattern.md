# ADR-007: Domain Events Pattern

**Estado**: ✅ Aceptado
**Fecha**: 1 Nov 2025

---

## Contexto

Necesitamos manejar efectos secundarios y comunicación entre módulos sin acoplar use cases. El sistema Ryder Cup es event-driven por naturaleza: registros, actualizaciones de handicap, torneos, etc.

**Problemas**:
- Use cases acoplados (lógica principal + efectos secundarios)
- Violación SRP (un use case hace múltiples cosas)
- Tests complejos con múltiples mocks
- Difícil extender sin modificar código existente
- Falta de auditoría

**Eventos del Sistema**:
```python
UserRegisteredEvent         → Email bienvenida, auditoría
HandicapUpdatedEvent        → Auditoría, notificaciones
TournamentCreatedEvent      → Invitaciones
MatchCompletedEvent         → Leaderboard, resultados
```

---

## Decisión

**Domain Events Pattern** con event bus en memoria.

### Componentes

**1. DomainEvent Base**
```python
@dataclass(frozen=True)
class DomainEvent(ABC):
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    occurred_on: datetime = field(default_factory=datetime.now)
    aggregate_id: str
    event_version: int = 1
```

**2. Eventos Específicos**
```python
@dataclass(frozen=True)
class UserRegisteredEvent(DomainEvent):
    user_id: str
    email: str
    full_name: str

@dataclass(frozen=True)
class HandicapUpdatedEvent(DomainEvent):
    user_id: str
    old_handicap: float?
    new_handicap: float?
    updated_at: datetime

    @property
    def handicap_delta(self) -> float?:
        if self.old_handicap and self.new_handicap:
            return self.new_handicap - self.old_handicap
        return None
```

**3. Event Collection en Entidades**
```python
class User:
    def __init__(self, ...):
        self._domain_events: List[DomainEvent] = []

    @classmethod
    def create(cls, ...) -> 'User':
        user = cls(...)
        user._add_domain_event(UserRegisteredEvent(...))
        return user

    def update_handicap(self, new_handicap: float?) -> None:
        old = self.handicap
        # ... actualizar ...
        if old != self.handicap:
            self._add_domain_event(HandicapUpdatedEvent(...))
```

**4. Event Bus + Handlers**
```python
class EventBus(ABC):
    @abstractmethod
    async def publish(self, event: DomainEvent) -> None:
        pass

    @abstractmethod
    def subscribe(self, event_type: Type, handler: EventHandler) -> None:
        pass

class EventHandler(ABC):
    @abstractmethod
    async def handle(self, event: DomainEvent) -> None:
        pass
```

**5. Integración con Unit of Work**
```python
class RegisterUserUseCase:
    async def execute(self, command: RegisterUserCommand):
        async with self._uow:
            user = User.create(...)  # Genera UserRegisteredEvent
            await self._uow.users.save(user)
            await self._uow.commit()

            # Publicar eventos después del commit exitoso
            await self._uow.publish_events(self._event_bus)

        return UserResponse(...)
```

---

## Alternativas Rechazadas

**1. Callbacks directos**
- ❌ Acoplamiento entre capas
- ❌ Difícil testing

**2. Observer Pattern tradicional**
- ❌ Viola Clean Architecture
- ❌ Domain conoce infraestructura

**3. Message Queues (RabbitMQ, Redis)**
- ❌ Complejidad innecesaria para monolito
- ❌ Overhead configuración

---

## Consecuencias

### Positivas
✅ **Single Responsibility**: Use cases enfocados en lógica de negocio
✅ **Desacoplamiento**: Handlers independientes
✅ **Testabilidad**: Tests aislados
✅ **Extensibilidad**: Nuevo handler = nueva funcionalidad
✅ **Auditoría**: Trazabilidad completa
✅ **Performance**: Eventos en memoria, sin red
✅ **Transaccionalidad**: Eventos solo después de commit

### Negativas
⚠️ **Complejidad**: Más abstracciones
⚠️ **Debugging**: Flujo indirecto
⚠️ **Error handling**: Manejo de fallos en handlers

---

## Implementación

### Componentes
- `DomainEvent` base class (Domain Layer)
- `EventHandler` interface (Application Layer)
- `EventBus` interface + `InMemoryEventBus` (Shared)
- Eventos específicos de dominio (ej: `UserRegisteredEvent`, `HandicapUpdatedEvent`)
- Handlers específicos (Application)

---

## Referencias

- [ADR-001: Clean Architecture](./ADR-001-clean-architecture.md)
- [ADR-002: Value Objects](./ADR-002-value-objects.md)
- [ADR-005: Repository Pattern](./ADR-005-repository-pattern.md)
- [ADR-006: Unit of Work](./ADR-006-unit-of-work-pattern.md)
- [ADR-008: Logging System](./ADR-008-logging-system.md)
- [ADR-014: Handicap System](./ADR-014-handicap-management-system.md)
- [Design Document](../design-document.md) - Ver sección Métricas para eventos implementados
