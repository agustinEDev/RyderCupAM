# ADR-026: Playing Handicap WHS Calculation

**Date**: January 7, 2026
**Status**: Accepted
**Decision Makers**: Development Team

## Context and Problem

The World Handicap System (WHS) defines how to calculate the "playing handicap" for a round, based on:
- Player's Handicap Index
- Tee's Slope Rating
- Course Rating of the course
- Course Par

**Need:** Implement correct calculation with edge case handling.

## Decisions

### 1. Official WHS Formula

```python
playing_handicap = round(
    (handicap_index * slope_rating / 113) + (course_rating - par)
)
```

**Reason**: Official WHS formula without modifications.

### 2. Rounding

**Decision**: Round to nearest integer (Python `round()`).

**Reason**: WHS standard. Example: 18.5 → 18, 18.6 → 19.

### 3. Negative Handicap (Plus Handicap)

**Decision**: Allow negative handicaps (-10.0 to +54.0).

**Reason**: WHS supports "plus handicaps" for professional players.

### 4. Range Validations

```python
# Handicap Index
-10.0 <= handicap_index <= 54.0

# Slope Rating
55 <= slope_rating <= 155

# Course Rating
course_rating > 0
```

**Reason**: Official WHS ranges.

### 5. Strokes Received per Hole

**Algorithm**: Distribute strokes based on playing handicap and hole stroke index.
- Handicap ≤ 18: One stroke per hole up to playing handicap
- Handicap > 18: Multiple strokes on holes, distributed by stroke index

**Reason**: Standard WHS algorithm for match play stroke distribution.

### 6. Calculation Timing

**Decision**: Calculate when assigning tee, store in `Match` entity.

```python
# Trigger: AssignTeeToPlayerUseCase
# Storage: Match.team_a_player_1_playing_handicap (int)
```

**Reason**: Efficiency + auditing + immutability (moment snapshot).

### 7. Recalculation Policy

**Do NOT recalculate if:**
- Player's handicap index updates afterwards
- Course Rating changes (immutable fields post-approval)

**Recalculate only if:**
- Assigned tee changes for player
- Player is reassigned to match

**Reason**: Playing handicap is snapshot at configuration time.

## Consequences

### Positive ✅
- Official WHS compliance
- Well-defined edge cases
- Auditable playing handicap
- Efficient calculations

### Negative ⚠️
- Updated handicap does NOT automatically recalculate matches
- Creator must manually reconfigure if needed

## References

- **World Handicap System**: https://www.usga.org/handicapping.html
- **ADR-025**: Competition Module Evolution v2.1.0
