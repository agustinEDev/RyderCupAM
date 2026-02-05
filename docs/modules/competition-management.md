# Module: Competition Management

## 📋 Description

Module responsible for managing Ryder Cup format tournaments, including enrollments, teams, and handicap configuration. Implements Clean Architecture with DDD.

**📋 See complete API:** `docs/API.md`

---

## 🎯 Implemented Use Cases

### Competition Management (10 use cases)
1. **CreateCompetitionUseCase** - Create tournament in DRAFT status
2. **GetCompetitionUseCase** - Get tournament details
3. **ListCompetitionsUseCase** - List tournaments with filters
4. **UpdateCompetitionUseCase** - Update tournament (DRAFT only)
5. **DeleteCompetitionUseCase** - Delete tournament (DRAFT only)
6. **ActivateCompetitionUseCase** - Transition DRAFT → ACTIVE
7. **CloseEnrollmentsUseCase** - Transition ACTIVE → CLOSED
8. **StartCompetitionUseCase** - Transition CLOSED → IN_PROGRESS
9. **CompleteCompetitionUseCase** - Transition IN_PROGRESS → COMPLETED
10. **CancelCompetitionUseCase** - Transition to CANCELLED from any status

### Enrollment Management (7 use cases)
11. **RequestEnrollmentUseCase** - Request enrollment (REQUESTED)
12. **DirectEnrollPlayerUseCase** - Direct enrollment by creator (APPROVED)
13. **ListEnrollmentsUseCase** - List enrollments with filters
14. **HandleEnrollmentUseCase** - Approve/reject requests
15. **CancelEnrollmentUseCase** - Cancel request/invitation
16. **WithdrawEnrollmentUseCase** - Withdraw from competition
17. **SetCustomHandicapUseCase** - Set custom handicap

---

## 🗃️ Domain Model

### Entity: Competition (Aggregate Root)

**Identification:**
- `id`: CompetitionId (Value Object - UUID)

**Main Data:**
- `name`: CompetitionName (Value Object - 3-100 chars, unique)
- `dates`: DateRange (Value Object - start_date, end_date)
- `location`: Location (Value Object - up to 3 adjacent countries)
- `creator_id`: UserId (Value Object - tournament creator)
- `max_players`: int (2-100 players)
- `status`: CompetitionStatus (enum - DRAFT/ACTIVE/CLOSED/IN_PROGRESS/COMPLETED/CANCELLED)

**Play Mode:**
- `play_mode`: PlayMode (enum - SCRATCH/HANDICAP)
  - SCRATCH: No handicap applied
  - HANDICAP: Allowance percentages configured per Round (two-tier system, ADR-037)

**Team Configuration:**
- `team_assignment`: TeamAssignment (RANDOM or MANUAL)
- `team_1_name`: str (optional, max 50)
- `team_2_name`: str (optional, max 50)

**Timestamps:**
- `created_at`: datetime
- `updated_at`: datetime

### Entity: Enrollment (Secondary Aggregate)

**Identification:**
- `id`: EnrollmentId (Value Object - UUID)
- `competition_id`: CompetitionId
- `user_id`: UserId

**Status and Configuration:**
- `status`: EnrollmentStatus (REQUESTED/INVITED/APPROVED/REJECTED/CANCELLED/WITHDRAWN)
- `custom_handicap`: float (optional, -10.0 to 54.0)
- `team_id`: str (optional, "1" or "2")

**Timestamps:**
- `created_at`: datetime
- `updated_at`: datetime

### Entity: Round (Session) ⭐ Sprint 2 Block 4

**Identification:**
- `id`: RoundId (Value Object - UUID)
- `competition_id`: CompetitionId
- `golf_course_id`: GolfCourseId

**Session Configuration:**
- `round_date`: date (day of the session)
- `session_type`: SessionType (MORNING/AFTERNOON/EVENING)
- `match_format`: MatchFormat (SINGLES/FOURBALL/FOURSOMES)
- `status`: RoundStatus (PENDING_TEAMS → PENDING_MATCHES → SCHEDULED → IN_PROGRESS → COMPLETED)

**Handicap Configuration (Two-Tier System):**
- `handicap_mode`: HandicapMode | None (STROKE_PLAY/MATCH_PLAY, only for SINGLES)
- `allowance_percentage`: int | None (50-100 in steps of 5, None = WHS default)
- WHS defaults: Singles STROKE_PLAY 95%, MATCH_PLAY 100%, Fourball 90%, Foursomes 50%

**Timestamps:**
- `created_at`: datetime
- `updated_at`: datetime

### Entity: Match ⭐ Sprint 2 Block 4

**Identification:**
- `id`: MatchId (Value Object - UUID)
- `round_id`: RoundId

**Match Data:**
- `match_number`: int (order within round)
- `team_a_players`: tuple[MatchPlayer, ...] (1 for SINGLES, 2 for FOURBALL/FOURSOMES)
- `team_b_players`: tuple[MatchPlayer, ...] (mirrored)
- `status`: MatchStatus (SCHEDULED → IN_PROGRESS → COMPLETED | WALKOVER)

### Entity: TeamAssignment ⭐ Sprint 2 Block 4

**Identification:**
- `id`: TeamAssignmentId (Value Object - UUID)
- `competition_id`: CompetitionId

**Assignment Data:**
- `mode`: TeamAssignmentMode (AUTOMATIC/MANUAL)
- `team_a_player_ids`: tuple[UserId, ...]
- `team_b_player_ids`: tuple[UserId, ...]
- `created_at`: datetime

**Business Rules:**
- Teams must have equal player count
- No player can be in both teams
- No duplicate players within a team

### Value Object: MatchPlayer ⭐ Sprint 2 Block 4

**Frozen dataclass (immutable):**
- `user_id`: UserId
- `playing_handicap`: int (calculated via WHS formula, ≥ 0)
- `tee_category`: TeeCategory
- `strokes_received`: tuple[int, ...] (hole numbers where player receives a stroke, 1-18)

### Entity: Country (Shared Domain)

**Identification:**
- `code`: CountryCode (Value Object - ISO 3166-1 alpha-2)

**Data:**
- `name_en`: str (name in English)
- `name_es`: str (name in Spanish)
- `active`: bool (if available for selection)

---

## 🏭 Value Objects Implemented

### Competition Module - Base (9 VOs)
- `CompetitionId` - Unique competition UUID
- `CompetitionName` - Validated name (3-100 chars, unique)
- `DateRange` - Date range (start_date ≤ end_date)
- `Location` - Up to 3 adjacent countries (main + 2 optional)
- `PlayMode` - Play mode (SCRATCH/HANDICAP)
- `CompetitionStatus` - Tournament status (6 possible states)
- `EnrollmentId` - Unique enrollment UUID
- `EnrollmentStatus` - Enrollment status (6 possible states)
- `CountryCode` - ISO 3166-1 alpha-2 code (shared)

### Competition Module - Rounds & Matches (11 VOs) ⭐ Sprint 2 Block 4
- `RoundId` - Unique round UUID
- `MatchId` - Unique match UUID
- `TeamAssignmentId` - Unique team assignment UUID
- `SessionType` - Session time (MORNING/AFTERNOON/EVENING)
- `MatchFormat` - Match format (SINGLES/FOURBALL/FOURSOMES) with `players_per_team()`
- `MatchStatus` - Match state (SCHEDULED/IN_PROGRESS/COMPLETED/WALKOVER)
- `RoundStatus` - Round state (PENDING_TEAMS/PENDING_MATCHES/SCHEDULED/IN_PROGRESS/COMPLETED) with `can_modify()`, `can_generate_matches()`
- `TeamAssignmentMode` - Team assignment method (AUTOMATIC/MANUAL)
- `ScheduleConfigMode` - Schedule configuration method (AUTOMATIC/MANUAL)
- `HandicapMode` - Handicap calculation mode for SINGLES (STROKE_PLAY 95%/MATCH_PLAY 100%)
- `PlayMode` - Competition-level default handicap mode (STROKE_PLAY/MATCH_PLAY)

---

## 🔧 Domain Services ⭐ Sprint 2 Block 4

### PlayingHandicapCalculator
WHS formula: `PH = (HI x (SR / 113) + (CR - Par)) x Allowance%`

**Methods:**
- `calculate(handicap_index, tee_rating, allowance_percentage)` → int
- `calculate_for_singles(player_hi, player_tee, opponent_hi, opponent_tee, handicap_mode)` → tuple
- `calculate_for_fourball(player1_hi, player1_tee, player2_hi, player2_tee)` → tuple
- `calculate_for_foursomes(team1_hi_avg, team1_tee, team2_hi_avg, team2_tee)` → tuple (strokes to each team)

### SnakeDraftService
Serpentine algorithm for balanced team assignment.

**Pattern:** A,B,B,A,A,B,B,A... (players sorted by handicap, best first)

**Methods:**
- `assign_teams(players, first_pick)` → list[DraftResult]
- `validate_team_balance(results)` → bool
- `get_team_players(results, team)` → list[UserId]

---

## 🔄 Domain Events Implemented

### Competition Events (11 events)
1. `CompetitionCreatedEvent` - Tournament created
2. `CompetitionUpdatedEvent` - Tournament updated
3. `CompetitionActivatedEvent` - Transition to ACTIVE
4. `EnrollmentsClosedEvent` - Transition to CLOSED
5. `CompetitionStartedEvent` - Transition to IN_PROGRESS
6. `CompetitionCompletedEvent` - Transition to COMPLETED
7. `CompetitionCancelledEvent` - Tournament cancelled
8. `CompetitionDeletedEvent` - Tournament deleted

### Enrollment Events (4 events)
9. `EnrollmentRequestedEvent` - Enrollment request
10. `EnrollmentApprovedEvent` - Enrollment approved
11. `EnrollmentCancelledEvent` - Enrollment cancelled
12. `EnrollmentWithdrawnEvent` - Player withdrawn

---

## 🏛️ Architecture

### Repository Pattern

**Interfaces (Domain Layer):**
- `CompetitionRepositoryInterface` - Competition CRUD
  - find_by_id, find_by_creator, find_by_status, find_active_in_date_range
  - add, update, delete, exists_with_name, count_by_creator
- `EnrollmentRepositoryInterface` - Enrollment CRUD
  - find_by_id, find_by_competition, find_by_competition_and_status, find_by_user
  - add, update, exists_for_user_in_competition, count_approved, find_by_competition_and_team
- `CountryRepositoryInterface` - Country queries (shared)
  - find_by_code, find_all_active, are_adjacent, find_adjacent_countries, exists

**Implementations (Infrastructure Layer):**
- `SQLAlchemyCompetitionRepository` - Async persistence with PostgreSQL
- `SQLAlchemyEnrollmentRepository` - Enrollment persistence
- `SQLAlchemyCountryRepository` - Country queries (seed data)

**📋 See implementation:** `src/modules/competition/infrastructure/persistence/sqlalchemy/`

### Unit of Work Pattern

**Interface (Domain Layer):**
```
CompetitionUnitOfWorkInterface
├── competitions: CompetitionRepositoryInterface
├── enrollments: EnrollmentRepositoryInterface
├── countries: CountryRepositoryInterface
├── async commit()
├── async rollback()
└── async __aenter__() / __aexit__()
```

**Implementation (Infrastructure Layer):**
- `SQLAlchemyCompetitionUnitOfWork` - Atomic transaction management

---

## 📊 Database Schema

### Tabla: competitions
```sql
CREATE TABLE competitions (
    id UUID PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    country_code VARCHAR(2) REFERENCES countries(code),
    secondary_country_code VARCHAR(2) REFERENCES countries(code),
    tertiary_country_code VARCHAR(2) REFERENCES countries(code),
    max_players INTEGER NOT NULL CHECK (max_players BETWEEN 2 AND 100),
    play_mode VARCHAR(20) NOT NULL,
    team_assignment VARCHAR(20) NOT NULL,
    team_1_name VARCHAR(50),
    team_2_name VARCHAR(50),
    status VARCHAR(20) NOT NULL,
    creator_id UUID REFERENCES users(id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX idx_competitions_creator_id ON competitions(creator_id);
CREATE INDEX idx_competitions_status ON competitions(status);
CREATE INDEX idx_competitions_dates ON competitions(start_date, end_date);
```

### Table: enrollments
```sql
CREATE TABLE enrollments (
    id UUID PRIMARY KEY,
    competition_id UUID REFERENCES competitions(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    status VARCHAR(20) NOT NULL,
    custom_handicap DECIMAL(4,1),
    team_id VARCHAR(1),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE (competition_id, user_id)
);
CREATE INDEX idx_enrollments_competition_id ON enrollments(competition_id);
CREATE INDEX idx_enrollments_user_id ON enrollments(user_id);
CREATE INDEX idx_enrollments_status ON enrollments(status);
```

### Table: countries (Shared - Seed Data)
```sql
CREATE TABLE countries (
    code VARCHAR(2) PRIMARY KEY,
    name_en VARCHAR(100) NOT NULL,
    name_es VARCHAR(100) NOT NULL,
    active BOOLEAN DEFAULT TRUE
);
```

### Table: country_adjacencies (Bidirectional Relationships)
```sql
CREATE TABLE country_adjacencies (
    country_code VARCHAR(2) REFERENCES countries(code),
    adjacent_country_code VARCHAR(2) REFERENCES countries(code),
    PRIMARY KEY (country_code, adjacent_country_code)
);
```

**Seed Data:**
- 166 global countries (not only Europe)
- 614 bidirectional border relationships (Wikipedia)
- Bilingual names (English/Spanish)

**📋 See mappers:** `src/modules/competition/infrastructure/persistence/sqlalchemy/mappers.py`

---

## 📡 API Endpoints

### Competition Management (10 endpoints)
- `POST /api/v1/competitions` - Create competition
- `GET /api/v1/competitions` - List competitions with filters
- `GET /api/v1/competitions/{id}` - Get competition
- `PUT /api/v1/competitions/{id}` - Update competition (DRAFT only)
- `DELETE /api/v1/competitions/{id}` - Delete competition (DRAFT only)
- `POST /api/v1/competitions/{id}/activate` - DRAFT → ACTIVE
- `POST /api/v1/competitions/{id}/close-enrollments` - ACTIVE → CLOSED
- `POST /api/v1/competitions/{id}/start` - CLOSED → IN_PROGRESS
- `POST /api/v1/competitions/{id}/complete` - IN_PROGRESS → COMPLETED
- `POST /api/v1/competitions/{id}/cancel` - Any status → CANCELLED

### Enrollment Management (8 endpoints)
- `POST /api/v1/competitions/{id}/enrollments` - Request enrollment
- `POST /api/v1/competitions/{id}/enrollments/direct` - Direct enrollment (creator)
- `GET /api/v1/competitions/{id}/enrollments` - List enrollments
- `POST /api/v1/enrollments/{id}/approve` - Approve request
- `POST /api/v1/enrollments/{id}/reject` - Reject request
- `POST /api/v1/enrollments/{id}/cancel` - Cancel request
- `POST /api/v1/enrollments/{id}/withdraw` - Withdraw from competition
- `PUT /api/v1/enrollments/{id}/handicap` - Set custom handicap

### Country Management (2 endpoints - Shared)
- `GET /api/v1/countries` - List active countries
- `GET /api/v1/countries/{code}/adjacent` - Adjacent countries

**📋 See complete documentation:** `docs/API.md`

---

## 🔐 Security and Rate Limiting

### Rate Limits
- `POST /api/v1/competitions` - 10 tournaments/hour (anti-spam)

### Authorization
- **Only creator** can update, delete or change tournament status
- **Only creator** can approve/reject enrollment requests
- **Only creator** can enroll players directly
- **Only creator** can set custom handicaps
- **Only owner** can cancel/withdraw from their own enrollment

---

## 🧪 Testing

### Statistics
- **Total Competition Domain:** 296 tests (100% passing) ⭐ Sprint 2 Block 4
- **Unit Tests (Domain - Base):** 62 tests (entities, value objects, repositories)
- **Unit Tests (Domain - Rounds & Matches):** 234 tests (11 VOs + 3 entities + 2 services) ⭐
- **Unit Tests (Application):** 84 tests (use cases + Golf Courses M2M)
- **Unit Tests (DTOs):** 49 tests (validations)
- **Integration Tests:** 9 tests (API endpoints)

### Structure
```
tests/unit/modules/competition/
├── domain/value_objects/test_*.py (20 base + 9 new VOs)
├── domain/entities/test_*.py (3 new: round, match, team_assignment)
├── domain/services/test_*.py (2 new: handicap_calculator, snake_draft)
├── application/dto/test_*.py (49 tests)
├── application/use_cases/test_*.py (84 tests)
└── infrastructure/ (pending)

tests/integration/api/v1/
├── test_competition_routes.py
├── test_enrollment_routes.py
└── test_competition_golf_courses_routes.py
```

### Execution
```bash
# All tests for Competition module
pytest tests/unit/modules/competition/ -v

# Only unit tests (fast)
pytest tests/unit/modules/competition/domain/ -v

# With parallelization
pytest tests/unit/modules/competition/ -n auto
```

---

## 🔄 States and Transitions

### Competition Status (Tournament Status)

```
DRAFT → ACTIVE → CLOSED → IN_PROGRESS → COMPLETED
  ↓        ↓         ↓           ↓
  └────────┴─────────┴───────────┴─→ CANCELLED
```

**States:**
- `DRAFT` - Draft, only visible to creator, editable
- `ACTIVE` - Active, enrollments open
- `CLOSED` - Enrollments closed, teams configured
- `IN_PROGRESS` - Tournament in progress
- `COMPLETED` - Tournament finished
- `CANCELLED` - Cancelled from any status

**Rules:**
- Only DRAFT is editable/deletable
- Only ACTIVE accepts enrollments
- Only creator can change states

### Enrollment Status (Enrollment Status)

```
REQUESTED → APPROVED → WITHDRAWN
    ↓           ↓
REJECTED    CANCELLED
```

**States:**
- `REQUESTED` - Pending request
- `INVITED` - Invited by creator (future)
- `APPROVED` - Enrollment approved
- `REJECTED` - Request rejected
- `CANCELLED` - Cancelled by player (pre-approval)
- `WITHDRAWN` - Withdrawn by player (post-approval)

---

## 🏛️ Architecture Decisions

### 1. Location Value Object - Multi-Country Support
**Decision:** Support for up to 3 adjacent countries in a competition

**Reason:**
- Cross-border tournaments are common in Europe
- Automatic validation of geographical adjacency
- Local database with seed data (no external API)

**Implementation:**
- Composite Value Object: Location(main, secondary, tertiary)
- Adjacency validation against country_adjacencies table
- 614 bidirectional relationships preloaded

### 2. Custom Handicap Override
**Decision:** Allow override of official handicap per enrollment

**Reason:**
- Flexibility for organizers
- Special cases (injured players, special categories)
- Does not modify user's official handicap

**Implementation:**
- Optional `custom_handicap` field in Enrollment entity
- Only creator can set
- If NULL, uses user's official handicap

### 3. Competition State Machine
**Decision:** Explicit states with strict validations

**Reason:**
- Prevent inconsistencies (e.g.: starting tournament without closing enrollments)
- Complete traceability with Domain Events
- Security (only creator can change states)

**Implementation:**
- CompetitionStatus enum with 6 states
- Transition methods in entity (activate, close, start, complete, cancel)
- Domain Events emitted on each transition

---

## 🔗 Related Links

### Documentation
- **API Endpoints:** `docs/API.md`
- **User Management Module:** `docs/modules/user-management.md`
- **Security Implementation:** `docs/SECURITY_IMPLEMENTATION.md`

### Source Code
- **Domain Layer:** `src/modules/competition/domain/`
- **Application Layer:** `src/modules/competition/application/`
- **Infrastructure Layer:** `src/modules/competition/infrastructure/`

### ADRs (Architecture Decision Records)
- **ADR-020:** Competition Module Domain Design
- **ADR-005:** Repository Pattern
- **ADR-006:** Unit of Work Pattern
- **ADR-007:** Domain Events Pattern
- **ADR-026:** Playing Handicap WHS Calculation
- **ADR-037:** Two-Tier Handicap Architecture and Session-Based Round Model ⭐ Sprint 2

### Testing
- **Unit Tests:** `tests/unit/modules/competition/`
- **Integration Tests:** `tests/integration/api/v1/`

---

## 💡 Development Tips

### Create New Competition Use Case
1. Define Request and Response DTO in `application/dto/competition_dto.py`
2. Create Use Case in `application/use_cases/`
3. Inject CompetitionUnitOfWork in constructor
4. Implement logic in `execute()` method
5. Use `async with self._uow:` for transactions
6. Emit domain events if necessary
7. Create unit + integration tests

### Add New State Transition
1. Create method in Competition entity (`def transition_name(self)`)
2. Validate current state with `_ensure_state(CompetitionStatus.XXX)`
3. Change state and emit Domain Event
4. Create Use Case wrapper (optional, recommended)
5. Add endpoint in `competition_routes.py`
6. Create valid/invalid transition tests

### Working with Enrollments
1. Always validate that competition.status == ACTIVE
2. Verify no duplicate enrollment exists
3. Use `custom_handicap` only if necessary (NULL uses official)
4. Emit domain events for traceability
5. Validate permissions (only creator/owner depending on action)

---

**Last Updated:** 5 February 2026
**Version:** Sprint 2 Block 4 (Rounds & Matches Domain Layer)
