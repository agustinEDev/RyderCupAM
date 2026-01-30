# 🗺️ Roadmap - RyderCupFriends Backend

> **Current Version:** 2.0.0 (Production)
> **Last Updated:** Jan 29, 2026
> **OWASP Score:** 9.4/10

---

## 📊 Current Status

**Tests:** 1,091 (100% passing, ~65s) | **Endpoints:** 40 REST API | **CI/CD:** GitHub Actions (10 jobs, ~3min)

**Completed Modules:**
- **User:** Login, Register, Email Verification, Password Reset, Handicap (RFEG), Device Fingerprinting, RBAC Foundation
- **Competition:** CRUD, Enrollments, Countries (166 + 614 borders), State Machine (6 states)
- **Security:** Rate Limiting, httpOnly Cookies, Session Timeout, CORS, CSRF, Account Lockout, Password History, IP Spoofing Prevention

**OWASP Top 10:** A01(10/10), A02(10/10), A03(10/10), A04(9/10), A05(9.5/10), A06(9/10), A07(9.5/10), A08(7/10), A09(10/10), A10(8/10) = **9.4/10** ⭐

---

## 🎯 Future Roadmap

### v2.0.1 - Competition Module Evolution ⭐ TOP PRIORITY

**Dates:** Jan 27 - Mar 17, 2026 (7 weeks) | **Effort:** 330h | **Tests:** 75+ | **Endpoints:** 30

**Goal:** Complete Ryder Cup tournament management system with golf courses, scheduling, live scoring with dual validation, and real-time leaderboards.

**Note:** Minor version bump (v2.0.0 was RBAC Foundation). Major changes: 30 endpoints, 12 entities, 7 weeks development.

---

#### 📅 Sprint Breakdown

| Sprint | Dates | Hours | Endpoints | Tests | Sync Point |
|--------|-------|-------|-----------|-------|------------|
| **Sprint 1** | Jan 27 - Feb 6 | 60h | 7 (RBAC + Golf Courses) | 25+ | 🔄 Fri, Jan 31 |
| **Sprint 2** | Feb 7 - Feb 17 | 70h | 10 (Rounds + Matches) | 18+ | 🔄 Fri, Feb 13 |
| **Sprint 3** | Feb 18 - Feb 24 | 48h | 5 (Invitations) | 12+ | 🔄 Fri, Feb 20 |
| **Sprint 4** | Feb 25 - Mar 10 | 92h | 4 (Scoring) | 20+ | 🔄 Fri, Mar 6 |
| **Sprint 5** | Mar 11 - Mar 17 | 60h | 2 (Leaderboards) | 10+ | 🔄 Fri, Mar 13 |

---

#### Sprint 1: RBAC Foundation v2.0.0 (✅ COMPLETED: Jan 29, 2026)

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

**Golf Courses Endpoints (6):**
```
POST /api/v1/golf-courses/request          # Creator requests
GET  /api/v1/golf-courses/{id}             # Details (tees + holes)
GET  /api/v1/golf-courses?approval_status=APPROVED
GET  /api/v1/admin/golf-courses/pending
PUT  /api/v1/admin/golf-courses/{id}/approve
PUT  /api/v1/admin/golf-courses/{id}/reject
```
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

#### Sprint 2: Competition Scheduling (1.5 weeks)

**Code Quality Refactor (Priority):**
- **Issue**: CodeRabbit #2 - Replace fragile string matching with exception subclasses
- **Files**: `business_rule_violation.py`, `competition_policy.py`, `request_enrollment_use_case.py`
- **Action**: Create `DuplicateEnrollmentViolation`, `InvalidCompetitionStatusViolation`, etc.
- **Benefit**: Type-safe exception handling, better DDD, maintainable
- **Tests**: Update ~20 tests (CompetitionPolicy + use cases)
- **Time**: 2-3 hours

**Rounds Endpoints (4):**
```
POST   /api/v1/competitions/{comp_id}/rounds
PUT    /api/v1/rounds/{round_id}
DELETE /api/v1/rounds/{round_id}
GET    /api/v1/competitions/{comp_id}/schedule  # Rounds + matches nested
```

**Matches Endpoints (6):**
```
POST   /api/v1/rounds/{round_id}/matches
GET    /api/v1/matches/{match_id}
PUT    /api/v1/matches/{match_id}/players
PUT    /api/v1/matches/{match_id}/status
POST   /api/v1/matches/{match_id}/walkover
DELETE /api/v1/matches/{match_id}
```

**Playing Handicap Calculation (Domain Service):**
```python
class PlayingHandicapCalculator:
    """WHS Official: PH = (HI × SR / 113) + (CR - Par)"""
    @staticmethod
    def calculate(handicap_index: float, tee: Tee, course_par: int) -> int:
        slope_factor = tee.slope_rating / 113
        ph = (handicap_index * slope_factor) + (tee.course_rating - course_par)
        return round(ph)
```

**Validations:** SINGLES (1 player/team), FOURBALL/FOURSOMES (2 players/team), tee must exist in golf course, players must be enrolled with APPROVED status.

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

#### 🗄️ New Entities (12 total)

**Domain Layer:**
- `GolfCourse`, `Tee`, `Hole` - Golf Course Management (3 tables)
- `Round`, `Match` - Scheduling (2 tables)
- `Invitation` - Invitation System (1 table)
- `HoleScore` - Score Annotation (1 table)

**Enums:** GolfCourseType, TeeCategory, ApprovalStatus, MatchFormat, MatchStatus, InvitationStatus, ScoreStatus

---

#### ✅ Acceptance Criteria

**Functionality:**
- 30 endpoints implemented + Swagger docs
- Functional RBAC (ADMIN, CREATOR, PLAYER) using a simplified, table-less design.
- Auto-calculated playing handicaps (WHS)
- Dual validation (player + marker)
- Public real-time leaderboard

**Testing:**
- ≥85% coverage
- 75+ tests (unit + integration)
- 0 failing in CI/CD

**Performance:**
- API p95 < 200ms
- Eager loading + Redis cache
- Critical DB indexes

**Security:**
- Authorization checks on all endpoints
- Pydantic validation
- Configured CORS

**Documentation:**
- Complete Swagger (descriptions, examples)
- 3 new ADRs (031, 032, 033)
- 10 Alembic migrations

---

#### 🔄 Handoffs with Frontend

| Sprint | Backend Delivers | Frontend Consumes | Sync Point |
|--------|----------------|------------------|------------|
| Sprint 1 | RBAC + Golf Courses | User Management + Course Selector | Fri, Jan 31 |
| Sprint 2 | Scheduling | Drag-drop + Match Wizard | Fri, Feb 14 |
| Sprint 3 | Invitations | Invitation Cards | Fri, Feb 21 |
| Sprint 4 | Scoring | 3 Tabs + Validation | Fri, Mar 7 |
| Sprint 5 | Leaderboards | Public Leaderboard + Polling | Fri, Mar 14 |

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
          │ ⭐ v2.0.1 - Competition Module Evolution (Jan 27 - Mar 17) ← IN PROGRESS
2026 Q2  │ v2.1.0 - Compliance (GDPR, Audit Logging, Avatars)
          │ v2.2.0 - AI & RAG Module (Golf Rules Assistant)
2026 Q3  │ v2.1.1 - WebSocket, Custom points
          │ v2.1.2 - Advanced Stats, Export PDF
2026 Q4+ │ v3.0.0 - Major Release (planning + development)
```

---

## 🔗 References

**Documentation:**
- **ADRs:** `docs/architecture/decisions/ADR-*.md` (33 total ADRs)
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