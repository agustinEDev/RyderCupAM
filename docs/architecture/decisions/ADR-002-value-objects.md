# ADR-002: Implementación de Value Objects

**Fecha**: 31 de octubre de 2025  
**Estado**: Aceptado  
**Decisores**: Equipo de desarrollo  

## Contexto y Problema

En el diseño de la entidad User, necesitamos decidir cómo representar conceptos de dominio como identificadores, emails y passwords. Las opciones son usar tipos primitivos (string, int) o crear Value Objects específicos.

### Problemática con Tipos Primitivos:
```python
# Problemático: tipos primitivos sin validación
class User:
    def __init__(self, id: str, email: str, password: str):
        self.id = id          # ¿UUID válido?
        self.email = email    # ¿Formato correcto?
        self.password = password  # ¿Hasheado? ¿Fuerte?
```

## Opciones Consideradas

1. **Tipos Primitivos Simples**: string, int para todos los campos
2. **Validación en Constructor**: Validar en el constructor de la entidad
3. **Value Objects**: Objetos inmutables con validación encapsulada
4. **Mixto**: Value Objects solo para casos complejos

## Decisión

**Implementamos Value Objects** para conceptos de dominio importantes:

- **UserId**: Identificador único basado en UUID
- **Email**: Dirección de email validada y normalizada
- **Password**: Contraseña hasheada con bcrypt
- **Handicap**: Hándicap de golf con validación de rango RFEG/EGA (-10.0 a 54.0)

### Ejemplo de Implementación:

```python
@dataclass(frozen=True)
class Email:
    value: str
    
    def __post_init__(self):
        normalized = self._normalize_email(self.value)
        if not self._is_valid_email(normalized):
            raise InvalidEmailError(f"'{self.value}' no es un email válido")
        object.__setattr__(self, 'value', normalized)
```

## Justificación

### Ventajas de Value Objects:

1. **Encapsulación de Validación**
   - Validación automática en construcción
   - Imposible crear objetos inválidos
   - Reglas de negocio centralizadas

2. **Inmutabilidad**
   - `@dataclass(frozen=True)` previene mutaciones
   - Thread-safe por diseño
   - Previene bugs por modificación accidental

3. **Expresividad del Código**
   ```python
   # Claro y expresivo
   def change_email(self, new_email: Email) -> None:
   
   # vs ambiguo
   def change_email(self, new_email: str) -> None:
   ```

4. **Reutilización**
   - Email puede usarse en User, Team, etc.
   - Validación consistente en toda la aplicación
   - DRY (Don't Repeat Yourself)

5. **Testabilidad**
   - Fácil testear validaciones específicas
   - Tests unitarios granulares por concepto
   - 49 tests específicos para Value Objects

### Casos de Uso Específicos:

#### UserId (UUID v4):
- **Problema**: IDs secuenciales predecibles
- **Solución**: UUID único, validación automática
- **Beneficio**: Seguridad y unicidad garantizada

#### Email:
- **Problema**: Formatos inconsistentes, validación dispersa  
- **Solución**: Normalización (lowercase, trim) + regex avanzada
- **Beneficio**: Emails consistentes en toda la aplicación

#### Password:
- **Problema**: Contraseñas en texto plano, validación débil
- **Solución**: bcrypt automático + validación de fortaleza
- **Beneficio**: Seguridad por defecto, imposible almacenar sin hash

#### Handicap:
- **Problema**: Valores de hándicap inválidos (ej: 999.0, -100.0), sin validación consistente
- **Solución**: Validación automática de rango según reglas RFEG/EGA (-10.0 a 54.0)
- **Beneficio**: Garantiza hándicaps válidos, type-safe, inmutable

## Consecuencias

### Positivas:
- ✅ **Validación automática**: Imposible crear objetos inválidos
- ✅ **Código más expresivo**: Tipos específicos vs genéricos  
- ✅ **Inmutabilidad**: Previene bugs y efectos colaterales
- ✅ **Centralización**: Una sola fuente de verdad para validaciones
- ✅ **Testabilidad**: Tests granulares y específicos

### Negativas:
- ❌ **Más código**: Más archivos y clases que mantener
- ❌ **Complejidad inicial**: Curva de aprendizaje
- ❌ **Performance**: Overhead mínimo en creación de objetos

### Riesgos Mitigados:
- **Complejidad**: Documentación clara y ejemplos
- **Performance**: Benchmarks muestran impacto despreciable
- **Mantenimiento**: Tests automatizados garantizan funcionalidad

## Implementación Detallada

### Patrones Aplicados:

1. **Factory Methods**:
   ```python
   password = Password.from_plain_text("MySecure123")
   user_id = UserId.generate()
   ```

2. **Validación en `__post_init__`**:
   ```python
   def __post_init__(self):
       if not self._is_valid():
           raise ValueError("Invalid value")
   ```

3. **Inmutabilidad con `frozen=True`**:
   ```python
   @dataclass(frozen=True)
   class ValueObject:
       # No permite modificaciones después de creación
   ```

### Optimizaciones para Testing:
- **bcrypt rápido**: rounds=4 en tests vs rounds=12 en producción
- **Variable TESTING**: Detección automática del entorno
- **Performance**: Value Objects no impactan velocidad de tests

## Validación

### Métricas de Éxito (Actualizado 9 Nov 2025):
- ✅ **69 tests específicos** de Value Objects (100% passing)
  - Email: 14 tests
  - Password: 23 tests
  - UserId: 12 tests
  - Handicap: 20 tests (nuevo)
- ✅ **0 bugs** relacionados con validación de datos
- ✅ **Código expresivo**: `User.create(email=Email("test@example.com"))`
- ✅ **Performance**: ~8s para 330 tests totales (incluyendo Value Objects)

### Criterios de Validación:
- [x] Imposible crear emails inválidos (✅ 14 tests)
- [x] Passwords siempre hasheados (✅ 23 tests)
- [x] UUIDs únicos y válidos (✅ 12 tests)
- [x] Hándicaps en rango válido (✅ 20 tests)
- [x] Objetos inmutables (✅ Tests de inmutabilidad)

## Referencias

- [Domain-Driven Design by Eric Evans](https://domainlanguage.com/ddd/)
- [Value Objects Explained](https://martinfowler.com/bliki/ValueObject.html)
- [Python Dataclasses Documentation](https://docs.python.org/3/library/dataclasses.html)

## Evolución e Implementaciones

### Value Objects Implementados (9 Nov 2025):
- ✅ **Handicap**: Handicap de golf con validación RFEG/EGA (-10.0 a 54.0)
  - Implementación completa con `@dataclass(frozen=True)`
  - Validación automática en `__post_init__`
  - Factory method `from_optional()` para valores opcionales
  - Type checking estricto (int/float)
  - 20 tests específicos con 100% de cobertura
  - Ver [ADR-014](./ADR-014-handicap-management-system.md) para detalles

#### Implementación Completa: Handicap Value Object

```python
from dataclasses import dataclass
from typing import Optional

@dataclass(frozen=True)
class Handicap:
    """
    Value Object que representa el hándicap de golf de un usuario.

    Rango válido: -10.0 a 54.0 según reglas RFEG/EGA.
    Es inmutable y garantiza que solo existan hándicaps válidos.
    """
    value: float

    def __post_init__(self):
        """Valida que el hándicap esté en el rango permitido."""
        if not isinstance(self.value, (int, float)):
            raise TypeError(
                f"El hándicap debe ser un número. Recibido: {type(self.value).__name__}"
            )

        if self.value < -10.0 or self.value > 54.0:
            raise ValueError(
                f"El hándicap debe estar entre -10.0 y 54.0. "
                f"Recibido: {self.value}"
            )

    def __str__(self) -> str:
        """Representación en string con un decimal."""
        return f"{self.value:.1f}"

    def __float__(self) -> float:
        """Permite convertir a float directamente."""
        return self.value

    @classmethod
    def from_optional(cls, value: Optional[float]) -> Optional['Handicap']:
        """Crea un Handicap desde un valor opcional."""
        return cls(value) if value is not None else None
```

**Beneficios del Handicap VO**:
- ✅ **Validación automática**: Imposible crear `Handicap(999.0)` o `Handicap(-100.0)`
- ✅ **Type Safety**: `TypeError` si se pasa string u otro tipo
- ✅ **Inmutabilidad**: `frozen=True` previene modificaciones
- ✅ **Reglas de negocio centralizadas**: Validación RFEG/EGA en un solo lugar
- ✅ **Testabilidad**: 20 tests específicos cubriendo todos los casos edge
- ✅ **Expresividad**: Código autodocumentado con tipos específicos

### Value Objects Planificados:
- **TeamId**: Identificador de equipo
- **Score**: Puntuación con validación de rango
- **MatchDate**: Fecha con validaciones de torneo

### Extensiones Posibles:
- **Serialización**: JSON automático para APIs
- **Comparación**: Ordenamiento natural para algunos VOs
- **Transformaciones**: Métodos de conversión entre formatos