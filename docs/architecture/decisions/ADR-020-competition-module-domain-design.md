# ADR-020: Competition Module - Domain Design

**Date**: November 17, 2025
**Status**: Accepted
**Decision Makers**: Development Team

## Context and Problem

We need to implement the Competition module to manage Ryder Cup format tournaments, including:
- Complete tournament lifecycle (states)
- Enrollment system (requests, invitations, approvals)
- Handicap configuration
- Multi-country location support with multilanguage

### Critical Decisions:
1. Where to calculate handicaps? (Competition vs Match)
2. How to distinguish player cancellations vs creator rejections?
3. How to validate adjacent countries?

## Options Considered

1. **PlayMode**: Complete calculation vs policy only
2. **Enrollment States**: 4 basic states vs 6 states with CANCELLED
3. **Country Management**: Complete submodule vs pragmatic shared domain

## Decision

### Main Aggregates

**Competition (Aggregate Root)**
- States: `DRAFT → ACTIVE → CLOSED → IN_PROGRESS → COMPLETED/CANCELLED`
- Factory: `Competition.create()` emits `CompetitionCreatedEvent`

**Enrollment (Secondary Aggregate)**
- States: `REQUESTED/INVITED → APPROVED/REJECTED/CANCELLED → WITHDRAWN`
- We added **CANCELLED** to distinguish player actions vs creator:
  - **CANCELLED**: Player cancels request or declines invitation
  - **REJECTED**: Creator rejects request
  - **WITHDRAWN**: Player withdraws after being approved

### PlayMode: Policy Only

**Decision**: Store only play mode (SCRATCH/HANDICAP). Allowance percentages are configured per Round (ADR-037).

```python
class PlayMode(str, Enum):
    SCRATCH = "SCRATCH"
    HANDICAP = "HANDICAP"
```

**Reason**: Complete World Handicap System calculation (Course Rating, Slope Rating) requires field-specific and round data. Allowance percentages (90/95/100%) are now configured per Round via the two-tier handicap system (ADR-037), not at Competition level.

### Country Management: Shared Domain

**Decision**: Country entity in shared with simple multilanguage.

```python
@dataclass
class Country:
    code: CountryCode  # ISO 3166-1 alpha-2
    name_en: str
    name_es: str
    active: bool = True
```

**Adjacency validation**: In Use Case layer (not in VO) by querying ICountryRepository.

### Domain Events (11 total)

**Competition (7)**: Created, Activated, EnrollmentsClosed, Started, Completed, Cancelled, Updated
**Enrollment (4)**: Requested, Approved, Cancelled, Withdrawn

## Consequences

### Positive ✅
- Clear semantics between CANCELLED/REJECTED/WITHDRAWN for auditing
- Simple PlayMode allows Round-level handicap configuration without refactoring (ADR-037)
- Pragmatic multilanguage (name_en, name_es columns)
- Clean Architecture: Validation with repository in Use Case, pure VOs

### Negative ⚠️
- Handicap logic in two places (Competition PlayMode + Round allowance percentages)
- Adding languages requires migration (vs separate table)

## Implementation

**Phase 1: Domain Layer** ✅ Completed (Nov 17, 2025)
- 2 entities with state machines
- 9 Value Objects
- 11 Domain Events
- 38 unit tests (100% coverage)

**Phase 2: Application Layer** 🚧 Pending
- Use Cases and DTOs
- ICompetitionRepository, IEnrollmentRepository, ICountryRepository

**Phase 3: Infrastructure** ⏳ Pending
- SQLAlchemy repositories
- Migrations: competitions, enrollments, countries, country_adjacencies
- REST API endpoints

## References

- **CLAUDE.md**: Competition Module Section
- **CHANGELOG.md**: v1.3.0
- **Tests**: `tests/unit/modules/competition/domain/`
