# ADR-031: Match Play Scoring Calculation

**Date**: January 27, 2026
**Status**: Accepted
**Decision Makers**: Development Team
**Sprint**: v2.0.0 - Sprint 4 (Scoring System)

## Context and Problem

Match Play scoring requires calculating hole winners, net scores, and match standings based on:
- Gross scores (actual strokes)
- Strokes received per hole (from playing handicap + stroke index)
- Net scores (gross - strokes received)
- Match standing ("Team A leads 2UP", "All Square", "Team B wins 3&2")

**Need**: Domain Service to calculate match play standings following official R&A rules.

## Decisions

### 1. Net Score Calculation

```python
net_score = gross_score - strokes_received
```

**Where:**
- `gross_score`: Actual strokes taken on hole
- `strokes_received`: Calculated from playing handicap + hole stroke index

### 2. Strokes Received per Hole

**Algorithm** (already defined in ADR-026, applied here):

```python
def calculate_strokes_received(playing_handicap: int, stroke_index: int) -> int:
    strokes = 0
    if playing_handicap >= stroke_index:
        strokes = 1
    if playing_handicap >= (18 + stroke_index):
        strokes = 2  # For PH > 18
    return strokes
```

**Example**: Player with PH=15 on hole SI=10 → 1 stroke received

### 3. Hole Winner Logic

```python
if net_player_a < net_player_b:
    winner = "TEAM_A"  # +1 point
elif net_player_b < net_player_a:
    winner = "TEAM_B"  # +1 point
else:
    winner = "HALVED"  # +0.5 points each
```

### 4. Match Standing Calculation

**Domain Service**: `MatchPlayCalculator`

```python
class MatchPlayCalculator:
    @staticmethod
    def calculate_standing(holes_data: list[HoleScoreDetail]) -> MatchStanding:
        team_a_won = 0
        team_b_won = 0
        halved = 0

        for hole in holes_data:
            winner = determine_hole_winner(hole)
            if winner == "TEAM_A":
                team_a_won += 1
            elif winner == "TEAM_B":
                team_b_won += 1
            else:
                halved += 1

        return MatchStanding(
            team_a_holes_won=team_a_won,
            team_b_holes_won=team_b_won,
            holes_halved=halved,
            status=format_standing(team_a_won, team_b_won, holes_played)
        )
```

### 5. Match Status Strings

**Format**: `"{Leader} leads {holes}UP"` or `"{Winner} wins {holes}&{remaining}"`

**Examples**:
- "Team A leads 2UP" (A ganó 2 hoyos más, match continúa)
- "All Square" (empate perfecto)
- "Team B wins 3&2" (B ganó por 3 hoyos con 2 restantes)
- "All Square thru 12" (empate después de 12 hoyos)

**Algorithm**:
```python
def format_standing(a_won: int, b_won: int, holes_played: int) -> str:
    diff = a_won - b_won
    remaining = 18 - holes_played

    if diff == 0:
        return "All Square" if holes_played == 18 else f"All Square thru {holes_played}"

    leader = "Team A" if diff > 0 else "Team B"
    abs_diff = abs(diff)

    # Dormie (can't lose)
    if abs_diff >= remaining and remaining > 0:
        return f"{leader} wins {abs_diff}&{remaining}"

    # Match still alive
    return f"{leader} leads {abs_diff}UP"
```

### 6. Domain Service Location

**Package**: `src/modules/competition/domain/services/match_play_calculator.py`

**Stateless**: No internal state, pure functions

**Tests**: 10 unit tests covering:
- Basic hole winners (lower net wins)
- Halved holes (equal net scores)
- Standing calculation (multiple holes)
- Status formatting (leads, wins, all square)
- Edge cases (PH > 18, dormie situations)

## Consequences

### Positive ✅
- Official R&A Match Play rules compliance
- Clear separation: calculation logic in Domain Service
- Reusable across different match formats (FOURBALL, FOURSOMES, SINGLES)
- Stateless service = easy to test and reason about
- Frontend gets human-readable status strings

### Negative ⚠️
- Requires complete hole data to calculate standing (can't do partial calculations)
- String formatting in Domain layer (some argue should be in Presentation)

## Alternatives Considered

1. **Stroke Play calculation** → Descartado (not Ryder Cup format)
2. **Stableford points** → Descartado (different scoring system, v2.2.0)
3. **Status strings in API layer** → Descartado (business logic belongs in Domain)

## References

- **R&A Rules of Golf**: Rule 3.2 (Match Play)
- **ADR-025**: Competition Module Evolution v2.0.0
- **ADR-026**: Playing Handicap WHS Calculation (strokes received algorithm)
- **ROADMAP.md**: v2.0.0 Sprint 4 (Scoring System)

---
**Lines**: 98 | **Immutable after acceptance**
