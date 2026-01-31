# ADR-031: Match Play Scoring Calculation

**Date**: January 27, 2026
**Status**: Accepted
**Decision Makers**: Development Team
**Sprint**: v2.0.0 - Sprint 4 (Scoring System)

## Context and Problem

Match Play scoring needs: hole winners, net scores, match standings ("Team A leads 2UP", "All Square", "Team B wins 3&2").

**Need**: Domain Service for match play standings following R&A rules.

## Decisions

### 1. Net Score Calculation

**Formula**: `net_score = gross_score - strokes_received`

**Strokes received** (from ADR-026): Based on playing handicap vs hole stroke index.

### 2. Hole Winner Logic

- Lower net score → Team wins hole (+1 point)
- Equal net scores → Halved (+0.5 points each)

### 3. Match Standing Calculation

**Domain Service**: `MatchPlayCalculator` (stateless)

**Inputs**: List of hole score details (gross, net, strokes received)

**Outputs**: `MatchStanding` with:
- `team_a_holes_won`, `team_b_holes_won`, `holes_halved`
- `status` string (human-readable)

### 4. Match Status Strings

**Format examples**:
- "Team A leads 2UP" (match continues)
- "All Square" (tied after 18)
- "Team B wins 3&2" (dormie/won with 2 holes remaining)
- "All Square thru 12" (tied mid-match)

**Logic**:
- Calculate difference in holes won
- Check if dormie (difference ≥ remaining holes)
- Format accordingly

### 5. Implementation Location

**Package**: `src/modules/competition/domain/services/match_play_calculator.py`

**Characteristics**:
- Pure functions, no state
- Reusable across formats (FOURBALL, FOURSOMES, SINGLES)
- 10 unit tests (winners, halves, standings, edge cases)

## Consequences

### Positive ✅
- R&A Match Play rules compliant
- Domain Service separation (clear responsibility)
- Stateless = testable and predictable
- Human-readable status for frontend

### Negative ⚠️
- Requires complete hole data (no partial calculations)
- String formatting in Domain (debatable layer)

## Alternatives Considered

- **Stroke Play** → Not Ryder Cup format
- **Stableford** → Different system (v2.2.0)
- **Status in API layer** → Business logic belongs in Domain

## References

- **R&A Rules**: Rule 3.2 (Match Play)
- **ADR-025**: Competition Module Evolution
- **ADR-026**: Playing Handicap WHS Calculation
