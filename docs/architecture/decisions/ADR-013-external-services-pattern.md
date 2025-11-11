# ADR-013: External Services Pattern

**Estado**: ✅ Aceptado
**Fecha**: 9 Nov 2025

---

## Contexto

Necesitamos integrar la **Real Federación Española de Golf (RFEG)** para obtener handicaps oficiales. El servicio es externo, sin control sobre su disponibilidad.

**Requisitos**:
- Mantener Clean Architecture (no contaminar domain)
- Testeable sin dependencias externas
- Flexible para cambiar/agregar proveedores
- Manejo robusto de errores
- No bloqueante si falla

**Características RFEG**:
- URL: `https://www.rfegolf.es`
- Método: Web scraping (no hay API pública)
- Auth: Bearer token extraído del HTML
- Complejidad: 2 llamadas HTTP (token + búsqueda)
- Confiabilidad: Sin SLA garantizado

---

## Decisión

**Domain Service con Interface** (Domain) + **Implementaciones Concretas** (Infrastructure).

### Implementación

**1. Interface en Domain**
```python
# src/modules/user/domain/services/handicap_service.py
class HandicapService(ABC):
    @abstractmethod
    async def search_handicap(self, full_name: str) -> float?:
        """Busca handicap oficial de un jugador."""
        pass
```

**2. Implementación Real (Infrastructure)**
```python
# src/modules/user/infrastructure/external/rfeg_handicap_service.py
class RFEGHandicapService(HandicapService):
    BASE_URL = "https://www.rfegolf.es"

    async def search_handicap(self, full_name: str) -> float?:
        try:
            token = await self._obtener_bearer_token()
            return await self._buscar_handicap(full_name, token)
        except httpx.TimeoutException:
            raise HandicapServiceUnavailableError("Timeout RFEG")
        except Exception as e:
            raise HandicapServiceError(f"Error: {e}")
```

**3. Mock para Tests**
```python
# src/modules/user/infrastructure/external/mock_handicap_service.py
class MockHandicapService(HandicapService):
    def __init__(self, handicaps: dict = None):
        self._handicaps = handicaps or {}

    async def search_handicap(self, full_name: str) -> float?:
        return self._handicaps.get(full_name)
```

**4. Uso en Use Cases**
```python
class UpdateUserHandicapUseCase:
    def __init__(
        self,
        uow: UserUnitOfWorkInterface,
        handicap_service: HandicapService  # ← Depende de abstracción
    ):
        self._uow = uow
        self._handicap_service = handicap_service

    async def execute(self, user_id: UserId) -> UserResponseDTO?:
        user = await self._uow.users.find_by_id(user_id)
        if not user:
            return None

        full_name = user.get_full_name()
        handicap = await self._handicap_service.search_handicap(full_name)

        if handicap is not None:
            user.update_handicap(handicap)
            await self._uow.users.update(user)
            await self._uow.commit()

        return UserResponseDTO.from_entity(user)
```

**5. Dependency Injection**
```python
# src/config/dependencies.py
def get_handicap_service() -> HandicapService:
    # Producción: RFEG
    return RFEGHandicapService(timeout=10)

    # Tests: Mock
    # return MockHandicapService()
```

---

## Alternativas Rechazadas

**1. Llamada Directa en Use Case**
- ❌ Acopla use case a implementación
- ❌ No testeable sin red
- ❌ Difícil cambiar proveedor

**2. Interface en Application Layer**
- ❌ Viola Dependency Inversion
- ❌ No es concepto de dominio

**3. Message Queue (RabbitMQ)**
- ❌ Complejidad innecesaria para monolito
- ❌ Overhead de configuración

---

## Consecuencias

### Positivas
✅ **Dependency Inversion**: Use Cases dependen de abstracción
✅ **Open/Closed**: Fácil extender con nuevos proveedores
✅ **Testeable**: 100% cobertura con mocks
✅ **Flexible**: Cambiar implementación sin tocar use cases
✅ **Mantenible**: Cambios RFEG aislados en una clase

### Negativas
⚠️ **Más Archivos**: Interface + impl + mock
⚠️ **Indirección**: Nivel extra de abstracción

**Mitigación**: Beneficios superan complejidad adicional.

---

## Beneficios

### 1. Clean Architecture
- Domain define contrato (`HandicapService`)
- Infrastructure provee implementaciones (`RFEGHandicapService`)
- Application usa abstracciones

### 2. Testabilidad Máxima
```python
def test_update_handicap():
    mock = MockHandicapService({"Rafael Nadal Parera": 2.5})
    use_case = UpdateUserHandicapUseCase(uow, mock)

    result = await use_case.execute(user_id)
    assert result.handicap == 2.5
```

### 3. Extensibilidad
- Fácil agregar: `EGAHandicapService`, `USGAHandicapService`
- Fácil fallback: Intentar RFEG → EGA → USGA
- Fácil cambiar sin tocar use cases

### 4. Manejo de Errores
```python
try:
    handicap = await self._handicap_service.search_handicap(full_name)
    user.update_handicap(handicap)
except HandicapServiceError:
    # Continuar sin bloquear flujo
    logger.warning("No se pudo obtener handicap")
```

---

## Referencias

- **Patrones**: Dependency Inversion (SOLID), Strategy Pattern, Adapter Pattern
- [ADR-001: Clean Architecture](./ADR-001-clean-architecture.md)
- [ADR-005: Repository Pattern](./ADR-005-repository-pattern.md)
- [ADR-012: Composition Root](./ADR-012-composition-root.md)
- [ADR-014: Handicap System](./ADR-014-handicap-management-system.md)
- [Design Document](../design-document.md) - Ver sección Métricas para servicios externos implementados
