# 🗺️ Roadmap - RyderCupFriends Backend

> **Current Version:** 2.0.5 (Production)
> **Last Updated:** Feb 5, 2026
> **OWASP Score:** 9.4/10

---

## 📊 Current Status

**Tests:** 1,201 (1,201 passing, 16 skipped, ~79s) | **Endpoints:** 54 REST API | **CI/CD:** GitHub Actions (10 jobs, ~3min)

**Completed Modules:**
- **User:** Login, Register, Email Verification, Password Reset, Handicap (RFEG), Device Fingerprinting, RBAC Foundation
- **Competition:** CRUD, Enrollments, Countries (166 + 614 borders), State Machine (6 states), Competition ↔ GolfCourse M2M (add/remove/reorder) ⭐ v2.0.2
- **Golf Course:** Request, Approval Workflow (Admin), Update Workflow (Clone-Based), CRUD endpoints (10 total), WHS-compliant tees/holes validation ⭐ v2.0.1
- **Security:** Rate Limiting, httpOnly Cookies, Session Timeout, CORS, CSRF, Account Lockout, Password History, IP Spoofing Prevention

**OWASP Top 10:** A01(10/10), A02(10/10), A03(10/10), A04(9/10), A05(9.5/10), A06(9/10), A07(9.5/10), A08(7/10), A09(10/10), A10(8/10) = **9.4/10** ⭐

---

## 🎯 Future Roadmap

### v2.0.1 - Competition Module Evolution ⭐ TOP PRIORITY

**Dates:** Jan 27 - Mar 24, 2026 (8 weeks) | **Effort:** 394h | **Tests:** 130+ | **Endpoints:** 34

**Goal:** Complete Ryder Cup tournament management system with golf courses, scheduling, live scoring with dual validation, and real-time leaderboards.

**Note:** Minor version bump (v2.0.0 was RBAC Foundation). Major changes: 34 endpoints, 13 entities, 8 weeks development.

---

#### 📅 Sprint Breakdown

| Sprint | Dates | Hours | Endpoints | Tests | Sync Point |
|--------|-------|-------|-----------|-------|------------|
| **Sprint 1** | Jan 27 - Jan 31 | 60h | 11 (RBAC + Golf Courses) | 51+ | ✅ COMPLETED |
| **Sprint 2** | Feb 3 - Feb 24 | 134h | 14 (Competition-GolfCourse + Rounds + Matches) | 73+ | 🔄 Fri, Feb 13, Feb 20 |
| **Sprint 3** | Feb 25 - Mar 3 | 48h | 5 (Invitations) | 12+ | 🔄 Fri, Feb 27 |
| **Sprint 4** | Mar 4 - Mar 17 | 92h | 4 (Scoring) | 20+ | 🔄 Fri, Mar 13 |
| **Sprint 5** | Mar 18 - Mar 24 | 60h | 2 (Leaderboards) | 10+ | 🔄 Fri, Mar 20 |

---

#### Sprint 1: RBAC Foundation + Golf Course Module v2.0.1 (✅ COMPLETED: Jan 31, 2026)

**RBAC Foundation v2.0.0: Simplified Role System**
- **Architecture**: Three-tier system WITHOUT a formal roles table.
  - **ADMIN Role** (Global): `users.is_admin` boolean field.
  - **CREATOR Role** (Contextual): Derived from `competition.creator_id == user.id`.
  - **PLAYER Role** (Contextual): Derived from an enrollment with `status = APPROVED`.
- **New Endpoint**:
  - `GET /api/v1/users/me/roles/{competition_id}` - Checks the user's roles for a specific competition.
    - Returns: `{is_admin, is_creator, is_player}` for the current user.
- **Authorization Helpers** (Infrastructure Layer): `is_admin_user()`, `is_creator_of()`, `is_player_in()`.
- **Test Coverage**: 17 unit tests (authorization helpers), 8 integration tests (API endpoint). **Total: 25 new tests (100% passing)**.
- **Key Files Modified/Created**:
  - `alembic/versions/7522c9fc51ef_add_is_admin_field_to_users_table.py` (migration)
  - `src/modules/user/domain/entities/user.py` (`is_admin` added)
  - `src/modules/user/infrastructure/api/v1/user_routes.py` (new endpoint)
  - `src/modules/competition/infrastructure/authorization/` (helper functions)
  - `tests/integration/api/v1/test_user_roles_endpoint.py` (integration tests)

**Golf Courses Endpoints (10):**
```
POST /api/v1/golf-courses/request          # Creator requests new course
POST /api/v1/admin/golf-courses            # Admin creates course directly (approved)
GET  /api/v1/golf-courses/{id}             # Details (tees + holes)
GET  /api/v1/golf-courses?approval_status=APPROVED
GET  /api/v1/admin/golf-courses/pending
PUT  /api/v1/admin/golf-courses/{id}/approve
PUT  /api/v1/admin/golf-courses/{id}/reject
PUT  /api/v1/golf-courses/{id}             # Creator submits update (clone-based workflow)
PUT  /api/v1/admin/golf-courses/updates/{id}/approve  # Admin approves update
PUT  /api/v1/admin/golf-courses/updates/{id}/reject   # Admin rejects update
```

**Update Workflow (Clone-Based - Option A+):**
- Creator submits update → creates pending clone (original unchanged)
- Admin approves → clone replaces original, original soft-deleted
- Admin rejects → clone deleted, original unchanged
- No data loss during approval process
**Key DTOs:**
```python
class GolfCourseRequest(BaseModel):
    name: str = Field(min_length=3, max_length=200)
    country_code: str = Field(regex=r"^[A-Z]{2}$")
    course_type: Literal["STANDARD_18", "PITCH_AND_PUTT", "EXECUTIVE"]
    tees: list[TeeDTO] = Field(min_length=2, max_length=6)
    holes: list[HoleDTO] = Field(min_length=18, max_length=18)

    @field_validator('holes')
    def validate_stroke_index_unique(cls, holes):
        stroke_indices = [h.stroke_index for h in holes]
        if len(stroke_indices) != len(set(stroke_indices)):
            raise ValueError("Stroke indices must be unique (1-18)")
        return holes

    @field_validator('holes')
    def validate_total_par(cls, holes):
        total_par = sum(h.par for h in holes)
        if not (66 <= total_par <= 76):
            raise ValueError("Total par must be between 66 and 76")
        return holes
```

**Validations:** Exactly 18 holes, unique stroke indices 1-18, total par 66-76, 2-6 tees.

---

#### Sprint 2: Competition Scheduling (1.5 weeks) - 🔄 IN PROGRESS (Blocks 0-3 ✅ COMPLETED)

**Block 0: Clean Architecture Refactor - UoW Pattern Consistency (✅ COMPLETED: Jan 31, 2026)**
- **Issue**: Competition (14 use cases) and User (2 use cases) modules have explicit `await self._uow.commit()` calls
- **Problem**: Violates Unit of Work pattern - UoW context manager (`__aexit__`) should handle commits automatically
- **Files to modify**:
  - Competition: 14 use cases (activate, cancel, close, complete, create, delete, start, update, handle_enrollment, direct_enroll, request_enrollment, set_custom_handicap, cancel_enrollment, withdraw_enrollment)
  - User: 2 use cases (register_device, revoke_device)
- **Actions**:
  1. Remove all explicit `await self._uow.commit()` calls (9 already removed from Golf Course module)
  2. Update ~16-20 unit tests to remove `mock_uow.commit.assert_called_once()` assertions
  3. Update mock fixtures to simulate UoW `__aexit__` behavior (commit on success, rollback on exception)
- **Benefit**: 100% consistent Clean Architecture, automatic transaction management, less code duplication
- **Tests**: Update existing tests, verify 1,177/1,177 still passing
- **Time**: 3-4 hours
- **Related**: Golf Course module already completed (v2.0.1 - commit bfa7efa)

**Block 1: Competition ↔ GolfCourse Many-to-Many Relationship (✅ COMPLETED: Feb 1, 2026)**
- **Rationale**: Competitions can be played across multiple golf courses (multi-round tournaments)
- **Architecture**: Many-to-Many via `competition_golf_courses` association table
- **Migration**: Create `competition_golf_courses` table (id, competition_id, golf_course_id, display_order, created_at)
  - **Type Safety**: Mixed UUID types - `competition_id` uses CHAR(36) to match existing `competitions.id`, `golf_course_id` uses UUID(as_uuid=True) to match `golf_courses.id`
- **Domain Layer**:
  - New entity: `CompetitionGolfCourse` (id, golf_course_id, display_order)
  - Update `Competition` entity: add `_golf_courses: list[CompetitionGolfCourse]`
  - Business methods: `add_golf_course()`, `remove_golf_course()`, `reorder_golf_courses()`
  - Business rules:
    - DRAFT competitions can have 0+ courses
    - ACTIVE requires ≥1 course (all APPROVED)
    - Cannot modify courses after ACTIVATED
    - Golf course country must match competition location (main or adjacent)
    - Cannot delete golf course used in ACTIVE/IN_PROGRESS competitions
- **Application Layer**:
  - New use cases: AddGolfCourseToCompetition, RemoveGolfCourseFromCompetition, ReorderGolfCourses
  - Update: CreateCompetition (accept `golf_course_ids`), ActivateCompetition (validate all APPROVED)
  - New DTOs: CompetitionGolfCourseDTO, Add/Remove/Reorder request DTOs
- **Infrastructure**:
  - SQLAlchemy mapper: relationship with `cascade="all, delete-orphan"`, `order_by=display_order`
  - Repository: `find_by_id_with_golf_courses()` (eager loading), `find_active_competitions_using_course()`
- **API Endpoints** (4 new):
  ```
  POST   /api/v1/competitions/{comp_id}/golf-courses
  DELETE /api/v1/competitions/{comp_id}/golf-courses/{gc_id}
  PUT    /api/v1/competitions/{comp_id}/golf-courses/reorder
  GET    /api/v1/competitions/{comp_id}/golf-courses
  ```
- **Frontend Integration**:
  - Competition creation: multi-select golf courses (existing APPROVED)
  - Option to create new course request (PENDING) and attach to competition
  - Warning if competition has PENDING courses (cannot activate until approved)
  - UI to reorder courses (drag-and-drop)
- **Tests**: +64 tests ✅
  - Domain: 24 tests (13 CompetitionGolfCourseId + 11 CompetitionGolfCourse) ✅
  - Application: 26 tests (11 AddGolfCourse + 6 RemoveGolfCourse + 9 ReorderGolfCourses) ✅
  - Integration: 9 tests (4 API endpoints) ✅
  - Infrastructure: InMemoryGolfCourseRepository + InMemoryGolfCourseUnitOfWork ✅
- **Time**: 4 hours (Domain + Migration + Infrastructure + API stubs)
- **ADR**: ADR-034 (Competition-GolfCourse Many-to-Many Relationship) - PENDING
- **Commits**:
  - 7bfc8f5 - feat(domain): add CompetitionGolfCourse many-to-many relationship
  - 15e3e5a - feat(migration): add competition_golf_courses association table
  - 79dd6e4 - feat(infra): add CompetitionGolfCourse mapper and endpoints
  - 63dc494 - fix(mapper): add explicit property mappings for CompetitionGolfCourse
  - 25d54d3 - fix(migration): change competition_id to CHAR(36) to match existing schema
  - a51fe85 - feat(sprint2): complete Block 1 - M2M integration tests (9 tests + create_admin_user helper)

**Block 2: Code Quality Refactor - Exception Subclasses (✅ COMPLETED: Feb 2, 2026)**
- **Issue**: CodeRabbit #2 - Replace fragile string matching with exception subclasses
- **Files Modified**:
  - `src/modules/competition/domain/exceptions/competition_violations.py` (NEW - 8 subclasses)
  - `src/modules/competition/domain/exceptions/__init__.py` (NEW)
  - `src/modules/competition/domain/services/competition_policy.py` (refactored)
  - `src/modules/competition/application/use_cases/request_enrollment_use_case.py` (refactored)
  - `tests/unit/modules/competition/domain/services/test_competition_policy.py` (20 tests updated)
- **Results**:
  - ✅ 8 type-safe exception subclasses created
  - ✅ Eliminated fragile string matching (`if "already enrolled" in str(e)`)
  - ✅ 970/970 unit tests passing (100%)
  - ✅ Better DDD compliance + maintainability
- **Time**: 2.5 hours

**Block 3: Fix SBOM Submission to GitHub Dependency Graph (✅ COMPLETED: Feb 2, 2026)**
- **Issue**: Action `github/dependency-graph-submit-action@v1` doesn't exist (CI/CD failing)
- **Solution**: GitHub REST API `/repos/{owner}/{repo}/dependency-graph/snapshots` (official)
- **Files Modified/Created**:
  - `scripts/submit-sbom-to-github.sh` (NEW - 202 lines, REST API integration)
  - `.github/workflows/ci_cd_pipeline.yml` (uncommented + modified SBOM submission)
  - `docs/architecture/decisions/ADR-036-sbom-submission-rest-api.md` (NEW)
- **Results**:
  - ✅ Zero external dependencies (no third-party actions)
  - ✅ Full control over SBOM submission logic
  - ✅ Proper error handling + logging
  - ✅ `permissions: contents: write` enabled for Dependency Graph integration
  - ⏸️ Manual verification pending (requires merge to main)
- **Benefit**: Supply chain visibility, Dependabot integration, OWASP A08 compliance maintained
- **Time**: 2 hours
- **ADR**: ADR-036 (SBOM Submission via GitHub REST API)

**Block 4: Domain Layer - Round & Match Entities (✅ COMPLETED: Feb 5, 2026)**
- **New Value Objects (11)**:
  - `RoundId` (UUID) - Unique identifier for rounds
  - `MatchId` (UUID) - Unique identifier for matches
  - `TeamAssignmentId` (UUID) - Unique identifier for team assignments
  - `SessionType` (Enum): MORNING, AFTERNOON, EVENING
  - `MatchFormat` (Enum): SINGLES, FOURBALL, FOURSOMES (with `players_per_team()`)
  - `MatchStatus` (Enum): SCHEDULED, IN_PROGRESS, COMPLETED, WALKOVER
  - `RoundStatus` (Enum): PENDING_TEAMS, PENDING_MATCHES, SCHEDULED, IN_PROGRESS, COMPLETED (with `can_modify()`, `can_generate_matches()`)
  - `TeamAssignmentMode` (Enum): AUTOMATIC, MANUAL
  - `ScheduleConfigMode` (Enum): AUTOMATIC, MANUAL
  - `HandicapMode` (Enum): STROKE_PLAY (95%), MATCH_PLAY (100%) - for SINGLES rounds
  - `PlayMode` (Enum): STROKE_PLAY, MATCH_PLAY - Competition-level default
- **New Entities (3)**:
  - `Round`: id, competition_id, golf_course_id, round_date, session_type, match_format, status, handicap_mode, allowance_percentage
    - Session-based model: each Round = one session (MORNING/AFTERNOON/EVENING), not a full day
    - State machine: PENDING_TEAMS → PENDING_MATCHES → SCHEDULED → IN_PROGRESS → COMPLETED
    - Tees NOT at Round level (managed per player via Enrollment.tee_category)
  - `Match`: id, round_id, match_number, team_a_players[], team_b_players[], status
    - MatchPlayer (frozen VO): user_id, playing_handicap, tee_category, strokes_received[]
  - `TeamAssignment`: id, competition_id, mode, team_a_player_ids[], team_b_player_ids[]
    - Validations: balanced teams, no overlap, no duplicates
- **Domain Services (2)** (includes Block 8 PlayingHandicapCalculator - absorbed into Block 4):
  - `PlayingHandicapCalculator`: WHS formula `PH = (HI x (SR / 113) + (CR - Par)) x Allowance%`
    - Methods: calculate(), calculate_for_singles(), calculate_for_fourball(), calculate_for_foursomes()
    - TeeRating dataclass with WHS validation (CR 55-85, SR 55-155, Par 66-76)
  - `SnakeDraftService`: Serpentine team assignment (A,B,B,A,A,B pattern)
    - Methods: assign_teams(), validate_team_balance(), get_team_players()
  - `ScheduleGenerator` and `MatchGenerator`: Deferred to Block 6 (use case level)
- **Two-Tier Handicap System** (ADR-037):
  - Competition-level `PlayMode` sets tournament-wide default
  - Round-level `handicap_mode`/`allowance_percentage` can override per session
  - WHS defaults: Singles STROKE_PLAY 95%, MATCH_PLAY 100%, Fourball 90%, Foursomes 50%
- **Enrollment Enhancement**: Added `tee_category` field (TeeCategory from Golf Course module)
- **Business Rules**:
  - Teams must be assigned before generating matches
  - Teams must have equal player count
  - SINGLES: 1 player/team per match
  - FOURBALL/FOURSOMES: 2 players/team per match
  - Allowance percentage must be 50-100 in increments of 5
  - Only modifiable rounds: PENDING_TEAMS or PENDING_MATCHES status
- **Domain Events**: Deferred to Block 6 (emitted from use cases)
- **Tests**: 296 domain tests passing (14 test files: 9 VOs + 3 entities + 2 services)
- **Time**: ~8 hours
- **Commit**: 886f99f - feat(competition): implement Block 4 Domain Layer for Rounds & Matches
- **ADR**: ADR-037 (Two-Tier Handicap Architecture and Session-Based Round Model)

**Block 5: Infrastructure - Migrations & Mappers (⏳ PENDING: Feb 7-8, 2026)**
- **Migrations**:
  - `xxx_create_team_assignments_table.py`: competition_id (FK), mode, team_a_players (JSON), team_b_players (JSON)
  - `xxx_create_rounds_table.py`: id, competition_id (FK), golf_course_id (FK), date, session_type, match_format, tee_male_category, tee_female_category, status
  - `xxx_create_matches_table.py`: id, round_id (FK), match_number, team_a (JSON), team_b (JSON), handicap_strokes_given, strokes_received_by, status, result (JSON)
- **SQLAlchemy Mappers**:
  - `TeamAssignmentMapper`: JSON columns for player arrays
  - `RoundMapper`: relationships to Competition, GolfCourse
  - `MatchMapper`: JSON columns for team players with playing_handicap
- **Indexes**:
  - `ix_rounds_competition_date` (competition_id, date)
  - `ix_matches_round_id` (round_id)
  - `ix_matches_status` (status) - for live leaderboard queries
- **Repository Interfaces**:
  - `ITeamAssignmentRepository`: save, find_by_competition
  - `IRoundRepository`: save, find_by_id, find_by_competition, delete
  - `IMatchRepository`: save, find_by_id, find_by_round, update_status, delete
- **Repository Implementations**: SQLAlchemy + InMemory (tests)
- **Tests**: +20 integration tests (repository + mapper)
- **Time**: 6-8 hours

**Block 6: Application Layer - Use Cases & DTOs (⏳ PENDING: Feb 8-10, 2026)**
- **DTOs**:
  - `ConfigureScheduleRequestDTO`: mode (AUTO/MANUAL), days[], default_tee_categories
  - `ConfigureScheduleResponseDTO`: schedule preview with format_details
  - `AssignTeamsRequestDTO`: mode, manual_assignments (optional)
  - `AssignTeamsResponseDTO`: teams with players, average_handicap, balance_analysis
  - `CreateRoundRequestDTO`: date, session_type, match_format, golf_course_id, tee_categories
  - `GenerateMatchesRequestDTO`: mode, manual_pairings (optional)
  - `MatchDetailDTO`: full match info with playing_handicaps, strokes_received
  - `ScheduleResponseDTO`: complete schedule with days[], rounds[], matches[]
- **Use Cases** (11 total):
  1. `ConfigureScheduleUseCase`: Sets up competition schedule (auto/manual)
  2. `AssignTeamsUseCase`: Assigns players to Team A/B (snake draft/manual)
  3. `CreateRoundUseCase`: Creates individual round (manual mode only)
  4. `UpdateRoundUseCase`: Updates round details (date, course, tees)
  5. `DeleteRoundUseCase`: Removes round and its matches
  6. `GetScheduleUseCase`: Returns complete schedule with nested rounds/matches
  7. `GenerateMatchesUseCase`: Creates matches for a round (auto/manual pairing)
  8. `GetMatchDetailUseCase`: Returns match with full player details
  9. `ReassignMatchPlayersUseCase`: Changes players in a match
  10. `UpdateMatchStatusUseCase`: SCHEDULED → IN_PROGRESS → COMPLETED
  11. `DeclareWalkoverUseCase`: Records walkover result
- **Validation Rules**:
  - Competition must be in DRAFT state for configuration
  - Teams must be assigned before match generation
  - Cannot modify rounds/matches after competition is IN_PROGRESS
- **Tests**: +55 unit tests (use cases)
- **Time**: 10-12 hours

**Block 7: API Layer - Endpoints (⏳ PENDING: Feb 10-12, 2026)**
- **Schedule Configuration (1 endpoint)**:
  ```
  POST /api/v1/competitions/{comp_id}/schedule/configure
  ```
- **Team Assignment (1 endpoint)**:
  ```
  POST /api/v1/competitions/{comp_id}/teams/assign
  ```
- **Rounds (4 endpoints)**:
  ```
  POST   /api/v1/competitions/{comp_id}/rounds
  PUT    /api/v1/rounds/{round_id}
  DELETE /api/v1/rounds/{round_id}
  GET    /api/v1/competitions/{comp_id}/schedule
  ```
- **Matches (6 endpoints)**:
  ```
  POST   /api/v1/rounds/{round_id}/matches/generate
  GET    /api/v1/matches/{match_id}
  PUT    /api/v1/matches/{match_id}/players
  PUT    /api/v1/matches/{match_id}/status
  POST   /api/v1/matches/{match_id}/walkover
  DELETE /api/v1/matches/{match_id}
  ```
- **Authorization**:
  - Configure/Assign/Create/Update/Delete: Creator or Admin only
  - Get Schedule/Match: Any authenticated user (enrolled players)
- **Tests**: +24 integration tests (API endpoints)
- **Time**: 8-10 hours

**Block 8: Playing Handicap Calculator (✅ ABSORBED INTO BLOCK 4: Feb 5, 2026)**
- Implemented as `PlayingHandicapCalculator` domain service in Block 4
- WHS formula with Decimal precision and ROUND_HALF_UP rounding
- Format-specific methods: Singles (individual PH), Fourball (individual PH per player), Foursomes (team CH difference x allowance%)
- TeeRating dataclass with WHS validation ranges
- 30+ tests included in Block 4's 296 domain tests

**Schedule Auto-Generation Rules:**
| Sessions | Formats Generated (in order) |
|----------|------------------------------|
| 1 | Singles |
| 2 | Fourball → Singles |
| 3 | Foursomes → Fourball → Singles |
| 4 | Fourball → Foursomes → Fourball → Singles |
| 5 | Foursomes → Fourball → Foursomes → Fourball → Singles |
| 6+ | Alternates Fourball/Foursomes → Singles last |

**Snake Draft Algorithm:**
```
Players sorted by handicap: [4.2, 8.1, 12.3, 15.0, 18.2, 22.5, 25.0, 28.4]
Pick 1: Team A ← 4.2    Pick 2: Team B ← 8.1
Pick 3: Team B ← 12.3   Pick 4: Team A ← 15.0
Pick 5: Team A ← 18.2   Pick 6: Team B ← 22.5
Pick 7: Team B ← 25.0   Pick 8: Team A ← 28.4
Result: Balanced teams (~0.5 handicap difference)
```

**Sprint 2 Block 4-8 Summary:**
| Block | Description | Tests | Hours |
|-------|-------------|-------|-------|
| Block 4 | Domain (Entities, VOs, Services) ✅ | 296 | ~8h |
| Block 5 | Infrastructure (Migrations, Mappers, Repos) | +20 | 6-8h |
| Block 6 | Application (Use Cases, DTOs) | +55 | 10-12h |
| Block 7 | API (12 Endpoints) | +24 | 8-10h |
| Block 8 | Playing Handicap Calculator ✅ (absorbed into Block 4) | - | - |
| **Total** | | **+395** | **32-38h** |

**ADRs Nuevos:**
- **ADR-037:** Two-Tier Handicap Architecture and Session-Based Round Model (✅ Block 4)
- **ADR-038:** Schedule Configuration Modes (Automatic vs Manual) (⏳ Block 6)
- **ADR-039:** Match Format Business Rules (⏳ Block 6)

---

#### Sprint 3: Invitations System (1 week)

**Endpoints (5):**
```
POST /api/v1/competitions/{comp_id}/invitations        # By user ID
POST /api/v1/competitions/{comp_id}/invitations/by-email
GET  /api/v1/invitations/me                            # Pending
POST /api/v1/invitations/{invitation_id}/respond       # Accept/Decline
GET  /api/v1/competitions/{comp_id}/invitations        # Creator view
```

**Security:**
- Token: 256-bit (`secrets.token_urlsafe(32)`), SHA256 hash in DB
- Expiration: 7 days, Celery background task (every 6h)
- Auto-enrollment: ACCEPTED → Enrollment status APPROVED (bypasses approval)

**Email Templates:** Bilingual ES/EN, Mailgun

---

#### Sprint 4: Scoring System (2 weeks)

**Endpoints (4):**
```
POST /api/v1/matches/{match_id}/scores/holes/{hole_number}
GET  /api/v1/matches/{match_id}/scoring-view           # 3-tab view
POST /api/v1/matches/{match_id}/scorecard/submit
GET  /api/v1/matches/{match_id}/scorecard
```

**Dual Validation:**
```python
class ScoringValidator:
    @staticmethod
    def validate_dual_entry(player_score: int | None, marker_score: int | None) -> str:
        """Returns: 'match' | 'mismatch' | 'pending'"""
        if player_score is None or marker_score is None:
            return "pending"
        return "match" if player_score == marker_score else "mismatch"
```

**Match Play Calculator:**
```python
class MatchPlayCalculator:
    @staticmethod
    def calculate_standing(holes_data: list[HoleScoreDetail]) -> MatchStanding:
        """Net score = gross - strokes_received. Lower net wins hole."""
        # Returns: "Team A leads 2UP" | "All Square" | "Team B wins 3&2"
```

**Unified View:**
```python
class MatchScoringView(BaseModel):
    current_hole: int              # Next uncompleted hole
    hole_info: HoleScoreDetail     # Tab 1: Input
    scorecard: list[HoleScoreDetail]  # Tab 2: Scorecard
    match_standing: MatchStanding  # Tab 3: Leaderboard
    can_submit: bool               # True if 18/18 holes are validated
```

---

#### Sprint 5: Leaderboards & Optimization (1 week)

**Endpoints (2):**
```
GET /api/v1/competitions/{comp_id}/leaderboard       # Public, complete
GET /api/v1/competitions/{comp_id}/leaderboard/live  # Only IN_PROGRESS matches
```

**Optimizations:**
- DB Indexes: (competition_id, status), (match_id, hole_number)
- Redis cache (TTL 30s) for live matches
- Eager loading (selectinload) to prevent N+1 queries
- Target: < 200ms p95

**Response:**
```python
class LeaderboardResponse(BaseModel):
    team_a_standing: TeamStanding  # points, matches won/lost/halved
    team_b_standing: TeamStanding
    matches: list[MatchSummary]
    has_live_matches: bool
    last_updated: datetime
```

---

#### 🗄️ New Entities (13 total)

**Domain Layer:**
- `GolfCourse`, `Tee`, `Hole` - Golf Course Management (3 tables)
- `CompetitionGolfCourse` - Competition-GolfCourse Many-to-Many association (1 table)
- `Round`, `Match` - Scheduling (2 tables)
- `Invitation` - Invitation System (1 table)
- `HoleScore` - Score Annotation (1 table)

**Enums:**
- CourseType: STANDARD_18, PITCH_AND_PUTT, EXECUTIVE
- TeeCategory (7 values): CHAMPIONSHIP_MALE, AMATEUR_MALE, SENIOR_MALE, CHAMPIONSHIP_FEMALE, AMATEUR_FEMALE, SENIOR_FEMALE, JUNIOR
- ApprovalStatus: PENDING_APPROVAL, APPROVED, REJECTED
- MatchFormat, MatchStatus, InvitationStatus, ScoreStatus (v2.1.0)

---

#### ✅ Acceptance Criteria

**Functionality:**
- 34 endpoints implemented + Swagger docs
- Functional RBAC (ADMIN, CREATOR, PLAYER) using a simplified, table-less design
- Competition-GolfCourse many-to-many relationship with reordering
- Auto-calculated playing handicaps (WHS)
- Dual validation (player + marker)
- Public real-time leaderboard

**Testing:**
- ≥85% coverage
- 130+ tests (unit + integration)
- 0 failing in CI/CD

**Performance:**
- API p95 < 200ms
- Eager loading (joinedload/selectinload) + Redis cache
- Critical DB indexes (competition_golf_courses, rounds, matches)

**Security:**
- Authorization checks on all endpoints
- Pydantic validation
- Configured CORS

**Documentation:**
- Complete Swagger (descriptions, examples)
- 4 new ADRs (031, 032, 033, 034)
- 11 Alembic migrations

---

#### 🔄 Handoffs with Frontend

| Sprint | Backend Delivers | Frontend Consumes | Sync Point |
|--------|----------------|------------------|------------|
| Sprint 1 | RBAC + Golf Courses | User Management + Course Selector | ✅ Jan 31 |
| Sprint 2 (Block 0-3) | Competition-GolfCourse M2M + Code Quality | Multi-select courses + Reorder UI | ✅ Feb 4 |
| Sprint 2 (Block 4-8) | Schedule Config + Teams + Rounds + Matches | Schedule Wizard + Team Assignment + Match Generation | 🔄 Feb 13 |
| Sprint 3 | Invitations | Invitation Cards | Fri, Feb 27 |
| Sprint 4 | Scoring | 3 Tabs + Validation | Fri, Mar 13 |
| Sprint 5 | Leaderboards | Public Leaderboard + Polling | Fri, Mar 20 |

**Sprint 2 Block 4-8 Frontend Integration:**
1. **Schedule Configuration**: Toggle Auto/Manual, day picker, session selector per day
2. **Team Assignment**: Toggle Auto/Manual, drag-and-drop players to teams, handicap balance preview
3. **Round Management**: Create/edit/delete rounds, golf course + tee selector
4. **Match Generation**: Auto-generate or manual pairing, playing handicap display
5. **Match Status**: Start/complete matches, walkover declaration

**Protocol:** Backend deploys to dev → updates Swagger → notifies Frontend (Friday) → integration (Monday).

---

#### 🔗 Related ADRs

**Existing:**
- **ADR-020:** Competition Module Domain Design (v1.x baseline)
- **ADR-025:** Competition Module Evolution v2.0.0 (umbrella ADR - Jan 9, 2026)
- **ADR-026:** Playing Handicap WHS Calculation (Jan 9, 2026)

**New (Sprint 1):**
- **ADR-031:** Match Play Scoring Calculation (Jan 27, 2026)
- **ADR-032:** Golf Course Approval Workflow Details (Jan 27, 2026)
- **ADR-033:** Invitation Token Security and Auto-Enrollment (Jan 27, 2026)

**New (Sprint 2):**
- **ADR-034:** Competition-GolfCourse Many-to-Many Relationship (Feb 3, 2026)

---

### v2.1.0 - Compliance & Features (2-3 weeks)

**Goal:** GDPR compliance + UX improvements
**Note:** The RBAC implementation in v2.0.0 is a simplified, table-less design. Future work should build on this foundation.

**Features:**
1. **GDPR Compliance** (8-10h):
   - GET `/api/v1/users/me/export` (complete JSON)
   - DELETE `/api/v1/users/me` (soft delete)
   - Data anonymization, consent logging, retention policies (90 days)

2. **Audit Logging** (6-8h):
   - `AuditLog` model in DB (user_id, action, resource, changes, timestamp, ip)
   - 90-day retention, CSV/JSON export

3. **Avatar System** (4-6h):
   - `avatar_url` field, Cloudinary/S3 storage
   - PUT `/api/v1/users/me/avatar`, DELETE `/api/v1/users/me/avatar`
   - Validation: max 2MB, jpg/png/webp

4. **Unified Error Handling** (3-4h):
   - Centralized exception handlers
   - Standard format: `{"error": {"code": "...", "message": "...", "details": {}}}`
   - ErrorCode enum (40+ codes), i18n (ES/EN)

**Total:** ~21-28 hours

---

### v2.2.0 - AI & RAG Module (2-3 weeks)

**Goal:** Golf rules assistant chatbot

**Stack:** LangChain + Pinecone + OpenAI GPT-4o-mini | **Cost:** $1-2/month

**Features:**
- RAG chatbot with semantic search
- Only available if `competition.status == IN_PROGRESS`
- Dual-layer rate limiting: 10/day global, 3/day player, 6/day creator
- Redis cache (TTL 7 days, 80% hit rate expected)
- Pre-FAQs (20-30 hardcoded), temperature 0.3

**Architecture:**
```
src/modules/ai/
├── domain/           # Entities, VOs, Interfaces
├── application/      # Use Cases, DTOs, Ports
└── infrastructure/   # Pinecone, Redis, OpenAI, API
```

**Ports:** VectorRepository, CacheService, DailyQuotaService, LLMService

**Endpoints:**
- POST `/api/v1/competitions/{id}/ai/ask`
- GET `/api/v1/competitions/{id}/ai/quota`

**Tests:** 60+ tests (mocking OpenAI)

**Knowledge Base:** R&A Official Rules of Golf

---

### v3.0.0 - Major Release (BREAKING CHANGES) (4-6 months)

**Goal:** Scalability + Advanced Features

**Breaking Changes:**
- ❌ Remove tokens from response body (httpOnly cookies only)
- ❌ Remove support for Authorization headers (6-month deprecation)
- ❌ Deprecate API v1 → API v2

**Security:**
- OAuth 2.0 / Social Login (Google, Apple, GitHub)
- WebAuthn (Hardware Security Keys)
- Advanced Threat Detection (ML-based anomaly)
- SOC 2 Compliance preparation

**Features:**
- Advanced analytics and statistics
- USGA, Golf Australia integration
- Push notifications (Firebase)
- Payment system (Stripe)
- Global rankings
- Photo gallery (AWS S3 + CloudFront)

**Infrastructure:**
- Kubernetes deployment
- Blue-green deployments
- Auto-scaling (HPA)
- CDN for static assets
- Database replication + read replicas
- Multi-region deployment

---

## 📅 Recommended Timeline

```
2026 Q1  │ ✅ v1.13.0 - Security Hardening (COMPLETED)
          │ ✅ v1.13.1 - Device Detection + HTTP Security (COMPLETED)
          │ ✅ v2.0.0 - RBAC Foundation (Jan 29, 2026) (COMPLETED)
          │ ⭐ v2.0.1 - Competition Module Evolution (Jan 27 - Mar 24) ← IN PROGRESS
2026 Q2  │ v2.1.0 - Compliance (GDPR, Audit Logging, Avatars)
          │ v2.2.0 - AI & RAG Module (Golf Rules Assistant)
2026 Q3  │ v2.1.1 - WebSocket, Custom points
          │ v2.1.2 - Advanced Stats, Export PDF
2026 Q4+ │ v3.0.0 - Major Release (planning + development)
```

---

## 🔗 References

**Documentation:**
- **ADRs:** `docs/architecture/decisions/ADR-*.md` (37 total ADRs)
- **CHANGELOG:** `CHANGELOG.md` (detailed change history)
- **CLAUDE:** `CLAUDE.md` (complete project context)
- **Frontend ROADMAP:** `../RyderCupWeb/ROADMAP.md`
- **DATABASE_ERD:** `docs/DATABASE_ERD.md`

**Standards:**
- **OWASP Top 10:** https://owasp.org/www-project-top-ten/
- **ASVS:** https://owasp.org/www-project-application-security-verification-standard/
- **WHS:** https://www.usga.org/handicapping.html
- **R&A Rules:** https://www.randa.org/en/rog/the-rules-of-golf

**Key ADRs for v2.0.0:**
- ADR-020: Competition Module Domain Design (baseline)
- ADR-025: Competition Module Evolution v2.0.0 (umbrella)
- ADR-026: Playing Handicap WHS Calculation
- ADR-031: Match Play Scoring Calculation
- ADR-032: Golf Course Approval Workflow Details
- ADR-033: Invitation Token Security

---

## 📜 Completed Version History

### v1.13.1 - Current Device Detection + HTTP Security (Jan 18, 2026) ✅

**Changes:**
- `is_current_device` field in GET /users/me/devices (UX improvement)
- Centralized helper `http_context_validator.py` (306 lines)
- IP spoofing prevention with `TRUSTED_PROXIES` whitelist
- Sentinel validation (rejects "unknown", "", localhost)
- +36 HTTP security tests (100% passing)
- **OWASP:** 9.2 → 9.4 (+0.2) - A01(10/10), A03(10/10)

---

### v1.13.0 - Security Hardening (Jan 9, 2026) ✅

**Features:**
1. **Account Lockout:** Lock after 10 failed attempts, auto-unlock in 30 min, manual unlock endpoint
2. **CSRF Protection:** Triple layer (header, cookie, SameSite), 256-bit token, middleware
3. **Password History:** Prevents reuse of last 5 passwords, bcrypt hashes, GDPR compliant
4. **Device Fingerprinting:** SHA256 fingerprint, list/revoke devices, soft delete, auto-register on login/refresh

**Tests:** 905 → 1,021 (+116 tests)
**OWASP:** 8.5 → 9.2 (+0.7)
**ADRs:** ADR-027, ADR-028, ADR-029, ADR-030

---

### v1.12.1 - Snyk Code SAST (Jan 5, 2026) ✅

- Snyk Code (SAST) in CI/CD pipeline
- Detection: SQL Injection, XSS, Hardcoded secrets, Path Traversal, Weak Crypto
- Separate reports: dependencies + code
- Artifacts retention: 30 days

---

### v1.12.0 - Snyk Vulnerability Fixes (Jan 3, 2026) ✅

- 6 CVEs resolved: authlib, setuptools, zipp, marshmallow
- Snyk integration in CI/CD (severity: HIGH)
- Tests: 905/905 (100%)

---

### Previous Versions (v1.0.0 - v1.11.0)

| Version | Date | Main Features |
|---------|------|---------------|
| **v1.11.0** | Dec 26, 2025 | Password Reset System (256-bit token, bilingual emails, +51 tests) |
| **v1.10.0** | Nov 30, 2025 | CI/CD Pipeline GitHub Actions (7 parallel jobs, Mypy, Gitleaks) |
| **v1.9.2** | Nov 25, 2025 | Cognitive complexity refactoring (competition_routes.py) |
| **v1.9.0** | Nov 25, 2025 | Increased Enrollment test coverage (7 use cases) |
| **v1.8.1** | Nov 25, 2025 | BREAKING: Competitions now include `countries` field (array) |
| **v1.8.0** | Nov 24, 2025 | Security Enhancements (httpOnly Cookies, Refresh Tokens, Rate Limiting, CORS, Security Headers, Logging, Correlation IDs, Validation, Sentry) |
| **v1.7.0** | Nov 23, 2025 | User Nationality, Nested Creator, My Competitions Filter, Search Parameters |
| **v1.6.4** | Nov 22, 2025 | Dual format support: `number_of_players` → `max_players` |
| **v1.6.0** | Nov 18, 2025 | Competition Module REST API (20 endpoints: 10 Competition + 8 Enrollment + 2 Countries) |
| **v1.5.0** | Nov 18, 2025 | Competition Module Infrastructure (Alembic migrations: 4 tables + 166 countries + 614 borders) |
| **v1.3.0** | Nov 18, 2025 | Competition Module Domain + Application (173 tests, 11 domain events) |
| **v1.2.0** | Nov 14, 2025 | Email Verification (24 tests, Mailgun integration) |
| **v1.1.0** | Nov 12, 2025 | Email Verification System (unique tokens, bilingual templates) |
| **v1.0.0** | Nov 1, 2025 | Clean Architecture + DDD, User Module, JWT Auth, Handicap RFEG, 420 tests |

**See full details:** `CHANGELOG.md`

---

**Next Review:** v2.0.1 Sprint 1 (Feb 7, 2026)
**Owner:** Backend Team