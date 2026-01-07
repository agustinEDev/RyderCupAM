# ADR-025: Competition Module Evolution - v2.1.0

**Fecha**: 7 de enero de 2026
**Estado**: Aceptado
**Decisores**: Equipo de desarrollo

## Contexto y Problema

El Competition Module actual permite crear torneos y gestionar inscripciones, pero carece de:
- Gestión de campos de golf (tees, hoyos, slope/course rating)
- Planificación de jornadas con matches específicos
- Live scoring con anotación hoyo a hoyo
- Validación dual (jugador vs marcador)
- Sistema de invitaciones para jugadores

**Necesidad:** Sistema completo para torneos Ryder Cup amateur profesionales.

## Decisiones

### 1. Sistema de Roles Formal

**Decisión**: Implementar roles con tablas dedicadas (no flags booleanos).

```python
RoleName = Enum("ADMIN", "CREATOR", "PLAYER")
# Tablas: roles, user_roles (many-to-many)
```

**Razón**: Escalabilidad para futuros roles y permisos granulares.

### 2. Tees con Categoría Normalizada

**Decisión**: Híbrido entre nomenclatura libre y categoría interna.

```python
class Tee:
    identifier: str          # "60", "Blancas", "Championship" (libre)
    category: TeeCategory    # CHAMPIONSHIP_MALE, AMATEUR_MALE, etc.
    slope_rating: float
    course_rating: float
    gender: Gender
```

**Razón**: Flexibilidad internacional + normalización para estadísticas.

### 3. Playing Handicap Pre-calculado

**Decisión**: Calcular y almacenar playing handicap al asignar tee al jugador.

```python
playing_handicap = (handicap_index × slope_rating / 113) + (course_rating - par)
# Storage: 4 campos en Match entity (team_a_player_1_playing_handicap, etc.)
```

**Razón**: Eficiencia en cálculos + auditoría (saber qué handicap se usó en cada match).

### 4. Validación Dual Independiente

**Decisión**: Cada jugador valida SOLO su propia tarjeta.

```python
def can_submit_scorecard(player: Player) -> bool:
    for hole in 1..18:
        if player.score[hole] != marker.annotation_for_player[hole]:
            return False  # ❌ Bloqueo
    return True  # ✅ Puede entregar
```

**Razón**: Player A puede entregar independientemente de la tarjeta de Player B. Refleja proceso real de golf.

### 5. Course Approval Workflow

**Decisión**: Creator crea campos → PENDING_APPROVAL → Admin aprueba/rechaza.

```python
ApprovalStatus = Enum("PENDING_APPROVAL", "APPROVED", "REJECTED")
```

**Razón**: No bloquea al Creator + control de calidad de datos.

### 6. Invitaciones con Token Seguro

**Decisión**: Sistema de invitaciones con token para registro directo.

```python
class Invitation:
    invitee_email: Email
    invitee_user_id: UserId | None  # null si no registrado
    token: str  # 256-bit, expira 7 días
    status: InvitationStatus
```

**Razón**: UX fluida (buscar por email + auto-inscripción al registrarse).

## Agregados Principales

**Nuevos:**
- `GolfCourse` (name, country, type, tees[], holes[])
- `Round` (date, golf_course, session_type)
- `Match` (format, players, tees, playing_handicaps, status)
- `Invitation` (competition, email, token, status)
- `HoleScore` (match, hole_number, player, gross, net, status)

**Enums clave:**
- `RoleName`, `TeeCategory`, `GolfCourseType`, `MatchFormat`, `MatchStatus`, `InvitationStatus`, `ScoreStatus`

## Consecuencias

### Positivas ✅
- Sistema profesional completo para torneos Ryder Cup
- Playing handicap auditable
- Validación dual refleja proceso real de golf
- Escalable: roles formales, tees normalizados
- UX fluida con invitaciones

### Negativas ⚠️
- Alta complejidad (+9 tablas, +14 entidades)
- Playing handicap duplicado (Competition policy + Match calculation)

## Referencias

- **ROADMAP.md**: Detalles de implementación v2.1.0
- **ADR-026**: Playing Handicap WHS Calculation
