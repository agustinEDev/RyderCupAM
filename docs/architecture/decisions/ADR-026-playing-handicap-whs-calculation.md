# ADR-026: Playing Handicap WHS Calculation

**Fecha**: 7 de enero de 2026
**Estado**: Aceptado
**Decisores**: Equipo de desarrollo

## Contexto y Problema

El World Handicap System (WHS) define cómo calcular el "playing handicap" para una ronda, basándose en:
- Handicap Index del jugador
- Slope Rating del tee
- Course Rating del campo
- Par del campo

**Necesidad:** Implementar cálculo correcto con manejo de casos edge.

## Decisiones

### 1. Fórmula WHS Oficial

```python
playing_handicap = round(
    (handicap_index * slope_rating / 113) + (course_rating - par)
)
```

**Razón**: Fórmula oficial WHS sin modificaciones.

### 2. Redondeo

**Decisión**: Redondear al entero más cercano (Python `round()`).

**Razón**: Estándar WHS. Ejemplo: 18.5 → 18, 18.6 → 19.

### 3. Handicap Negativo (Plus Handicap)

**Decisión**: Permitir handicaps negativos (-10.0 a +54.0).

**Razón**: WHS soporta "plus handicaps" para jugadores profesionales.

### 4. Validaciones de Rango

```python
# Handicap Index
-10.0 <= handicap_index <= 54.0

# Slope Rating
55 <= slope_rating <= 155

# Course Rating
course_rating > 0
```

**Razón**: Rangos oficiales WHS.

### 5. Strokes Received por Hoyo

```python
def get_strokes_received(playing_handicap: int, stroke_index: int) -> int:
    if playing_handicap <= 0:
        return 0

    # Primera vuelta (hoyos 1-18)
    strokes = 1 if playing_handicap >= stroke_index else 0

    # Vueltas adicionales (handicap > 18)
    extra = playing_handicap - 18
    if extra > 0:
        strokes += extra // 18
        if (extra % 18) >= stroke_index:
            strokes += 1

    return strokes
```

**Razón**: Algoritmo estándar para distribución de golpes en match play.

### 6. Momento del Cálculo

**Decisión**: Calcular al asignar tee, almacenar en `Match` entity.

```python
# Trigger: AssignTeeToPlayerUseCase
# Storage: Match.team_a_player_1_playing_handicap (int)
```

**Razón**: Eficiencia + auditoría + inmutabilidad (snapshot del momento).

### 7. Política de Recalculo

**No recalcular si:**
- Handicap index del jugador se actualiza después
- Course Rating cambia (campos inmutables post-aprobación)

**Recalcular solo si:**
- Se cambia el tee asignado al jugador
- Se reasigna jugador al match

**Razón**: Playing handicap es snapshot en momento de configuración.

## Consecuencias

### Positivas ✅
- Cumplimiento WHS oficial
- Casos edge bien definidos
- Playing handicap auditable
- Cálculos eficientes

### Negativas ⚠️
- Handicap actualizado NO recalcula matches automáticamente
- Creator debe reconfigurar manualmente si necesario

## Referencias

- **World Handicap System**: https://www.usga.org/handicapping.html
- **ADR-025**: Competition Module Evolution v2.1.0
