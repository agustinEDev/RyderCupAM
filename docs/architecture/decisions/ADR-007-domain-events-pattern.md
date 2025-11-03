# ADR-007: Domain Events Pattern for Event-Driven Architecture

## Status
**ACCEPTED** - 1 Noviembre 2025

## Context
Con el Domain Layer, Repository Pattern y Unit of Work implementados, necesitamos una forma de manejar efectos secundarios y comunicación entre módulos sin acoplar directamente los casos de uso. El sistema Ryder Cup es naturalmente event-driven: registros de usuarios, creación de torneos, finalización de partidos, etc., generan múltiples acciones que deben ejecutarse de forma desacoplada.

### Problemas Identificados
1. **Use Cases acoplados**: Los casos de uso deben manejar lógica de negocio principal + efectos secundarios
2. **Violación SRP**: Un caso de uso hace múltiples cosas (crear usuario + enviar email + auditoría)
3. **Dificultad de testing**: Tests complejos con múltiples mocks
4. **Extensibilidad limitada**: Agregar nueva funcionalidad requiere modificar código existente
5. **Falta de auditoría**: No hay trazabilidad clara de eventos de negocio

### Casos de Uso del Sistema Ryder Cup
```python
# Ejemplos reales de eventos en nuestro dominio:
UserRegisteredEvent      → Email bienvenida, auditoría, métricas
UserLoggedInEvent        → Actualizar última conexión, detectar login sospechoso
TournamentCreatedEvent   → Enviar invitaciones, notificar administradores
PlayerJoinedTournamentEvent → Actualizar equipos, recalcular handicaps
MatchStartedEvent        → Notificar jugadores, activar scoring
MatchCompletedEvent      → Actualizar leaderboard, notificar resultados
TournamentFinishedEvent  → Generar reportes, actualizar estadísticas históricas
```

### Alternativas Consideradas
1. **Callbacks directos**: Pasar funciones a los casos de uso
   - ❌ Acoplamiento directo entre capas
   - ❌ Dificil testing y mantenimiento

2. **Observer Pattern tradicional**: Suscriptores directos en entidades
   - ❌ Viola principios de Clean Architecture
   - ❌ Domain Layer no debe conocer infraestructura

3. **Message Queues externos**: RabbitMQ, Redis
   - ❌ Complejidad innecesaria para monolito
   - ❌ Overhead de configuración y mantenimiento

4. **Domain Events Pattern**: Eventos en memoria con event bus
   - ✅ Desacoplamiento total
   - ✅ Mantiene principios de Clean Architecture
   - ✅ Fácil testing y extensibilidad

## Decision
Implementaremos el **Domain Events Pattern** con las siguientes características:

### Arquitectura de Eventos

#### 1. Domain Events (Domain Layer)
```python
from abc import ABC
from dataclasses import dataclass, field
from datetime import datetime
import uuid

@dataclass(frozen=True)
class DomainEvent(ABC):
    """Evento de dominio base."""
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    occurred_on: datetime = field(default_factory=datetime.now)
    aggregate_id: str
    event_version: int = 1

@dataclass(frozen=True)
class UserRegisteredEvent(DomainEvent):
    """Usuario registrado exitosamente."""
    user_id: str
    email: str
    full_name: str
    registration_source: str = "web"

@dataclass(frozen=True)
class UserLoggedInEvent(DomainEvent):
    """Usuario autenticado exitosamente."""
    user_id: str
    login_time: datetime
    ip_address: str | None = None
    user_agent: str | None = None
```

#### 2. Event Collection en Entidades
```python
# En User entity
class User:
    def __init__(self, ...):
        # ... existing code ...
        self._domain_events: List[DomainEvent] = []
    
    @classmethod
    def create(cls, ...) -> 'User':
        user = cls(...)
        user.add_domain_event(UserRegisteredEvent(
            aggregate_id=str(user.id),
            user_id=str(user.id),
            email=str(user.email),
            full_name=user.get_full_name()
        ))
        return user
    
    def add_domain_event(self, event: DomainEvent) -> None:
        """Añade evento de dominio para publicar después del commit."""
        self._domain_events.append(event)
    
    @property
    def domain_events(self) -> List[DomainEvent]:
        """Eventos pendientes de publicar."""
        return self._domain_events.copy()
    
    def clear_domain_events(self) -> None:
        """Limpia eventos después de publicarlos."""
        self._domain_events.clear()
```

#### 3. Event Bus Interface (Application Layer)
```python
from abc import ABC, abstractmethod
from typing import Type, Callable, List

class EventBus(ABC):
    """Interface para el bus de eventos."""
    
    @abstractmethod
    async def publish(self, event: DomainEvent) -> None:
        """Publica un evento a todos sus handlers."""
        pass
    
    @abstractmethod
    def subscribe(self, event_type: Type[DomainEvent], handler: 'EventHandler') -> None:
        """Suscribe un handler a un tipo de evento."""
        pass

class EventHandler(ABC):
    """Handler base para eventos de dominio."""
    
    @abstractmethod
    async def handle(self, event: DomainEvent) -> None:
        """Maneja un evento específico."""
        pass
```

#### 4. Integration con Unit of Work
```python
class UserUnitOfWorkInterface(UnitOfWorkInterface):
    @abstractmethod
    async def collect_events(self) -> List[DomainEvent]:
        """Recolecta eventos de todas las entidades modificadas."""
        pass
    
    @abstractmethod
    async def publish_events(self, event_bus: EventBus) -> None:
        """Publica eventos recolectados después del commit.""" 
        pass

# En el caso de uso:
class RegisterUserUseCase:
    def __init__(self, uow: UserUnitOfWorkInterface, event_bus: EventBus):
        self._uow = uow
        self._event_bus = event_bus
    
    async def execute(self, command: RegisterUserCommand) -> UserResponse:
        async with self._uow:
            # Lógica de negocio limpia
            if await self._uow.users.exists_by_email(email):
                raise EmailAlreadyExistsError()
            
            user = User.create(...)  # Genera UserRegisteredEvent automáticamente
            await self._uow.users.save(user)
            await self._uow.commit()
            
            # Publicar eventos después del commit exitoso
            await self._uow.publish_events(self._event_bus)
        
        return UserResponse(...)
```

#### 5. Event Handlers (Application Layer)
```python
class WelcomeEmailEventHandler(EventHandler):
    """Envía email de bienvenida cuando se registra un usuario."""
    
    def __init__(self, email_service: EmailService):
        self._email_service = email_service
    
    async def handle(self, event: UserRegisteredEvent) -> None:
        await self._email_service.send_welcome_email(
            email=event.email,
            full_name=event.full_name,
            user_id=event.user_id
        )

class UserAuditEventHandler(EventHandler):
    """Registra eventos de usuario para auditoría."""
    
    def __init__(self, audit_repository: AuditRepository):
        self._audit_repository = audit_repository
    
    async def handle(self, event: DomainEvent) -> None:
        audit_entry = AuditEntry.create(
            event_type=event.__class__.__name__,
            aggregate_id=event.aggregate_id,
            event_data=asdict(event),
            occurred_on=event.occurred_on
        )
        await self._audit_repository.save(audit_entry)
```

## Consequences

### Beneficios
- ✅ **Single Responsibility**: Use cases enfocados solo en lógica de negocio
- ✅ **Desacoplamiento**: Handlers independientes, fácil agregar/remover funcionalidad
- ✅ **Testabilidad**: Test aislados para use cases y handlers por separado
- ✅ **Extensibilidad**: Nueva funcionalidad = nuevo handler, sin modificar código existente
- ✅ **Auditoría**: Trazabilidad completa de eventos de negocio
- ✅ **Performance**: Eventos en memoria, sin overhead de red
- ✅ **Transaccionalidad**: Eventos se publican solo después de commit exitoso

### Desafíos
- ⚠️ **Complejidad inicial**: Más abstracciones y conceptos
- ⚠️ **Debugging**: Flujo de ejecución más indirecto
- ⚠️ **Error handling**: Manejo de fallos en handlers
- ⚠️ **Orden de ejecución**: Algunos handlers pueden tener dependencias

### Impacto en el Sistema
- **Arquitectura**: Nueva capa de comunicación asíncrona entre módulos
- **Testing**: Estrategia dual (use cases + handlers separados)
- **Performance**: Mejora por procesamiento asíncrono de efectos secundarios
- **Mantenimiento**: Código más modular y extensible

## Implementation Plan

### Fase 1: Domain Events Base
- ✅ **DomainEvent base class** en Domain Layer
- ✅ **Event collection** en entidades (User.add_domain_event)
- ✅ **Tests** para recolección de eventos

### Fase 2: Event Bus & Handlers
- 🔄 **EventBus interface** en Application Layer
- 🔄 **EventHandler base class** y handlers específicos
- 🔄 **Integration** con Unit of Work

### Fase 3: Infrastructure Implementation
- ⏳ **In-memory EventBus** implementation
- ⏳ **Handler registration** y dependency injection
- ⏳ **Error handling** y retry mechanisms

### Fase 4: Eventos de Negocio
- ⏳ **User events**: Registration, Login, Profile updates
- ⏳ **Tournament events**: Creation, Player joins, Match results
- ⏳ **Audit events**: Comprehensive business event logging

## Related ADRs
- **ADR-001**: Clean Architecture - Establece la base arquitectónica
- **ADR-005**: Repository Pattern - Complementa con abstracción de datos
- **ADR-006**: Unit of Work - Integración transaccional con eventos

## Future Considerations
- **Event Sourcing**: Para módulos críticos como scoring (futuro)
- **External Events**: Integración con webhooks para sistemas externos
- **Event Replay**: Capacidad de reejecutar eventos para testing/debugging
- **Event Store**: Persistencia de eventos para análisis histórico

## Notes
Este patrón es fundamental para un sistema de torneos donde múltiples acciones deben ocurrir en respuesta a eventos de negocio. La implementación en memoria es perfecta para el monolito actual, con posibilidad de evolucionar a message queues si se migra a microservicios en el futuro.

Los eventos también proporcionan una base sólida para futuras características como notificaciones en tiempo real, integración con sistemas de scoring externos, y análisis detallado del comportamiento de usuarios en torneos.