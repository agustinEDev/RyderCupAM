# ADR-037: Two-Tier Handicap Architecture and Session-Based Round Model

**Status**: Implemented
**Date**: February 5, 2026
**Scope**: Competition Domain Layer (Sprint 2 Block 4)

---

## Context

Block 4 required modeling tournament rounds and handicap calculation. Two key design decisions:

1. **Handicap configuration granularity**: Where to define STROKE_PLAY vs MATCH_PLAY and allowance percentages? Competition-level only, Round-level only, or both?
2. **Round modeling**: Should a Round represent a full day (containing multiple sessions) or a single session (MORNING/AFTERNOON/EVENING)?

**Constraints:**
- WHS defines different default allowances per format: Singles 95-100%, Fourball 90%, Foursomes 50%
- A competition day can have mixed formats (e.g., Foursomes morning, Singles afternoon)
- Each session can use a different golf course
- Organizers need flexibility to override WHS defaults per round

---

## Decision

### 1. Two-Tier Handicap System

**Competition level** (`PlayMode` enum): Sets the tournament-wide default.
- `STROKE_PLAY` → Singles rounds default to 95% allowance
- `MATCH_PLAY` → Singles rounds default to 100% allowance

**Round level** (optional overrides):
- `handicap_mode`: Override STROKE_PLAY/MATCH_PLAY for this specific round (SINGLES only)
- `allowance_percentage`: Override the WHS default (50-100 in increments of 5)
- `None` values → fall back to Competition default or WHS standard

**Resolution order**: Round override > Competition PlayMode > WHS default.

### 2. Session-Based Round Model

Each `Round` = one session (MORNING, AFTERNOON, or EVENING), not a full day.

- A competition day with Foursomes AM + Singles PM = 2 Round entities
- Each Round has exactly one `MatchFormat` and one `GolfCourseId`
- Tees are NOT defined at Round level; each player has their `tee_category` in Enrollment

**WHS Default Allowances** (constants in Round entity):
| Format | Mode | Allowance |
|--------|------|-----------|
| SINGLES | STROKE_PLAY | 95% |
| SINGLES | MATCH_PLAY | 100% |
| FOURBALL | - | 90% |
| FOURSOMES | - | 50% (applied to team CH difference) |

---

## Consequences

### Positive
- **Maximum flexibility**: Organizers can customize per-round without affecting others
- **WHS compliant**: Defaults follow official World Handicap System percentages
- **Simple queries**: One Round = one format = one course = one set of matches
- **Clean state machine**: PENDING_TEAMS → PENDING_MATCHES → SCHEDULED → IN_PROGRESS → COMPLETED

### Negative
- **More entities per day**: 2-3 Rounds per day instead of 1 (minimal overhead)
- **Two-tier complexity**: Resolution logic requires checking Round → Competition → WHS defaults

### Alternatives Rejected
1. **Competition-only handicap**: Insufficient - can't have different allowances per round
2. **Day-based Round with nested sessions**: Over-engineered, complicates state machine and queries
3. **Tees at Round level**: Rejected - players within the same round may use different tees (male/female/senior)

---

## References

- [ADR-026: Playing Handicap WHS Calculation](./ADR-026-playing-handicap-whs-calculation.md)
- [WHS Manual of Handicapping](https://www.usga.org/handicapping.html)
- `src/modules/competition/domain/entities/round.py`
- `src/modules/competition/domain/value_objects/handicap_mode.py`

---

**Length**: 78 lines | **Author**: Development Team
