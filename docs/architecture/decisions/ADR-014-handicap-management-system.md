# ADR-014: Handicap Management System

**Estado**: ✅ Aceptado
**Fecha**: 9 Nov 2025

---

## Contexto

Necesitamos gestionar handicaps de golf para:
- Equidad competitiva entre jugadores
- Formación de equipos balanceados
- Cálculo de scores ajustados

**Requisitos**:
- Búsqueda automática desde RFEG
- Actualización batch (pre-torneo)
- Validación rango RFEG/EGA (-10.0 a 54.0)
- Auditoría completa de cambios

---

## Decisión

Implementar **Handicap como Value Object** + **Domain Events** + **External Service Pattern**.

### Componentes

**1. Handicap Value Object**
```python
@dataclass(frozen=True)
class Handicap:
    value: float

    def __post_init__(self):
        if not isinstance(self.value, (int, float)):
            raise TypeError(f"Debe ser número: {type(self.value)}")
        if not (-10.0 <= self.value <= 54.0):
            raise ValueError(f"Rango inválido: {self.value}")
```

**2. HandicapUpdatedEvent**
```python
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

**3. User.update_handicap()**
```python
def update_handicap(self, new_handicap: float?) -> None:
    old = self.handicap
    self.handicap = Handicap(new_handicap).value if new_handicap else None
    self.handicap_updated_at = datetime.now()

    if old != self.handicap:
        self._add_domain_event(HandicapUpdatedEvent(...))
```

**4. Use Cases**
- `UpdateUserHandicapUseCase`: RFEG lookup + fallback manual opcional
- `UpdateUserHandicapManuallyUseCase`: Actualización directa sin RFEG
- `UpdateMultipleHandicapsUseCase`: Batch con estadísticas detalladas

**5. External Service**
```python
# Domain
class HandicapService(ABC):
    @abstractmethod
    async def search_handicap(self, full_name: str) -> float?

# Infrastructure
class RFEGHandicapService(HandicapService):
    # Web scraping RFEG

class MockHandicapService(HandicapService):
    # Para tests determinísticos
```

**6. API Endpoints**
- `POST /api/v1/handicaps/update` - RFEG + fallback opcional
- `POST /api/v1/handicaps/update-manual` - Manual directo
- `POST /api/v1/handicaps/update-multiple` - Batch con stats

---

## Alternativas Rechazadas

**1. Handicap como float primitivo**
- ❌ Sin validación automática
- ❌ Permite valores inválidos (999.9, -100.0)
- ❌ No encapsula reglas de negocio

**2. Servicio en Application Layer**
- ❌ Viola Dependency Inversion
- ❌ No es concepto de dominio

**3. Actualización sincronía en registro**
- ❌ Bloquea registro si RFEG falla
- ❌ Mala UX

---

## Consecuencias

### Positivas
✅ **Type-safe**: Imposible crear `Handicap(999)`
✅ **Auditoría**: Eventos de todos los cambios
✅ **Testeable**: MockHandicapService para tests
✅ **Extensible**: Fácil agregar EGA, USGA
✅ **No bloqueante**: Errores RFEG no afectan flujo principal

### Negativas
⚠️ **Complejidad**: Más archivos que float simple
⚠️ **Overhead**: Value Object por cada handicap

**Mitigación**: La inversión paga en mantenibilidad y calidad.

---

## Implementación

### Archivos
```
user/domain/value_objects/handicap.py
user/domain/events/handicap_updated_event.py
user/domain/services/handicap_service.py
user/application/use_cases/update_*_handicap*.py
user/infrastructure/external/rfeg_handicap_service.py
user/infrastructure/api/v1/handicap_routes.py
```

### Tests
- 20 tests Handicap VO
- 16 tests HandicapUpdatedEvent
- 18 tests External Services
- 7 tests Use Cases
- 18 tests Integration
**Total: 79 tests nuevos**

---

## Puntos de Actualización

**1. Registro Usuario** (Opcional, no bloqueante)
```python
# Intentar buscar handicap en background
# No bloquea si falla
```

**2. Pre-Torneo** (Crítico)
```python
# Batch update de todos los participantes
await update_multiple_handicaps_use_case.execute(participant_ids)
```

**3. Admin Manual** (Fallback)
```python
# Actualización manual para jugadores no federados
await update_user_handicap_manually_use_case.execute(user_id, 15.5)
```

---

## Métricas

| Métrica | Antes | Después |
|---------|-------|---------|
| Tests | 299 | 330 |
| Tests handicap | 0 | 79 |
| Cobertura handicap | 0% | 100% |

---

## Referencias

- [ADR-002: Value Objects](./ADR-002-value-objects.md)
- [ADR-007: Domain Events](./ADR-007-domain-events-pattern.md)
- [ADR-013: External Services](./ADR-013-external-services-pattern.md)
- [RFEG Handicaps](https://www.rfegolf.es/Handicaps.aspx)
