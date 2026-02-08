# ADR-025: Competition Module Evolution - v2.0.0

**Date**: January 9, 2026
**Status**: Accepted
**Decision Makers**: Development Team

## Context and Problem

Competition Module lacks: golf courses, round planning, live scoring, dual validation, invitations.

**Need**: Complete system for professional amateur Ryder Cup tournaments.

## Decisions

### 1. Simplified RBAC (Table-less)

**Decision**: Three-tier contextual roles without database tables.

- **ADMIN**: `users.is_admin` boolean field (global)
- **CREATOR**: Derived from `competition.creator_id == user.id` (contextual)
- **PLAYER**: Derived from `enrollment.status == APPROVED` (contextual)

**Reason**: Reduces complexity while meeting requirements. No over-engineering.

### 2. Tees with Normalized Category

**Decision**: Hybrid free nomenclature + internal category.

- `identifier`: "60", "Blancas", "Championship" (free text)
- `category`: TeeCategory enum (CHAMPIONSHIP, AMATEUR, SENIOR, FORWARD, JUNIOR)
- `tee_gender`: Gender (MALE, FEMALE, or null) — independent field per tee
- `slope_rating`, `course_rating`

**Reason**: International flexibility + statistical normalization.

### 3. Pre-calculated Playing Handicap

**Decision**: Calculate and store playing handicap when assigning tee to player.

**Formula**: `PH = (HI × SR / 113) + (CR - par)`

**Storage**: 4 fields in Match entity (one per player).

**Reason**: Efficiency + audit trail (know exact handicap used in match).

### 4. Independent Dual Validation

**Decision**: Each player validates ONLY their own scorecard.

**Logic**: Player can submit if `player.score[hole] == marker.annotation[hole]` for all 18 holes.

**Reason**: Independence between players, reflects real golf process.

### 5. Course Approval Workflow

**Decision**: Creator creates → PENDING_APPROVAL → Admin approves/rejects.

**States**: `PENDING_APPROVAL`, `APPROVED`, `REJECTED` (final states).

**Reason**: Quality control without blocking Creator workflow.

### 6. Invitations with Secure Token

**Decision**: 256-bit token, 7-day expiration, auto-enrollment on acceptance.

**Flow**: Creator invites by email → Token sent → Player registers/accepts → Enrollment.APPROVED.

**Reason**: Smooth UX, invitation = pre-approval.

## Main Aggregates

**New**: `GolfCourse`, `Round`, `Match`, `Invitation`, `HoleScore`

**Key Enums**: `TeeCategory` (5 values + separate `Gender`), `MatchFormat`, `MatchStatus`, `InvitationStatus`, `ScoreStatus`

## Consequences

### Positive ✅
- Complete professional tournament system
- Auditable handicaps, dual validation
- Scalable RBAC, normalized data
- Smooth invitation UX

### Negative ⚠️
- High complexity (+9 tables, +14 entities)
- Playing handicap duplicated (policy + match)

## References

- **ROADMAP.md**: v2.0.0 details
- **ADR-026**: Playing Handicap WHS Calculation
- **ADR-031-033**: Match scoring, approval, invitations
