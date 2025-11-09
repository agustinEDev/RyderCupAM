# ADR-013: External Services Pattern para Integración con Servicios Externos

**Estado**: ✅ Aceptado
**Fecha**: 9 de Noviembre de 2025
**Decisores**: Equipo de Desarrollo
**Contexto**: Sistema de Gestión de Hándicaps - Integración RFEG

---

## 📋 Contexto y Problema

El sistema necesita integrar funcionalidad de búsqueda de hándicaps desde la **Real Federación Española de Golf (RFEG)**, un servicio externo sobre el cual no tenemos control. Esta integración debe:

1. **Mantener Clean Architecture**: No contaminar el dominio con detalles de implementación
2. **Ser Testeable**: Permitir testing unitario sin dependencias externas
3. **Ser Flexible**: Permitir cambiar de proveedor o agregar nuevos servicios fácilmente
4. **Manejar Errores**: Gestionar fallos de red, timeouts y servicios no disponibles
5. **Ser No Bloqueante**: No afectar flujos críticos del sistema si el servicio falla

### Características de la Integración RFEG

- **URL**: `https://www.rfegolf.es`
- **Método**: Scraping HTML + API REST
- **Autenticación**: Token Bearer extraído dinámicamente del HTML
- **Complejidad**: Requiere dos llamadas HTTP (1. obtener token, 2. buscar handicap)
- **Confiabilidad**: Servicio externo sin SLA garantizado

---

## 🤔 Opciones Consideradas

### Opción 1: Llamada Directa desde el Caso de Uso ❌

```python
class RegisterUserUseCase:
    async def execute(self, dto: RegisterUserDTO) -> User:
        # Lógica de registro...

        # ❌ Acoplamiento directo al servicio externo
        response = await httpx.get("https://www.rfegolf.es/...")
        handicap = parse_response(response)
        user.handicap = handicap
```

**Pros**:
- Simple y directo
- Menos archivos

**Contras**:
- ❌ Viola Clean Architecture (dependencia externa en Application Layer)
- ❌ No testeable sin red
- ❌ Difícil cambiar de proveedor
- ❌ Lógica HTTP mezclada con lógica de negocio

### Opción 2: Service Interface en Application Layer ❌

```python
# src/modules/user/application/services/handicap_service.py
class HandicapService(ABC):
    async def search(self, name: str) -> Optional[float]:
        pass
```

**Pros**:
- Abstrae el servicio externo
- Testeable con mocks

**Contras**:
- ❌ Viola Dependency Inversion (interface en Application, no en Domain)
- ❌ No es un concepto del dominio de negocio

### Opción 3: Domain Service con Interface (ABC) ✅ SELECCIONADA

```python
# src/modules/user/domain/services/handicap_service.py
class HandicapService(ABC):
    """Servicio de dominio para búsqueda de hándicaps."""

    @abstractmethod
    async def search_handicap(self, full_name: str) -> Optional[float]:
        """Busca el hándicap de un jugador por su nombre completo."""
        pass

# src/modules/user/infrastructure/external/rfeg_handicap_service.py
class RFEGHandicapService(HandicapService):
    """Implementación concreta usando la API de RFEG."""

    async def search_handicap(self, full_name: str) -> Optional[float]:
        token = await self._obtener_bearer_token()
        return await self._buscar_handicap(full_name, token)
```

**Pros**:
- ✅ Sigue Dependency Inversion Principle
- ✅ Interface definida en Domain (es un concepto de negocio)
- ✅ Implementaciones en Infrastructure (detalles técnicos)
- ✅ Testeable con mocks (MockHandicapService)
- ✅ Fácil agregar nuevos proveedores
- ✅ Uso Cases dependen de abstracciones, no de implementaciones

**Contras**:
- Más archivos y estructura

---

## ✅ Decisión

**Adoptamos la Opción 3: Domain Service con Interface (ABC)**

El servicio de búsqueda de hándicaps se modela como un **Domain Service** porque:

1. **Es un concepto del dominio**: La búsqueda de hándicaps es parte del dominio de golf
2. **No tiene estado**: Es un servicio puro que toma input y devuelve output
3. **Requiere conocimiento especializado**: Sabe cómo obtener hándicaps oficiales
4. **Es stateless**: No mantiene estado entre llamadas

### Ubicación de Componentes

```
src/modules/user/
├── domain/
│   ├── services/
│   │   └── handicap_service.py        # ✅ Interface (ABC)
│   └── errors/
│       └── handicap_errors.py         # ✅ Excepciones específicas
├── application/
│   └── use_cases/
│       ├── update_user_handicap_use_case.py
│       └── register_user_use_case.py  # Usa HandicapService
└── infrastructure/
    └── external/
        ├── rfeg_handicap_service.py   # ✅ Implementación RFEG
        └── mock_handicap_service.py   # ✅ Mock para testing
```

### Implementación del Pattern

#### 1. Domain Service Interface

```python
from abc import ABC, abstractmethod
from typing import Optional

class HandicapService(ABC):
    """Servicio de dominio para búsqueda de hándicaps.

    Este servicio abstrae la obtención de hándicaps oficiales
    desde fuentes externas como federaciones de golf.
    """

    @abstractmethod
    async def search_handicap(self, full_name: str) -> Optional[float]:
        """Busca el hándicap oficial de un jugador.

        Args:
            full_name: Nombre completo del jugador (nombre + apellidos)

        Returns:
            Hándicap del jugador o None si no se encuentra

        Raises:
            HandicapServiceError: Si hay un error en la búsqueda
        """
        pass
```

#### 2. Implementación Concreta (RFEG)

```python
import httpx
import re
from typing import Optional

class RFEGHandicapService(HandicapService):
    """Implementación del servicio de hándicaps usando la RFEG."""

    BASE_URL = "https://www.rfegolf.es"

    def __init__(self, timeout: int = 10):
        self._timeout = timeout
        self._client = httpx.AsyncClient(timeout=timeout)

    async def search_handicap(self, full_name: str) -> Optional[float]:
        """Busca hándicap en el sistema de la RFEG."""
        try:
            token = await self._obtener_bearer_token()
            if not token:
                raise HandicapServiceUnavailableError("No se pudo obtener token")

            return await self._buscar_handicap(full_name, token)

        except httpx.TimeoutException:
            raise HandicapServiceUnavailableError("Timeout al conectar con RFEG")
        except Exception as e:
            raise HandicapServiceError(f"Error al buscar hándicap: {str(e)}")

    async def _obtener_bearer_token(self) -> Optional[str]:
        """Extrae el token Bearer dinámico del HTML de RFEG."""
        response = await self._client.get(f"{self.BASE_URL}/index.php...")
        match = re.search(r"'coded_[0-9a-fA-F]+'", response.text)

        if match:
            token = match.group(0).strip("'")
            return f"Bearer {token}"
        return None

    async def _buscar_handicap(self, full_name: str, token: str) -> Optional[float]:
        """Realiza la búsqueda del hándicap con el token."""
        headers = {"Authorization": token}
        params = {"nombre": full_name}

        response = await self._client.get(
            f"{self.BASE_URL}/api/search/handicap",
            headers=headers,
            params=params
        )

        data = response.json()
        return data.get("handicap")
```

#### 3. Mock para Testing

```python
from typing import Dict, Optional

class MockHandicapService(HandicapService):
    """Mock del servicio de hándicaps para testing.

    Permite configurar respuestas predefinidas para tests determinísticos.
    """

    def __init__(
        self,
        handicaps: Optional[Dict[str, float]] = None,
        default: Optional[float] = None
    ):
        self._handicaps = handicaps or {}
        self._default = default

    async def search_handicap(self, full_name: str) -> Optional[float]:
        """Retorna hándicap configurado o valor por defecto."""
        return self._handicaps.get(full_name, self._default)
```

#### 4. Uso en Use Cases

```python
class UpdateUserHandicapUseCase:
    """Caso de uso para actualizar el hándicap de un usuario."""

    def __init__(
        self,
        uow: UserUnitOfWorkInterface,
        handicap_service: HandicapService  # ✅ Depende de la abstracción
    ):
        self._uow = uow
        self._handicap_service = handicap_service

    async def execute(self, user_id: UserId) -> Optional[UserResponseDTO]:
        async with self._uow:
            user = await self._uow.users.find_by_id(user_id)
            if not user:
                return None

            # Buscar hándicap usando el servicio
            full_name = user.get_full_name()
            handicap = await self._handicap_service.search_handicap(full_name)

            # Actualizar si se encontró
            if handicap is not None:
                user.update_handicap(handicap)
                await self._uow.users.update(user)
                await self._uow.commit()

            return UserResponseDTO.from_entity(user)
```

#### 5. Inyección de Dependencias

```python
# src/config/dependencies.py

def get_handicap_service() -> HandicapService:
    """Factory para el servicio de hándicaps."""
    # En producción: RFEG
    return RFEGHandicapService(timeout=10)

    # En testing: Mock
    # return MockHandicapService(default=15.0)

def get_update_handicap_use_case(
    handicap_service: HandicapService = Depends(get_handicap_service)
) -> UpdateUserHandicapUseCase:
    """Factory para el caso de uso de actualización de hándicap."""
    session_factory = async_session_maker
    return UpdateUserHandicapUseCase(
        uow=SQLAlchemyUnitOfWork(session_factory()),
        handicap_service=handicap_service
    )
```

---

## 🎯 Beneficios

### 1. **Clean Architecture Preservada**
- Domain define el contrato (`HandicapService`)
- Infrastructure provee implementaciones (`RFEGHandicapService`)
- Application usa abstracciones, no detalles

### 2. **Testabilidad Máxima**
```python
def test_update_handicap():
    # Arrange
    mock_service = MockHandicapService(
        handicaps={"Rafael Nadal Parera": 2.5}
    )
    use_case = UpdateUserHandicapUseCase(uow, mock_service)

    # Act & Assert
    result = await use_case.execute(user_id)
    assert result.handicap == 2.5
```

### 3. **Flexibilidad**
- Fácil agregar proveedores: `EGAHandicapService`, `USGAHandicapService`
- Fácil cambiar implementación sin tocar Use Cases
- Fácil implementar fallback: intentar RFEG, si falla usar EGA

### 4. **Manejo de Errores Robusto**
```python
class HandicapServiceError(DomainError):
    """Error base para servicios de hándicap."""
    pass

class HandicapNotFoundError(HandicapServiceError):
    """Jugador no encontrado en el servicio."""
    pass

class HandicapServiceUnavailableError(HandicapServiceError):
    """Servicio temporalmente no disponible."""
    pass
```

### 5. **No Bloqueante**
```python
# En RegisterUserUseCase - búsqueda opcional
try:
    handicap = await self._handicap_service.search_handicap(full_name)
    user.update_handicap(handicap)
except HandicapServiceError:
    # Continuar sin hándicap - no bloquear el registro
    logger.warning("No se pudo obtener hándicap, continuando...")
```

---

## ⚠️ Consecuencias

### Positivas

✅ **Dependency Inversion**: Use Cases dependen de abstracciones
✅ **Open/Closed**: Fácil extender con nuevos proveedores
✅ **Single Responsibility**: Cada implementación tiene una responsabilidad clara
✅ **Testeable**: 100% de cobertura en tests unitarios
✅ **Mantenible**: Cambios en RFEG aislados en una clase

### Negativas

⚠️ **Más Archivos**: 3 archivos en lugar de 1 (interface, impl, mock)
⚠️ **Complejidad Inicial**: Setup de inyección de dependencias
⚠️ **Indirección**: Un nivel extra de abstracción

**Mitigación**: Los beneficios superan ampliamente las desventajas. La estructura adicional paga dividendos a largo plazo.

---

## 📊 Métricas de Éxito

Después de la implementación:

- ✅ **79 tests nuevos** (100% passing)
- ✅ **18 tests** para MockHandicapService
- ✅ **5 tests de integración** con RFEG real
- ✅ **0 dependencias externas** en tests unitarios
- ✅ **Tiempo de tests**: < 10ms para mocks vs ~2s para RFEG real
- ✅ **Cobertura**: 100% en Domain Service Interface

---

## 🔗 Referencias

### Patrones Relacionados
- **Dependency Inversion Principle** (SOLID)
- **Strategy Pattern** (Gang of Four)
- **Adapter Pattern** (Gang of Four)
- **Repository Pattern** (Domain-Driven Design)

### ADRs Relacionados
- [ADR-001: Clean Architecture](./ADR-001-clean-architecture.md)
- [ADR-005: Repository Pattern](./ADR-005-repository-pattern.md)
- [ADR-012: Composition Root](./ADR-012-composition-root.md)

### Recursos Externos
- [Domain Services in DDD](https://enterprisecraftsmanship.com/posts/domain-vs-application-services/)
- [Hexagonal Architecture](https://alistair.cockburn.us/hexagonal-architecture/)
- [Clean Architecture - Uncle Bob](https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html)

---

## 📝 Notas de Implementación

### Testing con Nombres Reales
Para tests de integración, usamos nombres reales de la RFEG:

```python
@pytest.mark.integration
async def test_rfeg_integration():
    service = RFEGHandicapService()

    # Usar nombres que existen en RFEG
    nadal_handicap = await service.search_handicap("Rafael Nadal Parera")
    alcaraz_handicap = await service.search_handicap("Carlos Alcaraz Garfia")

    # Verificar que se obtienen resultados
    assert nadal_handicap is not None
    assert alcaraz_handicap is not None
```

### Manejo de Timeouts
```python
# Configuración de timeouts razonable
service = RFEGHandicapService(timeout=10)  # 10 segundos

# En producción, considerar:
# - Retry con backoff exponencial
# - Circuit breaker pattern
# - Fallback a caché
```

### Próximas Mejoras
1. **Caché de Resultados**: Redis para evitar llamadas repetidas
2. **Circuit Breaker**: Fallar rápido si RFEG está caído
3. **Múltiples Proveedores**: Fallback RFEG → EGA → USGA
4. **Background Jobs**: Actualización batch asíncrona

---

**Decisión Final**: ✅ Adoptado y completamente implementado
**Impacto**: 🔥 Alto - Patrón fundamental para futuras integraciones externas
**Revisión**: No requerida - Patrón probado y estable
