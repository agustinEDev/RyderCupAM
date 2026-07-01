# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased] — feature/scoring-improvements

### Fixed

**Scoring — Best Ball Player Determinism (FOURBALL)**

- `SQLAlchemyHoleScoreRepository.find_by_match()`: Added secondary `ORDER BY _player_user_id ASC` to guarantee consistent row order within each hole. Previously, when two players on the same team had equal net scores, PostgreSQL could return their rows in non-deterministic physical order after updates/vacuums, causing `find_best_ball_player()` to return a different player on each request.
- `ScoringService.find_best_ball_player()`: When two players on the same team tie on net score, the method now returns **both player IDs** (as a list) instead of a single ID. The DTO field `best_ball_player_a` / `best_ball_player_b` becomes a list to support the "Nombre1 y Nombre2" display in the frontend.

**Scoring — Leaderboard Result for Halved Matches**

- `calculate_match_result()`: When a match finishes AS (All Square), `winner` is now set to `"HALVED"` and `score` to `"AS"`. The frontend was previously displaying "Equipo X gana AS" because a non-empty `winner` string always triggered the `wins` translation key.

### Added

**Competition — Playing Handicap Limit**

- New optional field `max_playing_handicap: int | None` on the `Competition` entity. When set, `PlayingHandicapCalculator.calculate()` caps the result at this value before returning it.
- Alembic migration: adds nullable column `max_playing_handicap INTEGER` to `competitions` table.
- `CompetitionRequestDTO` / `CompetitionResponseDTO`: includes new field with validation `ge=1, le=54`.
- `CreateCompetitionUseCase` / `UpdateCompetitionUseCase`: propagate the new field.
- API: `POST /api/v1/competitions` and `PUT /api/v1/competitions/{id}` accept `max_playing_handicap`.

**Admin — Full Access to Scoring and Match Actions**

- All scoring routes now accept an admin user regardless of whether they are a player in the match. Check updated from "user must be in match" to "user must be in match OR is_admin".
- Affected routes: `GET /scoring-view`, `POST /scores/holes/{n}`, `POST /scorecard/submit`, `PUT /concede`.

---

## [2.0.16] - 2026-06-19

### Fixed

**Scoring — Match Play Calculation (SINGLES)**

- **SINGLES differential handicap**: `GenerateMatchesUseCase._build_singles_match_players()` now applies the WHS differential approach for Match Play, identical to FOURBALL and FOURSOMES. Only the higher-PH player receives strokes (the difference between both PHs), allocated on the hardest holes (lowest SI first). Previously both players received their individual PHs, causing strokes to cancel out on shared holes and fall on the wrong (less important) holes.
- Individual Playing Handicap values are preserved in `MatchPlayer.playing_handicap` for scorecard display; only `strokes_received` reflects the differential.

**Leaderboard — Points showing 0 for completed matches**

- `GetLeaderboardUseCase`: Added defensive fallback — when a completed match has `winner=None` (invalid stored result), the use case now recomputes the result from hole scores via `_compute_decided_result()`. Prevents 0-point totals caused by manual match completion with an empty/invalid result.
- `UpdateMatchStatusUseCase._handle_complete()`: Now validates that `result.winner` is `"A"`, `"B"`, or `"HALVED"` before persisting. Raises `InvalidActionError` for any other value, preventing corrupt results from being stored.

### Changed

- `HoleScore.MAX_SCORE`: Raised from 9 to 15 to support scores above 9 (accessible via the "Other..." option in the frontend number pad).
- `SubmitHoleScoreBodyDTO`: Updated `own_score` and `marked_score` field validation from `le=9` to `le=15`.

### Added

**Backward Competition State Transitions**

- **2 new domain events**: `CompetitionRevertedToClosedEvent`, `CompetitionEnrollmentsReopenedEvent`
- **2 new entity methods**: `Competition.revert_to_closed()` (IN_PROGRESS → CLOSED), `Competition.reopen_enrollments()` (CLOSED → ACTIVE)
- **2 new use cases**: `RevertCompetitionStatusUseCase`, `ReopenEnrollmentsUseCase`
- **4 new DTOs**: Request/Response for each backward transition
- **2 new API endpoints**:
  - `PUT /api/v1/competitions/{id}/revert-status` — Revert to fix schedule issues
  - `POST /api/v1/competitions/{id}/reopen-enrollments` — Reopen to add/remove players
- **29 new tests**: 16 CompetitionStatus VO + 6 revert use case + 6 reopen use case + 4 integration + 1 entity test
- **CompetitionStatus VO**: Added backward transitions (IN_PROGRESS → CLOSED, CLOSED → ACTIVE)

**Sprint 4: Live Scoring + Leaderboard (8 bloques)**

**Domain Layer**

- **HoleScore entity**: New entity with dual validation (own_score + marker_score → PENDING/MATCH/MISMATCH)
  - Pre-created 18 empty HoleScores per player when match starts (START)
  - Fields: own_score, marker_score, own_submitted, marker_submitted, strokes_received, net_score, validation_status
  - Factory methods: `create()`, `reconstruct()`
  - Business methods: `set_own_score()`, `set_marker_score()`, `recalculate_validation()`, `calculate_net_score()`
- **3 New Value Objects**: `HoleScoreId` (UUID), `ValidationStatus` (PENDING/MATCH/MISMATCH), `MarkerAssignment` (frozen dataclass)
- **MatchStatus.CONCEDED**: New terminal state for match concession, `can_concede()`, updated `is_finished()`
- **ScoringService** (domain service): Pure domain logic for match play scoring
  - `generate_marker_assignments()`: reciprocal (Singles), crossed (Fourball), per-team (Foursomes)
  - `get_affected_player_ids()` / `get_affected_marked_player_ids()`: Foursomes team expansion
  - `calculate_hole_winner()`: net score comparison per format (Singles 1v1, Fourball best ball, Foursomes single ball)
  - `calculate_match_standing()`: N up with M remaining, halved detection
  - `is_match_decided()`: early termination check
  - `format_decided_result()`: "3&2", "1UP", "AS" formatting
  - `calculate_ryder_cup_points()`: team points from match result
- **Match entity extensions**: `marker_assignments`, `scorecard_submitted_by`, `is_decided`, `decided_result` fields + 8 new methods (`concede()`, `submit_scorecard()`, `mark_decided()`, etc.)
- **3 Domain Events**: `HoleScoreSubmittedEvent`, `ScorecardSubmittedEvent`, `MatchConcededEvent`
- **HoleScoreRepositoryInterface**: `add()`, `update()`, `add_many()`, `find_by_match()`, `find_by_match_and_hole()`, `find_one()`, `find_by_match_and_player()`, `delete_by_match()`

**Application Layer**

- **~16 DTOs** in `scoring_dto.py`: `SubmitHoleScoreBodyDTO`, `ConcedeMatchBodyDTO`, `ScoringViewResponseDTO`, `SubmitScorecardResponseDTO`, `LeaderboardResponseDTO` + sub-DTOs
- **5 Use Cases**:
  - `GetScoringViewUseCase`: Unified scoring view (scores, standing, marker assignments, decided status)
  - `SubmitHoleScoreUseCase`: Register own_score + marker_score with Foursomes team expansion, auto-recalculate validation and standing, granular scorecard locking
  - `SubmitScorecardUseCase`: Validate all holes MATCH, submit scorecard, auto-complete match/round
  - `GetLeaderboardUseCase`: Team points, match standings, player names resolved via user repo
  - `ConcedeMatchUseCase`: Players concede own team, creator can concede any team
- **SearchUsersUseCase**: Autocomplete search by partial name (max 10 results)
- **5 New Exceptions**: `NotMatchPlayerError`, `ScorecardNotReadyError`, `ScorecardAlreadySubmittedError`, `MatchNotScoringError`, `InvalidHoleNumberError`

**Infrastructure Layer**

- **Alembic migration**: `hole_scores` table + 4 new columns on `matches` (marker_assignments JSONB, scorecard_submitted_by JSONB, is_decided BOOLEAN, decided_result JSONB)
- **TypeDecorators**: `HoleScoreIdDecorator`, `ValidationStatusDecorator`, `MarkerAssignmentsJsonType`, `ScorecardSubmittedByJsonType`
- **SQLAlchemy mapper**: Imperative mapping for HoleScore + extended Match mapping
- **HoleScoreRepository**: SQLAlchemy implementation with private attr queries
- **CompetitionUnitOfWork**: Extended with `hole_scores` repository property
- **5 Scoring endpoints** in `scoring_routes.py`:
  - `GET /matches/{match_id}/scoring-view`
  - `POST /matches/{match_id}/scores/holes/{hole_number}`
  - `POST /matches/{match_id}/scorecard/submit`
  - `GET /competitions/{competition_id}/leaderboard`
  - `PUT /matches/{match_id}/concede` — Dedicated concede endpoint with Pydantic `ConcedeMatchBodyDTO`
- **1 User endpoint** in `user_routes.py`:
  - `GET /users/search-autocomplete` — Partial name search with max 10 results
- **Match generation integration**: Auto-generates marker_assignments via ScoringService
- **Match start integration**: Pre-creates 18 HoleScore records per player with precalculated `strokes_received`
- **6 New DI providers** in `dependencies.py`

### Changed

- **Match entity**: Added scoring-related fields and methods (marker_assignments, scorecard_submitted_by, is_decided, decided_result)
- **MatchStatus enum**: Added CONCEDED state
- **CompetitionUnitOfWorkInterface**: Added `hole_scores` property
- **GenerateMatchesUseCase**: Now generates marker_assignments via ScoringService
- **UpdateMatchStatusUseCase**: Pre-creates HoleScores on START with explicit team loops (no fallback)
- **UserRepositoryInterface**: Added `search_by_partial_name()` method for autocomplete

### Fixed

- **Scorecard locking (granular, silent skip)**: After submitting scorecard, own_score is silently ignored (marker_score still editable); after marked player submits, marker_score is silently ignored (own_score still editable)
- **Invitation domain events**: Defensive `add_domain_event()` / `get_domain_events()` / `clear_domain_events()` — prevents `AttributeError` when entity is loaded from DB (SQLAlchemy `__new__` bypasses `__init__`)
- **Competition property names**: Use `team_1_name`/`team_2_name` instead of `team_a_name`/`team_b_name` in scoring use cases
- **Leaderboard DetachedInstanceError**: DTO construction moved inside `async with self._uow:` block
- **Leaderboard duplicate DB calls**: Cached matches per round to avoid calling `find_by_round()` twice
- **Leaderboard match_format None check**: Guard against missing `MatchFormat` before entering scoring path
- **Scoring view holes ordering**: Sort `golf_course.holes` by `h.number` before creating DTOs
- **Net score None filter**: Filter out `None` values from `team_a_nets`/`team_b_nets` in all 3 scoring use cases
- **Match decided validation**: `_check_decided` now uses `ValidationStatus.MATCH` (not `own_submitted and marker_submitted`) to avoid counting mismatched holes
- **Marked player validation**: `SubmitHoleScoreUseCase` validates `marked_player_id` is a match participant
- **Round null check**: `SubmitHoleScoreUseCase` checks `round_entity` exists before accessing `match_format`
- **CORS/CSRF middleware ordering**: Swapped middleware registration order so CORS headers appear on CSRF rejection responses
- **Golf course holes deletion**: Fixed approval workflow losing holes/tees by checking collection changes
- **deploy-db.sh**: Added 60s timeout to unbounded `until` loop for pod creation

### Testing

- **1,873 unit tests passing** (100%) — +224 tests from Sprint 4
- **252 integration tests** — +16 scoring E2E tests
- New test files: `test_hole_score.py`, `test_scoring_service.py`, `test_match_scoring.py`, `test_scoring_events.py`, `test_scoring_dto.py`, `test_scoring_use_cases.py`, `test_scoring_mappers.py`, `test_scoring_endpoints.py`

### Refactored

- **Clean Architecture Compliance**: Resolved 12/15 DDD violations (90% → 97% compliance)
  - Remove `@reconstructor` from domain — use SQLAlchemy event listeners in infrastructure
  - Encapsulate Competition (13 attrs) and Enrollment (9 attrs) entities with private attrs + properties
  - Move business logic to domain: `Competition.reorder_golf_courses()`, `GolfCourse.apply_update()`, `PlayingHandicapCalculator.compute_strokes_received()`, `ScheduleFormatService.build_format_sequence()`
  - Inject domain services via DI: `SnakeDraftService`, `PlayingHandicapCalculator`, `ScheduleFormatService`
  - Split `competition_routes.py` (1627 lines) → 3 focused route files + `CompetitionDTOMapper` moved to application layer
  - Fix `team_assignment` TypeDecorator: `String(20)` → `TeamAssignmentModeDecorator`
  - Centralize 10 Golf Course DI functions from routes to `dependencies.py`
  - Centralize duplicated exceptions: `MatchNotFoundError`, `CompetitionNotDraftError`, `InsufficientPlayersError`
  - Add `max_players` constructor validation (MIN=2, MAX=100)
  - Simplify `reassign_match_players_use_case` — extract helper methods, remove `noqa: PLR0915`

### Removed

- `docs/DDD_CLEAN_ARCHITECTURE_VIOLATIONS.md` — all actionable violations resolved, report no longer needed

## [2.0.8] - 2026-02-09 (Support Module + Contact Form)

### Added

- **Support Module**: New `POST /api/v1/support/contact` endpoint — public contact form that creates GitHub Issues via REST API
- **GitHub Issues Integration**: Category-to-label mapping (BUG→bug, FEATURE→enhancement, QUESTION→question, OTHER→other)
- **Clean Architecture**: Full module structure (domain/application/infrastructure) with IGitHubIssueService port/adapter pattern
- **Input Sanitization**: All contact form inputs sanitized via existing `sanitize_html()` before creating issues
- **K8s restart script**: `k8s/scripts/restart-cluster.sh` — reloads ConfigMaps/Secrets and restarts deployments without rebuilding images (supports `--api`, `--front`, `--db`, `--all`)
- +25 unit tests (ContactCategory enum, ContactRequestDTO validation, SubmitContactUseCase with mocked service)

### Changed

- **CSRF Exemption**: Added `/api/v1/support/contact` to CSRF exempt paths (public endpoint, no session)
- **Settings**: Added `GH_ISSUES_TOKEN` and `GITHUB_ISSUES_REPO` environment variables
- **Dependencies**: Added `get_github_issue_service()` and `get_submit_contact_use_case()` DI providers

### Security

- **Rate Limiting**: Contact endpoint limited to 3 requests/hour per IP
- **No Authentication Required**: Public endpoint, consistent with frontend contact page
- **OWASP Score**: Maintained at 9.4/10

### Testing

- **1,598 tests passing** (100%) — +25 tests from Support Module

## [2.0.7] - 2026-02-08 (CIDR Proxy Support + Hotfixes)

### Added

- **CIDR Notation for TRUSTED_PROXIES**: Subnet matching support (e.g., `10.0.0.0/8`, `172.16.0.0/12`) for cloud infrastructure proxy validation
- +24 unit tests for CIDR matching in HTTP context validator

### Fixed

- **SBOM Submission**: Corrected GitHub API payload format for dependency snapshot submission (`submit-sbom-to-github.sh`)
- **GPG Verification**: CI/CD pipeline now correctly handles GitHub web-flow squash merge commits (skips GPG check for `noreply@github.com` committer)
- **CodeQL Security**: Redacted sensitive trusted proxy configuration values from security log messages
- **Golf Course `approval_status`**: Include `approval_status` in `GolfCourseDetailDTO` responses to allow frontend activation of competitions; prevents defaulting to `PENDING_APPROVAL` when the field is missing from the DTO serialization

### Security

- **OWASP Score**: Maintained at 9.4/10
- Trusted proxy validation now supports CIDR ranges for Render/cloud infrastructure compatibility

## [2.0.6] - 2026-02-07 (TeeCategory Refactoring + Deploy Scripts)

### Changed

**⛳ TeeCategory Refactoring (7→5 + Gender)**
- `TeeCategory` reduced from 7 gender-combined values to 5 neutral difficulty levels: `CHAMPIONSHIP`, `AMATEUR`, `SENIOR`, `FORWARD`, `JUNIOR`
- New shared `Gender` enum (`MALE`/`FEMALE`) in `src/shared/domain/value_objects/gender.py`
- `Tee` entity gains nullable `gender` field; `GolfCourse` validates 2-10 tees with unique `(category, gender)` pairs
- `User` entity gains nullable `gender` field for automatic tee resolution at match generation
- `MatchPlayer` VO gains `tee_gender` field for match-level tee tracking
- Match generation auto-resolves tee using `(enrollment.tee_category, user.gender)` with null fallback
- Enrollment DTOs now expose `tee_category` selection for player preference
- Alembic migration `c3d5e7f9a1b2` for schema changes

### Added

- **Enrollment tee_category API**: `request_enrollment` and `direct_enroll_player` endpoints accept optional `tee_category`
- **GenderDecorator TypeDecorator**: SQLAlchemy TypeDecorator for Gender enum in User mapper
- **Deploy Scripts** (`k8s/scripts/`): `deploy-cluster.sh`, `deploy-api.sh`, `deploy-front.sh`, `deploy-db.sh` for Kind cluster automation
- **imagePullPolicy: Never**: Fixed Kubernetes deployments for Kind image loading

### Fixed

- **User Mapper GenderDecorator**: Fixed `AttributeError: 'str' has no attribute 'value'` in generate_matches by replacing `String(10)` with `GenderDecorator()` TypeDecorator

### Testing

- **1,306 tests passing** (100%) — +24 tests from TeeCategory refactoring and CIDR support

## [2.0.5] - 2026-02-06 (Sprint 2 Complete - Rounds, Matches & Teams)

### Added

**Sprint 2: Competition Scheduling - Complete (Blocks 0-8)**

**Block 4: Domain Layer - Rounds & Matches**

- **3 New Entities**:
  - `Round`: Session-based tournament round with state machine (PENDING_TEAMS → PENDING_MATCHES → SCHEDULED → IN_PROGRESS → COMPLETED)
  - `Match`: Tournament match with team handicap calculations and state transitions
  - `TeamAssignment`: Balanced team distribution with validation (equal sizes, no overlap)

- **11 New Value Objects**:
  - IDs: `RoundId`, `MatchId`, `TeamAssignmentId` (UUID-based)
  - Enums: `SessionType` (MORNING/AFTERNOON/EVENING), `MatchFormat` (SINGLES/FOURBALL/FOURSOMES), `MatchStatus`, `RoundStatus`, `TeamAssignmentMode` (AUTOMATIC/MANUAL), `ScheduleConfigMode`, `HandicapMode` (STROKE_PLAY/MATCH_PLAY), `PlayMode` (SCRATCH/HANDICAP)
  - `MatchPlayer`: Frozen VO with playing handicap and strokes received per hole

- **2 Domain Services**:
  - `PlayingHandicapCalculator`: WHS formula `PH = (HI x (SR/113) + (CR-Par)) x Allowance%` with format-specific calculations (Singles, Fourball, Foursomes)
  - `SnakeDraftService`: Serpentine team balancing algorithm (A,B,B,A,A,B pattern)

- **Two-Tier Handicap System**: Competition-level `PlayMode` (SCRATCH/HANDICAP) default + Round-level `HandicapMode` (STROKE_PLAY/MATCH_PLAY)/`allowance_percentage` override with WHS-compliant defaults (Singles 95-100%, Fourball 90%, Foursomes 50%)
- **ADR-037**: Two-Tier Handicap Architecture and Session-Based Round Model

**Block 5: Infrastructure - Migrations & Mappers**

- **Migration** `a7f3b2c8d4e1`: 3 new tables (`rounds`, `matches`, `team_assignments`) with indexes
- **Migration** `b9e4f1a3c7d2`: HandicapSettings → PlayMode refactor (rename column + convert values)
- **SQLAlchemy Mappers**: TypeDecorators for IDs (CHAR(36) ↔ UUID VOs), Enums (string ↔ enum), JSONB (MatchPlayers, UserIds)
- **Repositories**: SQLAlchemy + InMemory implementations for Round, Match, TeamAssignment
- **Unit of Work**: CompetitionUnitOfWork expanded to 6 repositories

**Block 6: Application Layer - Use Cases & DTOs**

- **~30 DTOs** in `round_match_dto.py`: Request/Response/Body DTOs for all 11 use cases + shared response DTOs
- **11 Use Cases**:
  - CRUD: CreateRound, UpdateRound, DeleteRound
  - Reading: GetSchedule (grouped by day), GetMatchDetail
  - Teams: AssignTeams (snake draft/manual), GenerateMatches (with PlayingHandicapCalculator), ConfigureSchedule
  - Transitions: UpdateMatchStatus (START/COMPLETE), DeclareWalkover, ReassignMatchPlayers (with handicap recalculation)
- **Cross-module integration**: AssignTeams, GenerateMatches, ReassignMatchPlayers use UserRepository and/or GolfCourseRepository

**Block 7: API Layer - 11 Endpoints**

- **New file**: `round_match_routes.py` with 11 REST endpoints
- **Rounds**: POST (create), PUT (update), DELETE, GET (schedule)
- **Matches**: GET (detail), PUT (status), POST (walkover), PUT (players)
- **Teams & Generation**: POST (assign teams), POST (generate matches), POST (configure schedule)
- **11 DI providers** in `dependencies.py` (8 UoW-only + 3 cross-module)
- **Rate limiting**: POST/PUT/DELETE 10/min, GET 20/min
- **Exception mapping**: 404 (NotFound), 403 (NotCreator), 400 (business errors)

**Other Additions**

- **Country Code Filter**: `GET /api/v1/golf-courses?country_code=ES` filters approved golf courses by country ISO code
- **Enhanced Golf Course Response**: Added `course_type` and `total_par` fields to `GET /api/v1/competitions/{id}/golf-courses` endpoint

### Changed (Sprint 2)

- `Enrollment` entity: Added `tee_category` field for player tee assignment
- `HandicapSettings` replaced with `PlayMode` enum (breaking API change: `handicap_type` + `handicap_percentage` → `play_mode`)
- `value_objects/__init__.py`: Updated exports with 11 new value objects
- `services/__init__.py`: Added PlayingHandicapCalculator and SnakeDraftService exports
- `entities/__init__.py`: New package init with Round, Match, TeamAssignment exports
- `dependencies.py`: 11 new DI providers for round/match/team use cases
- `main.py`: Registered `round_match_routes` router

### Fixed

- **Competition Golf Courses Endpoint**: Fixed 500 error on `GET /api/v1/competitions/{id}/golf-courses`
  - Corrected mapper initialization order for cross-module relationships
  - Added explicit eager loading for golf course tees and holes
  - Fixed Tee/Hole attribute access (`.category` instead of `.id`, `.number` instead of `.hole_number`)
- **CSRF Exemptions**: Exempted `refresh-token` and `logout` endpoints from CSRF validation
  - `refresh-token`: Protected by httpOnly cookie, CSRF token expires with access token
  - `logout`: Session termination has low security risk (worst case: forced logout)
- **Country Code Filter**: Fixed TypeDecorator compatibility by converting string to CountryCode VO

### Testing

- **1,282 unit tests passing** (100%) — +422 tests from Sprint 2 Blocks 4-7
  - Block 4: 296 domain tests (14 files: 3 entities + 2 services + 9 VOs)
  - Block 5: 52 infrastructure tests (migration, mappers, repositories, UoW)
  - Block 6: 74 application tests (12 DTO + 62 use case)
  - Block 7: 0 regressions on full suite

### Security

- **CSRF Configuration**: Two new exempt paths added with security rationale documented
- **OWASP Compliance**: Maintained - exemptions follow defense-in-depth principle (httpOnly cookies as primary protection)

## [2.0.4] - 2026-02-04 (Cookie-Based Device Identification)

### Added

**🍪 Cookie-Based Device Identification** (OWASP A01 - Session Management)
- **Primary Change**: Device identification now uses persistent httpOnly cookie instead of IP-based fingerprinting
- **Problem Solved**: Dynamic IPv6 rotation (common with Cloudflare/ISPs) no longer creates duplicate device records
- **Cookie Settings**: `device_id` cookie with 1-year expiration, httpOnly, secure, samesite=lax
- **New Repository Method**: `find_by_id_and_user()` for cookie-based device lookup with ownership validation
- **New Entity Method**: `update_ip_address()` for audit trail updates when IP changes
- **DTO Updates**:
  - `RegisterDeviceRequestDTO`: Added `device_id_from_cookie` field
  - `RegisterDeviceResponseDTO`: Added `set_device_cookie` boolean
  - `LoginResponseDTO`: Added `device_id`, `should_set_device_cookie`
  - `RefreshAccessTokenResponseDTO`: Added `device_id`, `should_set_device_cookie`
  - `ListUserDevicesRequestDTO`: Added `device_id_from_cookie`
- **Cookie Handler**: New functions `set_device_id_cookie()`, `get_device_id_cookie_name()`, `delete_device_id_cookie()`
- **ADR-030 Updated**: Documents evolution from fingerprint-based (v1.13.0) to cookie-based (v2.0.4)

### Changed

**🔄 RegisterDeviceUseCase Rewritten**
- Cookie-first identification: If `device_id_from_cookie` present, lookup by ID instead of fingerprint
- Fingerprint now used only for generating `device_name` (browser/OS detection)
- IP address stored for audit trail only, not for identification
- Returns `set_device_cookie=True` when new device created (caller must set cookie)

**🔄 ListUserDevicesUseCase Simplified**
- `is_current_device` determined by cookie match instead of fingerprint comparison
- More reliable current device detection (no false negatives from IP changes)

**🔄 Auth Routes Updated**
- Login endpoint reads `device_id` cookie, passes to use case, sets cookie on new device
- Refresh token endpoint follows same pattern
- Device routes pass `device_id_from_cookie` for accurate `is_current_device`

### Fixed - Security Hotfixes (Feb 2-4, 2026)

**🔒 Device Fingerprinting IP Normalization** (v2.0.3)
- Normalize IPs to /24 (IPv4) or /64 (IPv6) for consistent device fingerprinting
- Prevents false logout when user's IP rotates within same ISP network (e.g., Cloudflare rotation)
- Formula: `SHA256(user_agent + "|" + normalized_network_ip)`
- Example: `192.168.1.100` and `192.168.1.205` both normalize to `192.168.1.0`

**🌐 Cloudflare Headers Support** (v2.0.3)
- Use `CF-Connecting-IP` header when behind Cloudflare proxy (priority 1)
- Fallback chain: `CF-Connecting-IP` → `True-Client-IP` → `X-Forwarded-For` → `X-Real-IP` → `request.client.host`
- Accurate client IP detection in production (Render.com behind Cloudflare)

**🍪 Cross-Subdomain Cookie Support** (v2.0.3)
- New env var: `COOKIE_DOMAIN` (optional, default: None)
- Allows cookies shared across `*.rydercupfriends.com` subdomains
- Set `COOKIE_DOMAIN=.rydercupfriends.com` in production for SSO across subdomains

**⛳ TeeCategory Enum Updated**
- Renamed `FORWARD_MALE` → `SENIOR_MALE` (matches DB migration)
- Renamed `FORWARD_FEMALE` → `SENIOR_FEMALE` (matches DB migration)
- Added `JUNIOR` category for junior players
- Full enum (7 values): `CHAMPIONSHIP_MALE`, `AMATEUR_MALE`, `SENIOR_MALE`, `CHAMPIONSHIP_FEMALE`, `AMATEUR_FEMALE`, `SENIOR_FEMALE`, `JUNIOR`
- **Note**: Later refactored to 5 neutral values + separate Gender field (see [Unreleased])

**🐳 Docker/Render Compatibility**
- Updated `entrypoint.sh` regex to accept `postgresql+asyncpg://` URLs
- Supports: `postgres://`, `postgresql://`, `postgresql+asyncpg://`, `postgresql+psycopg2://`

### Security

**OWASP Score**: Maintained at 9.4/10
- **A01 (Broken Access Control)**: Improved - More reliable device tracking, no false duplicates from IP rotation
- **A02 (Cryptographic Failures)**: Unchanged - UUID v4 for device_id, httpOnly cookie protection
- **A07 (Authentication Failures)**: Improved - Eliminates false logouts from dynamic IP changes

## [2.0.2] - 2026-02-02 (Sprint 2: Competition Scheduling)

### Added
- **Competition ↔ GolfCourse Many-to-Many Relationship** (Block 1 - COMPLETED):
  - Domain Layer:
    - New entity: `CompetitionGolfCourse` (association entity with display_order)
    - Value Object: `CompetitionGolfCourseId`
    - Updated `Competition` aggregate: added `_golf_courses: list[CompetitionGolfCourse]`
    - Business methods: `add_golf_course()`, `remove_golf_course()`, `reorder_golf_courses()`
    - Business rules: DRAFT state required, country compatibility, no duplicates
  - Infrastructure:
    - Migration `2b72b9741fd1`: `competition_golf_courses` table with mixed UUID types
    - **Type Safety**: `competition_id` uses CHAR(36) to match `competitions.id`, `golf_course_id` uses UUID(as_uuid=True) to match `golf_courses.id`
    - SQLAlchemy mapper: `CompetitionGolfCourseIdDecorator`, `GolfCourseIdDecorator`
  - Application Layer:
    - 3 new use cases: `AddGolfCourseToCompetitionUseCase`, `RemoveGolfCourseFromCompetitionUseCase`, `ReorderGolfCoursesUseCase`
    - 6 new DTOs: Add/Remove/Reorder request/response DTOs
  - API Layer:
    - 4 new REST endpoints:
      - `POST /api/v1/competitions/{id}/golf-courses` - Add golf course to competition
      - `DELETE /api/v1/competitions/{id}/golf-courses/{gc_id}` - Remove golf course
      - `PUT /api/v1/competitions/{id}/golf-courses/reorder` - Reorder all courses
      - `GET /api/v1/competitions/{id}/golf-courses` - List competition's golf courses
  - Testing Infrastructure:
    - **In-Memory Testing**: `InMemoryGolfCourseRepository`, `InMemoryGolfCourseUnitOfWork`
    - **Application Tests**: +26 unit tests (11 AddGolfCourse + 6 RemoveGolfCourse + 9 ReorderGolfCourses - includes 2-phase reorder)
    - **Integration Tests**: +9 E2E tests (4 API endpoints with admin_user fixture)
  - Tests: +64 total tests (24 domain + 26 application + 9 integration + 5 infrastructure)
  - Total tests: 1,236 passing (16 skipped) - 98.72% success rate (100% excluding expected skips)
- **Type-Safe Exception Subclasses** (Block 2 - COMPLETED):
  - Created 8 domain-specific exception subclasses:
    - `MaxCompetitionsExceededViolation`, `DuplicateEnrollmentViolation`, `MaxEnrollmentsExceededViolation`
    - `InvalidCompetitionStatusViolation`, `EnrollmentPastStartDateViolation`, `CompetitionFullViolation`
    - `InvalidDateRangeViolation`, `MaxDurationExceededViolation`
  - Files: `src/modules/competition/domain/exceptions/competition_violations.py` (NEW)
  - Benefit: Type-safe exception handling, eliminates fragile string matching
- **SBOM Submission via GitHub REST API** (Block 3 - COMPLETED):
  - Created bash script `scripts/submit-sbom-to-github.sh` (+202 lines)
  - Replaced non-existent `github/dependency-graph-submit-action@v1` with direct REST API integration
  - Endpoint: `POST /repos/{owner}/{repo}/dependency-graph/snapshots`
  - Enabled `permissions: contents: write` for Dependency Graph API
  - ADR-036: Documents architectural decision and implementation details
  - Benefit: Supply chain visibility, Dependabot integration, zero external dependencies

### Changed
- **Exception Handling Refactor** (Block 2 - COMPLETED):
  - Refactored `CompetitionPolicy` to use type-safe exception subclasses instead of generic `BusinessRuleViolation`
  - Refactored `RequestEnrollmentUseCase` to use direct exception catching instead of fragile string matching
  - Updated 20 tests in `test_competition_policy.py` to expect specific exception types
  - Result: Improved maintainability, better DDD compliance, type-safe exception handling
- **Clean Architecture Refactor - UoW Pattern Consistency** (Block 0 - COMPLETED):
  - Removed explicit `await self._uow.commit()` calls from:
    - Competition module: 14 use cases (activate, cancel, close, complete, create, delete, start, update, handle_enrollment, direct_enroll, request_enrollment, set_custom_handicap, cancel_enrollment, withdraw_enrollment)
    - User module: 2 use cases (register_device, revoke_device)
  - Updated mock fixtures to simulate UoW `__aexit__` behavior (commit on success, rollback on exception)
  - Removed `mock_uow.commit.assert_called_once()` assertions from ~16-20 unit tests
  - Result: 100% consistent Clean Architecture across all modules

### Fixed
- **Competition ↔ GolfCourse M2M Endpoints** - Critical bug fixes (12 issues resolved):
  1. **Dependency Injection**: Added missing DI functions (`get_add_golf_course_to_competition_use_case`, `get_remove_golf_course_from_competition_use_case`, `get_reorder_golf_courses_use_case`) - fixes 404 errors
  2. **GolfCourseId Value Object**:
     - Constructor: Accept both `str` and `uuid.UUID`, removed invalid `version=4` parameter
     - Added comparison operators (`__lt__`, `__le__`, `__gt__`, `__ge__`) for SQLAlchemy sorting
     - Property `.value` returns `uuid.UUID` object instead of string
  3. **CompetitionGolfCourseId Value Object**: Added comparison operators (`__lt__`, `__le__`, `__gt__`, `__ge__`) for SQLAlchemy sorting
  4. **GolfCourseIdType TypeDecorator**: Fixed `process_bind_param()` to return `value.value` directly (already UUID object)
  5. **AddGolfCourseUseCase**:
     - Line 160: Fixed approval check from `is_approved()` to `approval_status != ApprovalStatus.APPROVED`
     - Line 168: Fixed property access from `golf_course.country` to `golf_course.country_code`
     - Line 179: Fixed repository method from `.save()` to `.update()`
  6. **RemoveGolfCourseUseCase**: Line 124 - Fixed `.save()` to `.update()`
  7. **ReorderGolfCoursesUseCase**:
     - Line 120-123: Fixed data type conversion - now creates `list[tuple[GolfCourseId, int]]` instead of `list[GolfCourseId]`
     - Line 133: Fixed `.save()` to `.update()`
     - **Two-phase reorder strategy**: Implemented flush-based approach to avoid UNIQUE + CHECK constraint violations
       - Phase 1: Assign temporary high values (10001+) to all fields
       - Flush to persist temporary values
       - Phase 2: Assign final values (1, 2, 3...)
       - Respects CHECK constraint `display_order >= 1` and UNIQUE constraint `(competition_id, display_order)`
  8. **CompetitionRepository**: Added eager loading with `selectinload()` for nested `golf_course` relationship
  9. **Competition Mapper**: Added `relationship()` for `_golf_courses` with proper cascade and ordering
  10. **CompetitionGolfCourse Mapper**: Added `relationship()` for `golf_course` entity
  11. **GET /golf-courses endpoint**: Enriched response to include complete golf course data (tees with ratings, holes with par/stroke index)
  12. **Competition Entity**: Simplified `reorder_golf_courses()` - moved two-phase logic to use case layer for flush access
  13. **AddGolfCourseUseCase** - Exception detection improvements:
      - Line 172: Added "compatible" keyword for country compatibility error detection
      - Line 174: Added "añadido" keyword for duplicate golf course detection

### Technical Debt
- **Pending**: ADR-034 (Competition-GolfCourse Many-to-Many Relationship)
- **Temporary**: Golf course validation in `Competition.activate()` commented out (24 existing tests need updating)
- **Note**: Integration tests require Docker/PostgreSQL to run (pass when DB is available)

## [2.0.1] - 2026-01-31 (Sprint 1: Golf Courses CRUD + Admin Update Workflow)

### Added
- **Golf Course Module** (Complete CRUD with Admin Approval Workflow + Update System):
  - Domain Layer: `GolfCourse` aggregate with `Tee` and `Hole` entities
  - Value Objects: `GolfCourseId`, `CourseType`, `ApprovalStatus`, `TeeCategory`
  - Domain Events: `GolfCourseRequestedEvent`, `GolfCourseApprovedEvent`, `GolfCourseRejectedEvent`
  - Unit of Work: `GolfCourseUnitOfWorkInterface` with dual repository coordination (golf_courses + countries)
  - Infrastructure: `SQLAlchemyGolfCourseUnitOfWork`, `GolfCourseRepository`, SQLAlchemy mappers
  - **10 REST API Endpoints** (6 original + 4 update workflow):
    - `POST /api/v1/golf-courses/request` - Creator requests new course
    - `POST /api/v1/admin/golf-courses` - Admin creates course directly (approved)
    - `GET /api/v1/golf-courses/{id}` - Get course details (tees + holes)
    - `GET /api/v1/golf-courses?approval_status=APPROVED` - List filtered courses
    - `GET /api/v1/admin/golf-courses/pending` - Admin view pending approvals
    - `PUT /api/v1/admin/golf-courses/{id}/approve` - Admin approves course
    - `PUT /api/v1/admin/golf-courses/{id}/reject` - Admin rejects course
    - `PUT /api/v1/golf-courses/{id}` - Creator submits update (clone + approval workflow)
    - `PUT /api/v1/admin/golf-courses/updates/{id}/approve` - Admin approves update
    - `PUT /api/v1/admin/golf-courses/updates/{id}/reject` - Admin rejects update
  - **Update Workflow (Option A+ - Clone-Based)**:
    - Creator submits update → creates pending clone (original unchanged)
    - Admin approves → clone replaces original, original soft-deleted
    - Admin rejects → clone deleted, original unchanged
    - No data loss during approval process
  - Authorization: Request/List (authenticated), Admin endpoints (admin only)
  - Validations: 2-6 tees, 18 holes unique, par 66-76, stroke indices 1-18 unique
  - ~28 integration tests (API endpoints, 100% passing)
  - Repository tests: 100% passing (fixture issue resolved)

- **User Module - RFEG Optimization**:
  - Conditional RFEG handicap search: executes ONLY for Spanish users (country_code='ES')
  - Performance improvement: ~80% reduction in external API calls
  - 3 new unit tests for RFEG conditional logic (100% passing)

- **Test Fixtures**:
  - `sample_golf_course_data()` - 18 holes, 2 tees, Real Club de Golf El Prat
  - `create_golf_course()` - Helper to request course via API
  - `approve_golf_course()` - Helper for admin approval
  - `reject_golf_course()` - Helper for admin rejection

### Changed
- **Golf Course Use Cases**: Refactored from `AbstractUoW` to `GolfCourseUnitOfWorkInterface`
- **Dependencies**: Added `get_golf_course_uow()` dependency provider in `src/config/dependencies.py`
- **Main Application**: Registered golf_course_routes under `/api/v1` with "Golf Courses" tag

### Fixed
- **GolfCourse Entity**: Added `@reconstructor` to ensure `_domain_events` is initialized when loaded from DB
- **RequestGolfCourseUseCase**: Added country validation to prevent FK errors
- **SQLAlchemy Orphan Management**: Fixed critical bug in update workflow - explicit DELETE before UPDATE prevents orphaned rows
- **Clean Architecture - UoW Pattern**: Removed 9 explicit `await self._uow.commit()` calls from Golf Course use cases (commits now handled automatically by UoW context manager `__aexit__`)
- **Test Mocks**: Updated 4 test fixtures to simulate UoW `__aexit__` behavior (auto-commit on success, rollback on exception)
- **CI/CD Pipeline**: Fixed DIRECT_DEPS grep to use POSIX classes (`grep -E -c "^[[:alnum:]._-]+[[:space:]]*=="`) for compatibility
- **API Documentation**: Corrected endpoint paths in golf_course_routes.py docstring (reflect actual router prefix `/golf-courses`)
- **Code Quality**: Applied Ruff auto-fixes - removed 72 redundant `return None` statements (11 migrations, 4 test files)
- **7 CodeRabbit Issues Resolved**:
  1. **CRITICAL**: Migration schema - removed incorrect `par` column from `golf_course_tees` table
  2. **CRITICAL**: Mapper registration - added `start_golf_course_mappers()` in main.py and tests/conftest.py
  3. **IMPORTANT**: Deprecated datetime - replaced `datetime.utcnow()` with `datetime.now(UTC).replace(tzinfo=None)` (7 occurrences)
  4. **IMPORTANT**: UnitOfWork rollback - added try/except in `__aexit__` to rollback on commit failure
  5. **MEDIUM**: HTTP status codes - return 400 for invalid `approval_status` values (not 403)
  6. **MINOR**: CI/CD grep pattern - fixed SBOM dependency counting (supports underscores/dots)
  7. **MINOR**: Ruff linting - added PLC0415 exceptions for local imports in domain entities

### Database
- **New Migration**: `af107e8f82c6_create_golf_course_tables`
  - `golf_courses` table (UUID PK, approval workflow, FK to users & countries)
  - `golf_course_tees` table (2-6 tees per course, WHS ratings)
  - `golf_course_holes` table (18 holes, par 3-5, unique stroke indices)
  - Indexes: `ix_golf_courses_approval_status`, `ix_golf_courses_creator_id`
  - Constraints: Check constraints for ranges, unique constraints per course
  - Cascade delete: Deleting a golf_course deletes all its tees and holes

### Tests
- **Total Tests**: 1,177 (1,177 passing, 16 skipped)
- **New Tests**: +10 integration tests (Golf Course update workflow) + +16 unit tests (use cases)
- **Modified Tests**: +3 user tests (RFEG conditional logic)
- **Execution Time**: ~142s (with `-n auto`)
- **Success Rate**: 100% (1,177/1,177 passing)

### Documentation
- Updated CLAUDE.md with Golf Course Module section
- Updated test statistics and skipped tests explanation
- All commits signed with GPG

**Part of**: Sprint 1 v2.0.1 (RBAC Foundation + Golf Courses CRUD)
**Ref**: ROADMAP.md lines 45-98

---

## [2.0.0] - 2026-01-29

### Added
- **RBAC Foundation**: Implemented a simplified, three-tier role system (ADMIN, CREATOR, PLAYER) without a formal roles table.
  - Added `is_admin` boolean field to the `User` entity with a partial index for performance.
  - Created a new endpoint `GET /api/v1/users/me/roles/{competition_id}` to check user roles within a competition.
  - Implemented authorization helpers: `is_admin_user()`, `is_creator_of()`, and `is_player_in()`.
- Added 25 new tests (17 unit, 8 integration) for the RBAC functionality, achieving 100% coverage for the new code.

### Changed
- Separated Docker and Kubernetes port variables to prevent conflicts during local development. `DOCKER_APP_PORT` and `DOCKER_DATABASE_PORT` are now used for the application in `docker-compose.yml`.
- Updated `docker-compose.yml` to use the new port variables.

### Fixed
- Resolved port allocation errors when running the application with Docker Compose and a local Kubernetes cluster simultaneously.

### Database
- A new database migration `7522c9fc51ef` is required to add the `is_admin` column to the `users` table.


---

## [1.13.1] - 2026-01-18

### Fixed - Current Device Detection UX ✅ COMPLETADO (18 Ene 2026)

**📱 Detección de Dispositivo Actual en Listado** (UX Improvement)

#### Problema:
- El endpoint `GET /api/v1/users/me/devices` no indicaba cuál dispositivo estaba siendo usado actualmente
- Frontend no podía resaltar visualmente el dispositivo en uso
- Sin advertencia al usuario al intentar revocar su propio dispositivo

#### Solución:
- ✅ Campo `is_current_device` (bool) añadido al response DTO
- ✅ Comparación de fingerprints en `ListUserDevicesUseCase`
- ✅ Validación de headers en request (user_agent + ip_address)
- ✅ Tests: 8 tests unitarios + 2 integration (100% pasando)

**Archivos Modificados:**
- `src/modules/user/application/use_cases/list_user_devices_use_case.py`
- `src/modules/user/application/dto/user_dto.py`
- `src/modules/user/infrastructure/api/v1/device_routes.py`
- `tests/unit/modules/user/application/use_cases/test_list_user_devices_use_case.py`

---

### Security - HTTP Security Enhancements ✅ COMPLETADO (18 Ene 2026)

**🔒 Validación Anti-Spoofing y Anti-Sentinel Values** (OWASP A01 + A03)

#### Problemas Identificados:

**1. CRÍTICO - Valores Sentinel sin Validación (OWASP A03):**
- `DeviceFingerprint.create()` fallaba con `ValueError` si recibía `user_agent="unknown"` o `ip_address=""`
- Causaba HTTP 500 en endpoint `/users/me/devices` si AsyncClient no enviaba headers
- **Impacto:** Endpoint inestable en testing/production con clientes sin headers

**2. CRÍTICO - IP Spoofing Vulnerability (OWASP A01):**
- Funciones `get_client_ip()` confiaban ciegamente en headers `X-Forwarded-For` sin validar proxy
- **Ataque:** Cliente malicioso podía falsificar su IP enviando header manipulado
- **Impacto:** Bypass de rate limiting, device fingerprinting incorrecto, sesiones compartidas
- Código duplicado en 3 archivos (90 líneas)

#### Solución Implementada:

**A. Helper Centralizado de HTTP Context Validation:**
- ✅ Módulo `src/shared/infrastructure/http/http_context_validator.py` (306 líneas)
- ✅ `validate_ip_address()`: Rechaza sentinels ("unknown", "0.0.0.0", "127.0.0.1", localhost)
- ✅ `validate_user_agent()`: Rechaza sentinels ("unknown", ""), valida longitud (10-500 chars)
- ✅ `get_trusted_client_ip()`: Validación de proxy contra whitelist
- ✅ `get_user_agent()`: Extracción con sanitización
- ✅ Graceful degradation: retorna `None` en lugar de lanzar excepciones

**B. Trusted Proxy Pattern:**
- ✅ Variable de entorno `TRUSTED_PROXIES` (lista separada por comas)
- ✅ Validación de proxy IP antes de confiar en headers forwarded
- ✅ Solo usa `X-Forwarded-For` si request viene de proxy confiable
- ✅ Fallback a `request.client.host` si proxy no es confiable

**C. Validación Defensiva en Use Cases:**
- ✅ `ListUserDevicesUseCase`: Pre-validación antes de `DeviceFingerprint.create()`
- ✅ Try-catch en creación de fingerprint (evita HTTP 500)
- ✅ Logging de advertencia cuando validación falla
- ✅ Retorna `is_current_device=False` si no puede determinar dispositivo actual

**D. Código Duplicado Eliminado:**
- ✅ Removidas 3 implementaciones de `get_client_ip()` y `get_user_agent()`
- ✅ 7 usages migrados a helper centralizado
- ✅ DRY compliance: Single source of truth

#### Tests:
- ✅ +36 tests de seguridad HTTP (100% passing)
  - 14 tests `validate_ip_address()`: sentinels, IPv4/IPv6, malformed strings
  - 10 tests `validate_user_agent()`: sentinels, longitud, edge cases
  - 12 tests `get_trusted_client_ip()`: trusted/untrusted proxy, X-Forwarded-For, fallback
- ✅ +9 tests unitarios (ListUserDevicesUseCase con validación)
- ✅ Suite completa: 1,066/1,066 tests (99.9% passing)
- ✅ Tiempo: ~60 segundos con paralelización

#### Archivos Creados:
- `src/shared/infrastructure/http/http_context_validator.py` (306 líneas)
- `tests/unit/shared/infrastructure/http/test_http_context_validator.py` (674 líneas, 36 tests)

#### Archivos Modificados:
- `src/config/settings.py` (añadido TRUSTED_PROXIES)
- `src/modules/user/application/use_cases/list_user_devices_use_case.py` (validación defensiva)
- `src/modules/user/infrastructure/api/v1/device_routes.py` (migrado a helper)
- `src/modules/user/infrastructure/api/v1/auth_routes.py` (6 usages migrados)
- `src/modules/user/infrastructure/api/v1/user_routes.py` (1 usage migrado)
- `src/config/dependencies.py` (fix mapper bug: UserDevice.is_active → user_devices_table.c.is_active)
- `tests/conftest.py` (añadido TRUSTED_PROXIES + headers HTTP)
- `ROADMAP.md` (actualizado v1.13.1 a COMPLETADO)

#### Seguridad OWASP:

**Score Global:** 9.2/10 → **9.4/10** (+0.2)

| Categoría | Antes | Después | Mejora | Impacto |
|-----------|-------|---------|--------|---------|
| **A01: Access Control** | 9.7/10 | **10/10** | +0.3 | IP Spoofing Prevention con trusted proxy whitelist |
| **A03: Injection** | 10/10 | **10/10** | 0.0 | Mantenido - Sentinel validation refuerza protección |

**Beneficios:**
- Prevención de IP spoofing en rate limiting y device fingerprinting
- Eliminación de HTTP 500 por valores sentinel
- Código más mantenible (DRY compliance)
- Testing robusto contra edge cases
- Graceful degradation (mejor UX)

#### Decisiones Técnicas:
- **Graceful Degradation vs Exceptions**: Retornar `None` en lugar de lanzar excepciones permite que el sistema continúe funcionando incluso con datos inválidos
- **Trusted Proxy Whitelist**: Solo confiar en headers forwarded si el request viene de un proxy conocido
- **Centralized Helper**: Eliminar duplicación de código y crear single source of truth para validaciones HTTP
- **Sentinel Rejection**: Lista explícita de valores prohibidos ("unknown", "", "0.0.0.0", localhost)
- **IP Format Validation**: Usar `ipaddress.ip_address()` de stdlib para validación estricta

**Impacto:** Protección completa contra IP spoofing y valores sentinel maliciosos. Compliance OWASP A01 alcanzado (10/10). Endpoint de dispositivos ahora 100% robusto en testing y producción.

---

## [1.13.0] - 2026-01-09

### Added - Account Lockout (Brute Force Protection) ✅ COMPLETADO (7 Ene 2026)

**🔒 Protección Contra Ataques de Fuerza Bruta** (OWASP A07)

#### Features Implementadas:
- ✅ Account lockout automático tras 10 intentos fallidos de login
- ✅ Bloqueo temporal de 30 minutos (auto-desbloqueo)
- ✅ HTTP 423 Locked cuando cuenta está bloqueada
- ✅ Reset automático de contador tras login exitoso
- ✅ Endpoint manual de desbloqueo para admins (POST /auth/unlock-account)
- ✅ Persistencia en BD (no solo memoria)

#### Arquitectura (Clean Architecture):
- **Domain Layer**:
  - 4 métodos nuevos en User entity: `record_failed_login()`, `is_locked()`, `unlock()`, `reset_failed_attempts()`
  - 2 Domain Events: `AccountLockedEvent`, `AccountUnlockedEvent`
  - 1 Excepción: `AccountLockedException`
- **Application Layer**:
  - LoginUserUseCase modificado (dual check pattern)
  - UnlockAccountUseCase nuevo
  - 2 DTOs: `UnlockAccountRequestDTO`, `UnlockAccountResponseDTO`
- **Infrastructure Layer**:
  - Migration b6d8a1c65bd2: 2 campos (`failed_login_attempts`, `locked_until`) + índice
  - Mapper actualizado para nuevos campos
- **API Layer**:
  - POST /api/v1/auth/unlock-account (pendiente rol Admin v2.1.0)
  - Login endpoint modificado (retorna HTTP 423)

#### Tests:
- ✅ 5 tests de integración pasando (100%)
- Tests: lockout tras 10 intentos, bloqueo con password correcta, reset contador, persistencia, mensaje con timestamp

#### Decisiones Técnicas (ADR-027):
- Integración en User entity (vs LoginAttempt separado)
- Naive datetimes (consistencia con codebase)
- Dual check pattern (pre + post password verification)
- X-Test-Client-ID para tests (bypass rate limiting)

#### Security:
- **OWASP A07** mitigado: Credential stuffing, dictionary attacks, brute force
- **Defense in Depth**: Complementa rate limiting existente (5/min)
- **Audit Trail**: Domain events para security logging

#### Commits:
1. `a9fe089`: Domain + Application + Infrastructure layers
2. `e499add`: API Layer + Tests
3. `14ecfd0`: Bug fixes (lockout logic + timezone consistency)

#### Documentación:
- ✅ ADR-027: Account Lockout - Brute Force Protection
- ✅ docs/API.md: Endpoint unlock-account documentado
- ✅ postman_collection.json: Request "Unlock Account (Admin)" agregado
- ✅ docs/SECURITY_IMPLEMENTATION.md: Actualizado

**Ver detalles:** `docs/architecture/decisions/ADR-027*.md`, `docs/API.md`

---

### Added - Device Fingerprinting ✅ COMPLETADO (10 Ene 2026)

**📱 Gestión de Dispositivos de Usuario + Auto-registro en Login/Refresh** (OWASP A01)

#### Features Implementadas:
- ✅ **Auto-registro de dispositivos** en LoginUserUseCase y RefreshAccessTokenUseCase
- ✅ Detección automática de dispositivos en login/refresh token (integración completa)
- ✅ Listado de dispositivos activos (GET /api/v1/users/me/devices)
- ✅ Revocación manual de dispositivos (DELETE /api/v1/users/me/devices/{device_id})
- ✅ Fingerprint único: SHA256(device_name + "|" + user_agent + "|" + ip_address)
- ✅ Soft delete con audit trail (is_active=FALSE)
- ✅ Partial unique index: previene duplicados activos, permite múltiples revocados

#### Arquitectura (Clean Architecture):
- **Domain Layer**:
  - UserDevice entity (id, user_id, fingerprint, last_used_at, is_active)
  - 2 Value Objects: UserDeviceId, DeviceFingerprint
  - 2 Domain Events: NewDeviceDetectedEvent, DeviceRevokedEvent
  - UserDeviceRepositoryInterface (5 métodos)
- **Application Layer**:
  - 3 Use Cases: RegisterDeviceUseCase, ListUserDevicesUseCase, RevokeDeviceUseCase
  - 7 DTOs (RegisterDevice, ListDevices, RevokeDevice request/response)
- **Infrastructure Layer**:
  - Migration 50ccf425ff32: tabla user_devices + 2 índices
  - SQLAlchemyUserDeviceRepository con TypeDecorators
  - UserUnitOfWork actualizado (user_devices property)
- **API Layer**:
  - GET /api/v1/users/me/devices - Lista dispositivos activos
  - DELETE /api/v1/users/me/devices/{device_id} - Revoca dispositivo

#### Tests:
- ✅ 86 tests unitarios (Domain: 66, Application: 20)
- ✅ 13 tests de integración (API con PostgreSQL)
- ✅ Total: 99/99 tests device fingerprinting pasando (100%)
- ✅ Suite completa: 1021/1021 tests (100% pasando)
- ✅ Integración completa: 10 archivos modificados (dependencies, use cases, DTOs, tests)

#### Decisiones Técnicas (ADR-030):
- IP incluida en fingerprint (redes diferentes = dispositivos diferentes)
- Soft delete para audit trail (vs hard delete)
- Partial unique index (user_id, fingerprint_hash WHERE is_active=TRUE)
- **Auto-registro integrado** en LoginUserUseCase y RefreshAccessTokenUseCase (condicional si user_agent + ip_address presentes)
- Validación de ownership en revocación
- RegisterDeviceUseCase inyectado via DI en dependencies.py

#### Security:
- **OWASP A01** mitigado: Session transparency, device management
- **User empowerment**: Auto-detección + control manual
- **Audit Trail**: Domain events para security logging

#### Documentación:
- ✅ ADR-030: Device Fingerprinting (123 líneas)
- ✅ docs/API.md: 2 endpoints documentados
- ✅ postman_collection.json: Requests "List Devices" y "Revoke Device" agregados

**Ver detalles:** `docs/architecture/decisions/ADR-030-device-fingerprinting.md`, `docs/API.md`

---

### Added - CSRF Protection ✅ COMPLETADO (8 Ene 2026)

**🛡️ Protección Contra Cross-Site Request Forgery** (OWASP A01)

#### Features Implementadas:
- ✅ Triple capa de protección CSRF:
  - **Capa 1**: Custom Header `X-CSRF-Token` (principal)
  - **Capa 2**: Double-Submit Cookie `csrf_token` (NO httpOnly)
  - **Capa 3**: SameSite="lax" (ya implementado)
- ✅ Middleware CSRFMiddleware con timing-safe comparison
- ✅ Token 256-bit (secrets.token_urlsafe(32)), duración 15 min
- ✅ Generación automática en login + refresh token endpoints
- ✅ Validación en POST/PUT/PATCH/DELETE (exime GET/HEAD/OPTIONS)
- ✅ Public endpoints exempt: /register, /login, /forgot-password, /reset-password, /verify-email

#### Tests:
- ✅ 11 tests de seguridad (10 passing + 1 skipped)
- ✅ Cobertura: token generation, validation, exemptions, timing-safe comparison
- ✅ Tests convertidos a async para pytest-xdist compatibility (8 workers paralelos)

#### Decisiones Técnicas (ADR-028):
- Custom middleware vs fastapi-csrf-protect (mayor control)
- Double-submit cookie pattern (stateless, no DB storage)
- Public endpoints exempt (no pueden tener token antes de registrarse)
- SameSite="lax" complementa (permite GET links de email)

#### Security:
- **OWASP A01** mitigado: CSRF attacks, unauthorized state changes
- **Defense in Depth**: 3 capas de protección
- **Timing-safe comparison**: Previene timing attacks

**Ver detalles:** `docs/architecture/decisions/ADR-028-csrf-protection.md`

---

### Added - Password History ✅ COMPLETADO (8 Ene 2026)

**🔐 Prevención de Reutilización de Contraseñas** (OWASP A07)

#### Features Implementadas:
- ✅ Previene reutilización de las últimas 5 contraseñas
- ✅ Tabla `password_history` con bcrypt hashes (255 chars)
- ✅ Cascade delete on user deletion (GDPR Article 17 compliance)
- ✅ Validación automática en UpdateSecurity y ResetPassword use cases
- ✅ Domain Event: PasswordHistoryRecordedEvent

#### Arquitectura:
- **Domain Layer**:
  - PasswordHistory entity (id, user_id, password_hash, created_at)
  - PasswordHistoryId Value Object
  - PasswordHistoryRepositoryInterface (5 métodos)
- **Infrastructure Layer**:
  - Migration: tabla password_history + índices
  - SQLAlchemyPasswordHistoryRepository
  - InMemoryPasswordHistoryRepository para tests
- **Application Layer**:
  - Validación integrada en UpdateSecurityUseCase
  - Validación integrada en ResetPasswordUseCase

#### Tests:
- ✅ 25 tests unitarios (PasswordHistoryId + PasswordHistory)
- ✅ 947/947 tests pasando (99.16% suite completa)

#### Decisiones Técnicas (ADR-029):
- LIMIT 5 (vs todas las contraseñas históricas)
- Bcrypt hashes almacenados (vs plaintext comparison imposible)
- Cascade delete (GDPR compliance)
- Auto-cleanup diferido a v1.14.0

**Ver detalles:** `docs/architecture/decisions/ADR-029-password-history.md`

---

### Fixed - CI/CD Pipeline (9 Ene 2026)

**🔧 Correcciones de Linting y Type Checking**

#### Ruff Fixes (36 errors → 0):
- Auto-fixed 33 errors: deprecated typing imports (`List→list`, `Dict→dict`)
- Manual fixes:
  - `alembic/env.py:33`: Moved noqa comment to opening line (E402)
  - `dev_tests.py:41`: Added type annotation for `DOCSTRING_CACHE`
  - `user_device_mapper.py:76`: Replaced `try/except/pass` → `contextlib.suppress()` (SIM105)

#### Mypy Fixes (3 errors → 0):
- `dev_tests.py`: Fixed DOCSTRING_CACHE type (`dict[str, str]` → `dict[str, dict[str, str]]`)
- `main.py:137`: Added `# type: ignore[arg-type]` for slowapi handler (sync/async compatibility)

#### Test Fixes:
- `test_csrf_protection.py`: Complete rewrite (21 → 413 lines)
  - Converted sync TestClient → AsyncClient for pytest-xdist compatibility
  - Fixed endpoint paths (`/api/v1/users/profile` not `/me/profile`)
  - 10/11 CSRF tests now passing (1 skipped)
- `test_device_routes.py`: Complete rewrite (broken syntax fixed)
  - 6/6 integration tests passing

#### CI/CD Verification:
- ✅ `ruff check .` → All checks passed!
- ✅ `mypy .` → Success: no issues found in 234 source files
- ✅ `bandit -r src/ -ll` → No issues identified (22,447 lines scanned)
- ✅ `pytest tests/ -n auto` → 1021 passed, 2 skipped in 61.56s

**Pipeline Status:** ✅ Ready for GitHub Actions (all checks will pass)

---

## [1.12.1] - 2026-01-05

### Added - Snyk Code (SAST) Integration ✅ COMPLETADO (5 Ene 2026)

**🔍 Análisis Estático de Código Fuente en CI/CD** (OWASP A03, A02, A01)

- ✅ Snyk Code (SAST) integrado en pipeline CI/CD
- ✅ Escaneo automático de código fuente en `src/`
- ✅ Detección de vulnerabilidades en código propio:
  - SQL Injection
  - XSS (Cross-Site Scripting)
  - Hardcoded secrets
  - Path Traversal
  - Weak Cryptography
  - Command Injection
- ✅ 2 tipos de análisis en Job 8:
  - Snyk Test (SCA): Escaneo de dependencias
  - Snyk Code (SAST): Escaneo de código fuente
- ✅ Reportes separados: `snyk-dependencies-report.json` + `snyk-code-report.json`
- ✅ Resumen automático con contador de issues por tipo
- ✅ Artifacts con retención de 30 días
- ✅ Resultados enviados a Snyk dashboard

**Archivos Modificados:**
- `.github/workflows/ci_cd_pipeline.yml` (Job 8 mejorado: +47 líneas, -6 líneas)

**Impacto:** Doble capa de seguridad en CI/CD (SCA + SAST). Detección temprana de vulnerabilidades antes de mergear a main. Compliance OWASP mejorado para A03 (Injection), A02 (Cryptographic Failures), A01 (Access Control).

**PR:** #39

---

## [1.12.0] - 2026-01-03

### Security - Snyk Vulnerability Fixes ✅ COMPLETADO (3 Ene 2026)

**🔒 Resolución de 6 Vulnerabilidades Detectadas por Snyk** (OWASP A06)

- ✅ **authlib** 1.2.1 → 1.6.5 (dependencia transitiva de safety)
  - CVE-2025-61920 RESUELTO - DoS via tokens con segmentos base64 excesivos (CVSS 8.7 HIGH)
  - CVE-2025-62706 RESUELTO - DoS via decompresión ZIP (zip bomb attack) (CVSS 7.1 HIGH)

- ✅ **setuptools** 68.0.0 → 78.1.1 (dependencia transitiva de safety)
  - CVE-2024-6345 RESUELTO - Code Injection via package_index (os.system) (CVSS 7.5 HIGH)
  - CVE-2025-47273 RESUELTO - Directory Traversal en _download_url (CVSS 6.8 MEDIUM)

- ✅ **zipp** 3.15.0 → 3.19.1 (dependencia transitiva de importlib-metadata)
  - CVE-2024-5569 RESUELTO - Infinite loop DoS via Path module (CVSS 6.9 MEDIUM)

- ✅ **marshmallow** 3.19.0 → 3.26.2 (dependencia transitiva de safety)
  - CVE-2025-68480 RESUELTO - DoS via Asymmetric Resource Consumption (CVSS 6.9 MEDIUM)

- ✅ **Snyk Integration en CI/CD** - Job automático en GitHub Actions
  - Scan automático en cada push/PR
  - Severity threshold: HIGH
  - Reportes JSON (retención 30 días)
  - Snyk monitor para dashboard web

**Archivos Modificados:**
- `requirements.txt` - 4 paquetes añadidos (authlib, setuptools, zipp, marshmallow)
- `.github/workflows/ci_cd_pipeline.yml` - Job 8: Snyk Security Scan

**Tests:**
- ✅ 905/905 tests pasando (100%)

**CI/CD Configuración:**
```bash
# GitHub Secrets requerido
SNYK_TOKEN=<tu_token_de_snyk>

# Opcional: Variable para habilitar/deshabilitar
SNYK_ENABLED=true
```

**Vulnerabilidades Pre-existentes (ya resueltas):**
- ✅ urllib3==2.6.0 (CVE-2024-37891, CVE-2025-50181 ya cubiertos)
- ✅ requests==2.32.4 (CVE-2024-35195, CVE-2024-47081 ya cubiertos)
- ✅ filelock==3.20.1 (CVE-2025-68146 ya cubierto)

**Impacto:** Protección contra 6 vulnerabilidades HIGH/MEDIUM en dependencias transitivas. Pipeline mejorado con triple escáner de seguridad (Safety + pip-audit + Snyk). Puntuación OWASP A06: 8.5/10 → 9.0/10 (mejorada por integración Snyk en v1.12.0).

---

## [1.11.0] - 2025-12-26

### Added - Password Reset System ✅ COMPLETADO (26 Dic 2025)

**🔑 Sistema de Recuperación de Contraseña Completo** (OWASP A01, A02, A07)

- ✅ Password Reset System implementado (100% funcional)
- ✅ 3 REST endpoints con rate limiting 3/hora
- ✅ Domain Layer: 3 métodos en User entity + 2 eventos
  - `generate_password_reset_token()` - Token seguro 24h (256 bits, secrets.token_urlsafe)
  - `can_reset_password()` - Validación token + expiración
  - `reset_password()` - Cambio + invalidación + revocación sesiones
  - `PasswordResetRequestedEvent` + `PasswordResetCompletedEvent`
- ✅ Application Layer: 3 Use Cases + 6 DTOs
  - `RequestPasswordResetUseCase` - Timing attack prevention (delay artificial)
  - `ResetPasswordUseCase` - Token único + session invalidation
  - `ValidateResetTokenUseCase` - Pre-validación (mejor UX)
- ✅ Infrastructure Layer: Migration + Repository + Email templates
  - Migración Alembic: 2 campos + 2 índices (único en token, normal en expires_at)
  - `find_by_password_reset_token()` en UserRepository
  - Templates HTML bilingües (ES/EN): reset request + password changed notification
- ✅ API Layer: 3 endpoints REST
  - `POST /api/v1/auth/forgot-password` - Solicitar reseteo
  - `POST /api/v1/auth/reset-password` - Completar reseteo
  - `GET /api/v1/auth/validate-reset-token/:token` - Validar token
  - Rate limiting: 3 intentos/hora por email/IP
- ✅ Security Features:
  - Token criptográficamente seguro (256 bits)
  - Expiración automática (24 horas)
  - Token de un solo uso (invalidación post-uso)
  - Timing attack prevention (delay artificial si email no existe)
  - Mensaje genérico anti-enumeración de usuarios
  - Invalidación automática de TODAS las sesiones activas (refresh tokens)
  - Templates de email bilingües con warnings de seguridad
  - Política de contraseñas aplicada (OWASP ASVS V2.1)
  - Security logging completo (audit trail)
- ✅ Tests: 905/905 tests pasando (100%) - +51 tests nuevos
  - 15 tests: User Entity métodos password reset
  - 9 tests: RequestPasswordResetUseCase
  - 11 tests: ResetPasswordUseCase
  - 7 tests: ValidateResetTokenUseCase
  - 9 tests: Domain Events

**Archivos Creados (11):**
- `alembic/versions/3s4721zck3x7_add_password_reset_fields_to_users_table.py`
- `src/modules/user/domain/events/password_reset_requested_event.py`
- `src/modules/user/domain/events/password_reset_completed_event.py`
- `src/modules/user/application/use_cases/request_password_reset_use_case.py`
- `src/modules/user/application/use_cases/reset_password_use_case.py`
- `src/modules/user/application/use_cases/validate_reset_token_use_case.py`
- `tests/unit/modules/user/domain/entities/test_user_password_reset.py`
- `tests/unit/modules/user/application/use_cases/test_request_password_reset_use_case.py`
- `tests/unit/modules/user/application/use_cases/test_reset_password_use_case.py`
- `tests/unit/modules/user/application/use_cases/test_validate_reset_token_use_case.py`
- `tests/unit/modules/user/domain/events/test_password_reset_events.py`

**Archivos Modificados (18):**
- `src/modules/user/domain/entities/user.py` (+3 métodos, +2 campos)
- `src/modules/user/infrastructure/api/v1/auth_routes.py` (+3 endpoints)
- `src/modules/user/application/dto/user_dto.py` (+6 DTOs)
- `src/config/dependencies.py` (+3 dependency injections)
- `src/shared/domain/events/security_events.py` (+2 eventos)
- `src/shared/infrastructure/logging/security_logger.py` (+2 helpers)
- `src/shared/infrastructure/email/email_service.py` (+2 templates)
- Y 11 archivos más (mappers, repositorios, interfaces)

**OWASP Coverage:**
- A01: Broken Access Control (session invalidation, mensaje genérico)
- A02: Cryptographic Failures (token seguro, expiración, uso único)
- A03: Injection (email sanitization, Pydantic validation)
- A04: Insecure Design (rate limiting 3/hora)
- A07: Authentication Failures (password policy, token validation)
- A09: Security Logging (audit trail completo)

**Impacto:** Feature de seguridad crítica implementada con Clean Architecture completa. Total: ~1,200 líneas de código. Tests: 853 → 905 (+51 nuevos, +6.1%). Compliance OWASP mejorado.

---

### Changed - CI/CD Pipeline Improvement ✅ COMPLETADO (19 Dic 2025)

**🔧 Pragmatic CVE Handling in Dependency Audit** (OWASP A06)

- ✅ Pipeline solo falla con CVEs que tienen fix disponible
- ✅ CVEs sin fix disponible se monitorean pero no bloquean deployment
- ✅ Filtro mejorado con jq: `map(select(.fix_versions | length > 0))`
- ✅ Métricas separadas: CVEs con fix vs CVEs sin fix
- ✅ Mensaje informativo para CVEs sin solución (CVE-2024-23342 en ecdsa)

**Impacto:**
- ✅ Pipeline pasa con CVE-2024-23342 (ecdsa) - sin fix disponible, out of scope del proyecto
- ✅ Pipeline sigue bloqueando CVEs con fix disponible (seguridad mantenida)
- ✅ Desarrollo no bloqueado por vulnerabilidades sin solución posible
- ✅ Reportes de seguridad mantienen visibilidad completa

**Archivos Modificados:**
- `.github/workflows/ci_cd_pipeline.yml` (líneas 277-320)

**Justificación Técnica:**
- CVE-2024-23342 (ecdsa timing attack) no tiene fix disponible
- ecdsa es dependencia transitiva de python-jose (JWT)
- No usamos ECDSA directamente (usamos HS256)
- Enfoque pragmático: solo bloquear lo que podemos solucionar

---

### Added - Security Tests Suite ✅ COMPLETADO (19 Dic 2025)

**🛡️ Comprehensive Security Testing** (OWASP A01, A03, A04, A07)

- ✅ 34 tests de seguridad (100% pasando en ~9s)
- ✅ Tests de rate limiting (7 tests) - OWASP A04, A07
  - Validación de límites en login (5/min), register (3/h), competitions (10/h)
  - Tests de bypass (User-Agent, persistencia)
  - Metadata de rate limiting
- ✅ Tests de SQL injection (5 tests) - OWASP A03
  - Intentos de inyección en login, registro, competiciones
  - Validación de protección ORM (consultas parametrizadas)
  - Tests de no-raw-SQL execution
- ✅ Tests de XSS - Cross-Site Scripting (13 tests) - OWASP A03
  - XSS en campos de usuario y competiciones
  - Stored XSS en perfiles
  - Sanitización HTML (tags, protocolos javascript:)
  - Security headers (X-Content-Type-Options, X-Frame-Options)
- ✅ Tests de authentication bypass (9 tests) - OWASP A01, A07
  - Validación de endpoints protegidos
  - Rechazo de tokens inválidos/expirados
  - Prevención de manipulación de tokens (alg=none, payload modificado)
  - Gestión de sesiones (logout, refresh tokens)
  - Prevención de enumeración de usuarios

**Archivos Creados:**
- `tests/security/__init__.py`
- `tests/security/test_rate_limiting_security.py` (293 líneas, 7 tests)
- `tests/security/test_sql_injection_security.py` (181 líneas, 5 tests)
- `tests/security/test_xss_security.py` (235 líneas, 13 tests)
- `tests/security/test_auth_bypass_security.py` (289 líneas, 9 tests)

**Tests Corregidos:**
- Fixture `test_user_token` reemplazado por `authenticated_client` existente
- Validación de respuesta 429 ajustada para SlowAPI
- Schema de competiciones completado con campos obligatorios
- Tests de manipulación de tokens corregidos (limpieza cookies/headers)
- Tests de logout corregidos (JSON vacío para LogoutRequestDTO)

**Cobertura OWASP:**
- A01: Broken Access Control (6 tests)
- A03: Injection - SQL (5 tests) + XSS (13 tests)
- A04: Insecure Design (7 tests de rate limiting)
- A07: Authentication Failures (9 tests)

**Impacto:** Testing automático de seguridad en CI/CD, documentación viva de protecciones, validación continua de controles de seguridad. Total de tests: 819 → 853 (+34 tests de seguridad).

---

### Added - Sentry Backend Integration ✅ COMPLETADO (18 Dic 2025)

**📊 Error Tracking y Performance Monitoring** (OWASP A09)

- ✅ Sentry SDK instalado con integración FastAPI, SQLAlchemy, Logging
- ✅ Error tracking automático con stack traces completos
- ✅ Performance monitoring (APM) con sampling configurable
- ✅ Profiling de código (CPU/memoria) con sampling configurable
- ✅ Middleware de contexto de usuario (captura user_id, email, IP de JWT)
- ✅ Filtros automáticos (health checks, OPTIONS, 404s)
- ✅ Configuración por entorno (development, staging, production)
- ✅ Tests completos: 819/819 tests pasando (100%)

**Archivos Creados:**
- `src/config/sentry_config.py` (157 líneas)
- `src/shared/infrastructure/http/sentry_middleware.py` (169 líneas)

**Archivos Modificados:**
- `requirements.txt` (añadido sentry-sdk[fastapi]==2.19.2)
- `src/config/settings.py` (añadidas 4 variables Sentry)
- `main.py` (inicialización Sentry + middleware)

**Variables de Entorno Nuevas:**
- `SENTRY_DSN`: URL del proyecto Sentry (opcional - si no está, Sentry se desactiva)
- `ENVIRONMENT`: development/staging/production (default: development)
- `SENTRY_TRACES_SAMPLE_RATE`: % de transacciones a capturar (default: 0.1 = 10%)
- `SENTRY_PROFILES_SAMPLE_RATE`: % de perfiles a capturar (default: 0.1 = 10%)

**Características:**
- Captura automática de excepciones no manejadas
- Breadcrumbs de navegación (últimos 50 eventos antes del error)
- Contexto HTTP completo (URL, método, headers, IP)
- Contexto de usuario (user_id, email) extraído de JWT
- Releases versionados (rydercup-backend@1.8.0)
- Integración con Security Logging existente

**Impacto:** Visibilidad total en producción, debugging simplificado, métricas de performance, alertas automáticas. Puntuación OWASP A09: 9.5/10 → 10/10 (+0.5)

---

### Security - Dependency Audit ✅ COMPLETADO (19 Dic 2025)

**🔍 Auditoría de Vulnerabilidades en Dependencias** (OWASP A06)

- ✅ Herramientas de auditoría instaladas: safety 3.7.0 + pip-audit 2.10.0
- ✅ 6 CVEs detectados en 4 paquetes
- ✅ 5 CVEs resueltos (83.3% de éxito)
- ✅ Actualizaciones críticas aplicadas sin breaking changes
- ✅ Tests completos: 819/819 tests pasando (100%)

**Vulnerabilidades Resueltas:**
- ✅ CVE-2024-47874 (starlette): DoS via Memory Exhaustion → starlette 0.38.6 → 0.50.0
- ✅ CVE-2025-54121 (starlette): Event Loop Blocking → starlette 0.38.6 → 0.50.0
- ✅ CVE-2025-66418 (urllib3): Unlimited Decompression Chain → urllib3 2.5.0 → 2.6.0
- ✅ CVE-2025-66471 (urllib3): Streaming Decompression Memory Leak → urllib3 2.5.0 → 2.6.0
- ✅ CVE-2025-68146 (filelock): TOCTOU Race Condition → filelock 3.20.0 → 3.20.1

**Vulnerabilidades Monitoreadas:**
- ⏳ CVE-2024-23342 (ecdsa): Timing Attack - Sin fix disponible, bajo impacto (no usamos ECDSA)

**Actualizaciones Aplicadas:**
- `fastapi==0.115.0` → `fastapi==0.125.0`
- `starlette==0.38.6` → `starlette==0.50.0` (automático con FastAPI)
- `urllib3==2.5.0` → `urllib3==2.6.0`
- `filelock==3.20.0` → `filelock==3.20.1`
- `safety==3.7.0` (nuevo)
- `pip-audit==2.10.0` (nuevo)

**Archivos Modificados:**
- `requirements.txt` (6 paquetes actualizados/agregados)
- `.github/workflows/ci_cd_pipeline.yml` (job security_checks mejorado)

**CI/CD Integration:**
- ✅ Safety + pip-audit integrados en GitHub Actions
- ✅ Pipeline falla automáticamente si encuentra CVEs críticos
- ✅ Reportes JSON generados como artifacts (retención 30 días)
- ✅ Resumen de seguridad en cada push/PR

**Proceso de Auditoría:**
1. Instalación de herramientas (safety + pip-audit)
2. Escaneo de 130 dependencias (directas + transitivas)
3. Análisis y priorización de vulnerabilidades
4. Actualización de paquetes críticos
5. Validación con suite completa de tests

**Impacto:** Protección contra 5 vulnerabilidades críticas/altas (DoS, Memory Exhaustion, Race Conditions). Puntuación OWASP A06: 8.0/10 → 8.5/10 (+0.5). Compliance mejorado para Vulnerable and Outdated Components.

---

### Added - Structured Logging Enhancement ✅ COMPLETADO (17 Dic 2025)

**🔍 Correlation IDs para Trazabilidad de Requests** (OWASP A09)

- ✅ Middleware de Correlation ID implementado
- ✅ ContextVar para propagación async
- ✅ Header X-Correlation-ID en requests/responses
- ✅ UUID v4 automático si request no incluye header
- ✅ Tests completos: 819/819 tests pasando (100%)

**Archivos Creados:**
- `src/shared/infrastructure/http/correlation_middleware.py`
- `tests/unit/shared/infrastructure/http/test_correlation_middleware.py`

**Impacto:** Trazabilidad completa de requests, debugging simplificado en producción, preparación para OpenTelemetry.

---

### Added - Security Logging Avanzado ✅ COMPLETADO (17 Dic 2025)

**🔐 Sistema de Auditoría de Seguridad Completo** (OWASP A09)

- ✅ 8 Domain Events de seguridad (LoginAttempt, Logout, RefreshTokenUsed, RefreshTokenRevoked, PasswordChanged, EmailChanged, AccessDenied, RateLimitExceeded)
- ✅ SecurityLogger service con formato JSON estructurado
- ✅ Archivo dedicado: `logs/security_audit.log` con rotación automática (10MB x 5 backups)
- ✅ Severity levels con auto-ajuste (CRITICAL, HIGH, MEDIUM, LOW)
- ✅ Contexto HTTP completo: IP (X-Forwarded-For, X-Real-IP), User-Agent
- ✅ Integración en 4 use cases críticos (Login, Logout, RefreshToken, UpdateSecurity)
- ✅ Tests: 816/816 pasando (100%) - 27 tests nuevos

**Archivos Creados:**
- `src/shared/domain/events/security_events.py` (424 líneas)
- `src/shared/infrastructure/logging/security_logger.py` (485 líneas)
- Tests unitarios e integración (27 tests)

**Impacto:** Compliance OWASP A09, trazabilidad completa, detección de anomalías, información forense. Puntuación: 6/10 → 9/10 (+3.0)

---

### Added - Validaciones Pydantic Mejoradas ✅ COMPLETADO (17 Dic 2025)

**🛡️ Sistema de Validación y Sanitización Avanzado** (OWASP A03/A04)

- ✅ Sanitizadores HTML anti-XSS (sanitize_html, sanitize_all_fields)
- ✅ Validadores estrictos (EmailValidator RFC 5322, NameValidator)
- ✅ Límites de longitud centralizados (FieldLimits)
- ✅ Prevención de ataques de homógrafos (normalize_unicode)
- ✅ DTOs actualizados con @field_validator y max_length
- ✅ Tests unitarios: 56/56 pasando
- ✅ Suite completa: 789/789 tests pasando

**Archivos Creados:**
- `src/shared/application/validation/` (field_limits.py, sanitizers.py, validators.py)
- `tests/unit/shared/application/` (56 tests)

**Impacto:** Prevención XSS, validación estricta de formatos, límites consistentes. A03: 9.5/10 (+0.5), A04: 8.5/10

---

### Added - CORS Configuration Mejorada ✅ COMPLETADO (17 Dic 2025)

**🔒 Configuración CORS Centralizada y Segura** (OWASP A05/A01)

- ✅ Módulo `src/config/cors_config.py` con configuración centralizada
- ✅ Validación automática de orígenes (rechazo de wildcards, esquemas inválidos)
- ✅ Separación clara desarrollo/producción
- ✅ Whitelist estricta, fallback seguro en desarrollo
- ✅ allow_credentials=True (requerido para cookies httpOnly)
- ✅ Tests de integración: 11/11 pasando
- ✅ Suite completa: 733/733 tests pasando

**Archivos Creados:**
- `src/config/cors_config.py` (200+ líneas)
- `tests/integration/api/v1/test_cors_configuration.py` (11 tests)

**Impacto:** Whitelist estricta, control de acceso a nivel de origen. Puntuación: 9.0/10 → 9.5/10 (+0.5)

---

### Added - Session Timeout with Refresh Tokens ✅ COMPLETADO (16 Dic 2025)

**🕒 Mejora de Seguridad de Sesiones con Tokens de Renovación** (OWASP A01/A02/A07)

- ✅ RefreshToken entity con lógica de negocio (Value Objects: RefreshTokenId, TokenHash SHA256)
- ✅ Tabla `refresh_tokens` con 7 columnas, 3 índices, FK a users CASCADE
- ✅ SQLAlchemyRefreshTokenRepository implementado
- ✅ Access Token reducido de 60 min a 15 min, Refresh Token 7 días
- ✅ JWT Handler con create_refresh_token(), verify_refresh_token()
- ✅ Endpoint POST /api/v1/auth/refresh-token (nuevo)
- ✅ Login/Logout actualizados: 2 cookies httpOnly (access + refresh)
- ✅ Revocación de refresh tokens en BD al logout
- ✅ Tests: 722/722 pasando (100%) - +35 tests nuevos

**Archivos Creados:**
- 10 archivos nuevos (~1,078 líneas): Domain, Infrastructure, Application, API layers
- `InMemoryRefreshTokenRepository` para tests

**Security Benefits:**
- Access Token Duration: 60 min → 15 min (-75%)
- Token Revocation: ❌ → ✅ (+100%)
- Session Hijacking Window: -75%
- Logout Efectivo: ⚠️ → ✅ (+100%)

**Impacto:** Puntuación OWASP: 8.5/10 → 9.0/10 (+0.5). A01 (+0.3), A02 (+0.2)

---

### Added - Password Policy (OWASP ASVS V2.1) ✅ COMPLETADO (16 Dic 2025)

**🔑 Política de Contraseñas Robusta según Estándares de Seguridad**

- ✅ Longitud mínima: 12 caracteres (actualizado de 8, ASVS V2.1.1)
- ✅ Complejidad completa: Mayúsculas + Minúsculas + Dígitos + Símbolos (ASVS V2.1.2)
- ✅ Blacklist de contraseñas comunes (password, admin, qwerty, etc.) (ASVS V2.1.7)
- ✅ Hashing: bcrypt 12 rounds (producción), 4 rounds (tests) (ASVS V2.4.1)
- ✅ 681 tests actualizados (100% pasando)
- ✅ Script de migración: `fix_test_passwords.py` con 157 reemplazos automáticos

**Fix de Paralelización:**
- ✅ UUID único por test (test_db_{worker_id}_{uuid})
- ✅ Helper `get_user_by_email()` refactorizado
- ✅ 0 errores intermitentes en pytest-xdist

**Impacto:** Puntuación: 8.0/10 → 8.2/10 (+0.2)

---

### Added - httpOnly Cookies (JWT Authentication) ✅ COMPLETADO (16 Dic 2025)

**🍪 Protección de Tokens JWT contra Ataques XSS** (OWASP A01/A02)

- ✅ Cookie Handler centralizado (`src/shared/infrastructure/security/cookie_handler.py`)
- ✅ Flags de seguridad: httponly=True, secure=is_production(), samesite="lax", max_age=3600
- ✅ Middleware dual: cookies (prioridad 1) + headers (prioridad 2)
- ✅ Endpoints actualizados: /login, /verify-email, /logout
- ✅ Compatibilidad transitoria: token en cookie + body (LEGACY)
- ✅ Tests: 6/6 pasando (100%)

**Migration Path:**
- v1.8.0 (actual): Dual support (cookie + body)
- v1.9.0: Deprecation warning
- v2.0.0: BREAKING CHANGE (solo cookies)

**Impacto:** Puntuación: 8.2/10 → 8.5/10 (+0.3)

---

### Added - Rate Limiting con SlowAPI ✅ COMPLETADO (15 Dic 2025)

**🚦 Protección contra Brute Force, DoS y Abuso de API** (OWASP A04/A07)

- ✅ SlowAPI v0.1.9 integrado
- ✅ Módulo centralizado `src/config/rate_limit.py`
- ✅ Límite global: 100/minuto por IP
- ✅ Límites específicos: Login 5/min, Register 3/h, RFEG 5/h, Competitions 10/h
- ✅ Exception handler automático (HTTP 429)
- ✅ Tests: 5 tests de integración

**Archivos Creados:**
- `src/config/rate_limit.py`
- `tests/integration/api/v1/test_rate_limiting.py`

**Impacto:** Puntuación: 7.0/10 → 7.5/10 (+0.5)

---

### Added - Security Headers HTTP ✅ COMPLETADO (15 Dic 2025)

**🔒 Protección contra XSS, Clickjacking, MIME-sniffing y MITM** (OWASP A02/A03/A04/A05/A07)

- ✅ secure v0.3.0 integrado
- ✅ 6 Security Headers implementados:
  - Strict-Transport-Security: max-age=63072000; includeSubdomains
  - X-Frame-Options: SAMEORIGIN
  - X-Content-Type-Options: nosniff
  - Referrer-Policy: no-referrer, strict-origin-when-cross-origin
  - Cache-Control: no-store
  - X-XSS-Protection: 0 (desactivado, obsoleto)
- ✅ Middleware global (aplica a todas las respuestas)
- ✅ Tests: 7 tests de integración

**Archivos Creados:**
- `tests/integration/api/v1/test_security_headers.py` (7 tests)

**Impacto:** Puntuación: 7.5/10 → 8.0/10 (+0.5)

---

## [1.10.0] - 2025-11-30

### Added
- ✅ CI/CD Pipeline con GitHub Actions (7 jobs paralelos: Preparation, Unit Tests, Integration Tests, Security Scan, Code Quality, Type Checking, Database Migrations)
- ✅ Mypy Configuration pragmática para SQLAlchemy imperative mapping (173 archivos validados, 0 errores)
- ✅ Gitleaks Configuration con whitelist para false positives
- ✅ Pipeline: ~3 minutos duración, 672 tests (100% passing)

### Fixed
- ✅ Ruff Linting: exception chaining (`from e`), import sorting
- ✅ Mypy Type Checking: reducción de errores 127 → 0

### Documentation
- ✅ ADR-021: GitHub Actions CI/CD Pipeline
- ✅ README.md: Badge de CI/CD, estadísticas actualizadas

---

## [1.9.2] - 2025-11-25

### Fixed
- ✅ Refactorización de complejidad cognitiva en `competition_routes.py` (34 → <15, mejora 56%)
- ✅ 6 funciones más pequeñas para mejor mantenibilidad
- ✅ Removido `async` innecesario de funciones síncronas
- ✅ Variables no utilizadas eliminadas en tests
- ✅ 672/672 tests pasando (100%)

---

## [1.9.1] - 2025-11-25

### Fixed
- ✅ Hotfix Deploy: Corregidas dependencias en `requirements.txt`
- ✅ Separados `pytest-asyncio` y `pytest-cov` en líneas individuales

### Chore
- ✅ Reorganizado `.gitignore`
- ✅ Añadido `sonar-project.properties`

---

## [1.9.0] - 2025-11-25

### Added
- ✅ Aumento de cobertura de tests (7 use cases de Enrollment)

### Fixed
- ✅ Corrección de tests de integración (helpers de autenticación)
- ✅ Mejora de rendimiento con paralelización (`pytest-xdist`)

---

## [1.8.1] - 2025-11-25

### Changed
- ✅ BREAKING CHANGE: Respuestas de competiciones incluyen campo `countries` (array)

### Documentation
- ✅ Actualizado `ROADMAP.md` y `API.md` a v1.8.0

---

## [1.8.0] - 2025-11-24

### Fixed
- ✅ CRITICAL BUG: AttributeError en serialización de Handicap
- ✅ Nuevo `HandicapDecorator` (TypeDecorator) reemplaza composite mapping
- ✅ Maneja correctamente valores NULL, valida rango -10.0 a 54.0
- ✅ Tests: 663/663 pasando (100%, mejora del 15.84%)
- ✅ Lecciones: TypeDecorator para Value Objects de 1 columna nullable

---

## [1.7.0] - 2025-11-23

### Added
- ✅ User Nationality Support (`country_code` opcional con CountryCode VO)
- ✅ Creator Nested Object en Competition responses (reduce ~60% llamadas API)
- ✅ My Competitions Filter (`my_competitions` query parameter)
- ✅ Search Parameters (search_name, search_creator con ILIKE case-insensitive)
- ✅ User Nested Object en Enrollment responses
- ✅ Cross-Module Dependency Injection (UserUoW en Competition/Enrollment modules)

### Changed
- ✅ Database Migrations consolidadas: 6 migraciones → 1 migración inicial
- ✅ Schema completo: users, competitions, enrollments, countries, country_adjacencies
- ✅ Seeds: 198 países + 614 fronteras

### Tests
- ✅ 663/663 tests pasando (100%)

---

## [1.6.4] - 2025-11-22

### Added
- ✅ Soporte dual de formatos: alias `number_of_players` → `max_players`
- ✅ Array de países: campo `countries` con conversión automática
- ✅ CountryResponseDTO con detalles completos (código, nombre_en, nombre_es)
- ✅ Compatibilidad backward con formato legacy

---

## [1.6.3] - 2025-11-20

### Security
- ✅ Corrección de divulgación de información en login
- ✅ Eliminada validación `min_length=8` en LoginRequestDTO
- ✅ Error genérico "Credenciales incorrectas" para todos los fallos

---

## [1.6.2] - 2025-11-19

### Fixed
- ✅ Update Competition Endpoint: actualiza correctamente todos los campos de negocio en DRAFT

### Changed
- ✅ Documentación: `docs/API.md` y `postman_collection.json` actualizados

---

## [1.6.1] - 2025-11-19

### Fixed
- ✅ Tests: de 618 a 651 (+33 arreglados), tasa de éxito 93.35% → 98.34%
- ✅ Competition routes: llamadas a use cases de state transitions corregidas
- ✅ Entidades: añadidos métodos `_ensure_domain_events()` y `_add_domain_event()`
- ✅ Mappers: Location composite con named parameters, mapeo explícito `max_players`
- ✅ Tests: seed extraído a función helper, país JP añadido

---

## [1.6.0] - 2025-11-18

### Added
- ✅ Competition Module COMPLETO: 7 use cases de Enrollment
- ✅ 8 endpoints REST de Enrollments (request, direct, list, approve, reject, cancel, withdraw, set-handicap)
- ✅ Reglas de negocio: autorización creador, validaciones estado, no duplicados
- ✅ Total módulo Competition: 20 endpoints (10 Competition + 8 Enrollment + 2 Countries)

---

## [1.5.1] - 2025-11-18

### Added
- ✅ 2 endpoints de Countries (GET /countries, GET /countries/{code}/adjacent)
- ✅ CountryResponseDTO con campos: code, name_en, name_es
- ✅ Router registrado en `main.py` con tag "Countries"

---

## [1.5.0] - 2025-11-18

### Added
- ✅ Competition Module API REST Layer (FASE 1 COMPLETA)
- ✅ 10 endpoints de Competition (CRUD + 5 state transitions)
- ✅ CompetitionDTOMapper con campos calculados (is_creator, enrolled_count, location)
- ✅ JWT authentication + autorización (solo creador puede modificar)
- ✅ Total código nuevo: ~1,422 líneas

---

## [1.4.0] - 2025-11-18

### Added
- ✅ Competition Module Infrastructure Layer
- ✅ 2 migraciones Alembic (4 tablas + seed: 166 países + 614 fronteras)
- ✅ 3 repositorios async (Competition, Enrollment, Country)
- ✅ SQLAlchemyCompetitionUnitOfWork

---

## [1.3.0] - 2025-11-18

### Added
- ✅ Competition Module Domain + Application Layer COMPLETO
- ✅ 2 entidades: Competition, Enrollment con máquinas de estado
- ✅ 9 Value Objects con validaciones completas
- ✅ 11 Domain Events (7 Competition + 4 Enrollment)
- ✅ 9 use cases (4 CRUD + 5 state transitions) con 58 tests
- ✅ LocationBuilder Domain Service
- ✅ Total: 173 tests pasando (100% cobertura Competition Module)

---

## [1.2.0] - 2025-11-14

### Added
- ✅ 24 tests para Email Verification (cobertura completa)
- ✅ Corregidos todos los warnings de pytest (0 warnings)
- ✅ Total: 420 tests pasando
- ✅ Helper: `get_user_by_email()` en conftest.py

---

## [1.1.0] - 2025-11-12

### Added
- ✅ Email Verification con tokens únicos
- ✅ Integración Mailgun (región EU), templates bilingües (ES/EN)
- ✅ Domain event: EmailVerifiedEvent
- ✅ Migración: campos `email_verified` y `verification_token`
- ✅ Endpoint: POST /api/v1/auth/verify-email
- ✅ Tests completos: 24 tests (unit, integration, E2E)

---

## [1.0.0] - 2025-11-01

### Added
- ✅ Clean Architecture + DDD completo
- ✅ User management (registro, autenticación, perfil)
- ✅ JWT authentication con tokens Bearer
- ✅ Handicap system con integración RFEG
- ✅ 8 endpoints API funcionales

### Architecture
- ✅ Repository Pattern con Unit of Work
- ✅ Domain Events Pattern
- ✅ Value Objects para validaciones
- ✅ External Services Pattern (Mailgun, RFEG)

### Testing
- ✅ 420 tests pasando (unit + integration)
- ✅ Cobertura >90% en lógica de negocio

### Infrastructure
- ✅ Docker + Docker Compose
- ✅ PostgreSQL 15 con Alembic
- ✅ FastAPI 0.115+, Python 3.12+

---

## Versionado

- **Mayor (X.0.0)**: Cambios incompatibles en la API
- **Menor (1.X.0)**: Nueva funcionalidad compatible hacia atrás
- **Parche (1.0.X)**: Correcciones de bugs compatibles
