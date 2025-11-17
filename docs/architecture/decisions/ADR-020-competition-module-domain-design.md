# ADR-020: Competition Module - Domain Design

**Fecha**: 17 de noviembre de 2025
**Estado**: Aceptado
**Decisores**: Equipo de desarrollo

## Contexto y Problema

Necesitamos implementar el módulo de Competition para gestionar torneos formato Ryder Cup, incluyendo:
- Ciclo de vida completo del torneo (estados)
- Sistema de inscripciones (solicitudes, invitaciones, aprobaciones)
- Configuración de hándicaps
- Soporte para ubicaciones multipaís con multilenguaje

### Decisiones Críticas:
1. ¿Dónde calcular hándicaps? (Competition vs Match)
2. ¿Cómo distinguir cancelaciones de jugador vs rechazos de creador?
3. ¿Cómo validar países adyacentes?

## Opciones Consideradas

1. **HandicapSettings**: Cálculo completo vs solo política
2. **Estados de Enrollment**: 4 estados básicos vs 6 estados con CANCELLED
3. **Country Management**: Submódulo completo vs shared domain pragmático

## Decisión

### Agregados Principales

**Competition (Aggregate Root)**
- Estados: `DRAFT → ACTIVE → CLOSED → IN_PROGRESS → COMPLETED/CANCELLED`
- Factory: `Competition.create()` emite `CompetitionCreatedEvent`

**Enrollment (Aggregate Secundario)**
- Estados: `REQUESTED/INVITED → APPROVED/REJECTED/CANCELLED → WITHDRAWN`
- Agregamos **CANCELLED** para distinguir acciones de jugador vs creador:
  - **CANCELLED**: Jugador cancela solicitud o declina invitación
  - **REJECTED**: Creador rechaza solicitud
  - **WITHDRAWN**: Jugador se retira después de estar aprobado

### HandicapSettings: Solo Política

**Decisión**: Almacenar solo tipo (SCRATCH/PERCENTAGE) y porcentaje (90/95/100).

```python
@dataclass(frozen=True)
class HandicapSettings:
    type: HandicapType
    percentage: Optional[int]  # 90, 95, 100
```

**Razón**: Cálculo completo de World Handicap System (Course Rating, Slope Rating) requiere datos específicos del campo y partida. Este cálculo se moverá a la futura entidad **Match**.

### Country Management: Shared Domain

**Decisión**: Country entity en shared con multilenguaje simple.

```python
@dataclass
class Country:
    code: CountryCode  # ISO 3166-1 alpha-2
    name_en: str
    name_es: str
    active: bool = True
```

**Validación de adyacencia**: En Use Case layer (no en VO) consultando ICountryRepository.

### Domain Events (11 total)

**Competition (7)**: Created, Activated, EnrollmentsClosed, Started, Completed, Cancelled, Updated
**Enrollment (4)**: Requested, Approved, Cancelled, Withdrawn

## Consecuencias

### Positivas ✅
- Semántica clara entre CANCELLED/REJECTED/WITHDRAWN para auditoría
- HandicapSettings simple permite agregar cálculo completo en Match sin refactorizar
- Multilenguaje pragmático (columnas name_en, name_es)
- Clean Architecture: Validación con repositorio en Use Case, VOs puros

### Negativas ⚠️
- Lógica de hándicap en dos lugares (Competition policy + Match calculation)
- Agregar idiomas requiere migración (vs tabla separada)

## Implementación

**Fase 1: Domain Layer** ✅ Completado (17 Nov 2025)
- 2 entidades con máquinas de estado
- 9 Value Objects
- 11 Domain Events
- 38 tests unitarios (100% cobertura)

**Fase 2: Application Layer** 🚧 Pendiente
- Use Cases y DTOs
- ICompetitionRepository, IEnrollmentRepository, ICountryRepository

**Fase 3: Infrastructure** ⏳ Pendiente
- SQLAlchemy repositories
- Migraciones: competitions, enrollments, countries, country_adjacencies
- Endpoints REST API

## Referencias

- **CLAUDE.md**: Sección Competition Module
- **CHANGELOG.md**: v1.3.0
- **Tests**: `tests/unit/modules/competition/domain/`
