# ADR-025: Competition Module Evolution - v2.0.0

**Date**: January 9, 2026
**Status**: Accepted
**Decision Makers**: Development Team

## Context and Problem

The current Competition Module allows creating tournaments and managing enrollments, but lacks:
- Golf course management (tees, holes, slope/course rating)
- Round planning with specific matches
- Live scoring with hole-by-hole annotation
- Dual validation (player vs marker)
- Invitation system for players

**Need:** Complete system for professional amateur Ryder Cup tournaments.

## Decisions

### 1. Formal Role System

**Decision**: Implement roles with dedicated tables (not boolean flags).

```python
RoleName = Enum("ADMIN", "CREATOR", "PLAYER")
# Tables: roles, user_roles (many-to-many)
```

**Reason**: Scalability for future roles and granular permissions.

### 2. Tees with Normalized Category

**Decision**: Hybrid between free nomenclature and internal category.

```python
class Tee:
    identifier: str          # "60", "Blancas", "Championship" (free)
    category: TeeCategory    # CHAMPIONSHIP_MALE, AMATEUR_MALE, etc.
    slope_rating: float
    course_rating: float
    gender: Gender
```

**Reason**: International flexibility + normalization for statistics.

### 3. Pre-calculated Playing Handicap

**Decision**: Calculate and store playing handicap when assigning tee to player.

```python
playing_handicap = (handicap_index × slope_rating / 113) + (course_rating - par)
# Storage: 4 fields in Match entity (team_a_player_1_playing_handicap, etc.)
```

**Reason**: Efficiency in calculations + auditing (know what handicap was used in each match).

### 4. Independent Dual Validation

**Decision**: Each player validates ONLY their own card.

```python
def can_submit_scorecard(player: Player) -> bool:
    for hole in 1..18:
        if player.score[hole] != marker.annotation_for_player[hole]:
            return False  # ❌ Block
    return True  # ✅ Can submit
```

**Reason**: Player A can submit independently of Player B's card. Reflects real golf process.

### 5. Course Approval Workflow

**Decision**: Creator creates courses → PENDING_APPROVAL → Admin approves/rejects.

```python
ApprovalStatus = Enum("PENDING_APPROVAL", "APPROVED", "REJECTED")
```

**Reason**: Doesn't block Creator + data quality control.

### 6. Invitations with Secure Token

**Decision**: Invitation system with token for direct registration.

```python
class Invitation:
    invitee_email: Email
    invitee_user_id: UserId | None  # null if not registered
    token: str  # 256-bit, expires 7 days
    status: InvitationStatus
```

**Reason**: Smooth UX (search by email + auto-enrollment on registration).

## Main Aggregates

**New:**
- `GolfCourse` (name, country, type, tees[], holes[])
- `Round` (date, golf_course, session_type)
- `Match` (format, players, tees, playing_handicaps, status)
- `Invitation` (competition, email, token, status)
- `HoleScore` (match, hole_number, player, gross, net, status)

**Key Enums:**
- `RoleName`, `TeeCategory`, `GolfCourseType`, `MatchFormat`, `MatchStatus`, `InvitationStatus`, `ScoreStatus`

## Consequences

### Positive ✅
- Complete professional system for Ryder Cup tournaments
- Auditable playing handicap
- Dual validation reflects real golf process
- Scalable: formal roles, normalized tees
- Smooth UX with invitations

### Negative ⚠️
- High complexity (+9 tables, +14 entities)
- Duplicated playing handicap (Competition policy + Match calculation)

## References

- **ROADMAP.md**: v2.0.0 implementation details
- **ADR-026**: Playing Handicap WHS Calculation
