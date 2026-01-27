# 🗺️ Roadmap - RyderCupFriends Backend

> **Versión Actual:** 1.13.1 (Producción)
> **Última actualización:** 27 Ene 2026
> **OWASP Score:** 9.4/10

---

## 📊 Estado Actual

**Tests:** 1,066 (99.9% passing, ~60s) | **Endpoints:** 39 REST API | **CI/CD:** GitHub Actions (10 jobs, ~3min)

**Módulos Completados:**
- **User:** Login, Register, Email Verification, Password Reset, Handicap (RFEG), Device Fingerprinting
- **Competition:** CRUD, Enrollments, Countries (166 + 614 fronteras), State Machine (6 estados)
- **Security:** Rate Limiting, httpOnly Cookies, Session Timeout, CORS, CSRF, Account Lockout, Password History, IP Spoofing Prevention

**OWASP Top 10:** A01(10/10), A02(10/10), A03(10/10), A04(9/10), A05(9.5/10), A06(9/10), A07(9.5/10), A08(7/10), A09(10/10), A10(8/10) = **9.4/10** ⭐

---

## 🎯 Roadmap Futuro

### v2.1.0 - Competition Module Evolution ⭐ PRIORIDAD MÁXIMA

**Fechas:** 27 Ene - 17 Mar 2026 (7 semanas) | **Esfuerzo:** 330h | **Tests:** 75+ | **Endpoints:** 30

**Objetivo:** Sistema completo de gestión de torneos Ryder Cup con campos de golf, planificación, live scoring con validación dual y leaderboards en tiempo real.

---

#### 📅 Sprint Breakdown

| Sprint | Fechas | Horas | Endpoints | Tests | Sync Point |
|--------|--------|-------|-----------|-------|------------|
| **Sprint 1** | 27 Ene - 6 Feb | 60h | 10 (RBAC + Golf Courses) | 15+ | 🔄 Vie 31 Ene |
| **Sprint 2** | 7 Feb - 17 Feb | 70h | 10 (Rounds + Matches) | 18+ | 🔄 Vie 14 Feb |
| **Sprint 3** | 18 Feb - 24 Feb | 48h | 5 (Invitations) | 12+ | 🔄 Vie 21 Feb |
| **Sprint 4** | 25 Feb - 10 Mar | 92h | 4 (Scoring) | 20+ | 🔄 Vie 7 Mar |
| **Sprint 5** | 11 Mar - 17 Mar | 60h | 2 (Leaderboards) | 10+ | 🔄 Vie 14 Mar |

---

#### Sprint 1: RBAC Foundation & Golf Courses (1.5 sem)

**RBAC Endpoints (4):**
```
POST   /api/v1/admin/users/{user_id}/roles
DELETE /api/v1/admin/users/{user_id}/roles/{role_name}
GET    /api/v1/users/me/roles
GET    /api/v1/admin/users?role=ADMIN|CREATOR|PLAYER
```

**Golf Courses Endpoints (6):**
```
POST /api/v1/golf-courses/request          # Creator solicita
GET  /api/v1/golf-courses/{id}             # Detalle (tees + holes)
GET  /api/v1/golf-courses?approval_status=APPROVED
GET  /api/v1/admin/golf-courses/pending
PUT  /api/v1/admin/golf-courses/{id}/approve
PUT  /api/v1/admin/golf-courses/{id}/reject
```

**DTOs Clave:**
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

**Validaciones:** 18 hoyos exactos, stroke index 1-18 únicos, par total 66-76, 2-6 tees

---

#### Sprint 2: Competition Scheduling (1.5 sem)

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

**Validaciones:** SINGLES (1 player/team), FOURBALL/FOURSOMES (2 players/team), tee debe existir en golf course, jugadores enrollados con status APPROVED

---

#### Sprint 3: Invitations System (1 sem)

**Endpoints (5):**
```
POST /api/v1/competitions/{comp_id}/invitations        # By user ID
POST /api/v1/competitions/{comp_id}/invitations/by-email
GET  /api/v1/invitations/me                            # Pending
POST /api/v1/invitations/{invitation_id}/respond       # Accept/Decline
GET  /api/v1/competitions/{comp_id}/invitations        # Creator view
```

**Security:**
- Token: 256-bit (`secrets.token_urlsafe(32)`), SHA256 hash en BD
- Expiration: 7 días, Celery background task (cada 6h)
- Auto-enrollment: ACCEPTED → Enrollment status APPROVED (bypass approval)

**Email Templates:** Bilingües ES/EN, Mailgun

---

#### Sprint 4: Scoring System (2 sem)

**Endpoints (4):**
```
POST /api/v1/matches/{match_id}/scores/holes/{hole_number}
GET  /api/v1/matches/{match_id}/scoring-view           # Vista 3 tabs
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
        """Net score = gross - strokes_received. Menor net gana hoyo."""
        # Returns: "Team A leads 2UP" | "All Square" | "Team B wins 3&2"
```

**Vista Unificada:**
```python
class MatchScoringView(BaseModel):
    current_hole: int              # Siguiente hoyo sin completar
    hole_info: HoleScoreDetail     # Tab 1: Input
    scorecard: list[HoleScoreDetail]  # Tab 2: Scorecard
    match_standing: MatchStanding  # Tab 3: Leaderboard
    can_submit: bool               # True si 18/18 validados
```

---

#### Sprint 5: Leaderboards & Optimization (1 sem)

**Endpoints (2):**
```
GET /api/v1/competitions/{comp_id}/leaderboard       # Público, completo
GET /api/v1/competitions/{comp_id}/leaderboard/live  # Solo IN_PROGRESS
```

**Optimizaciones:**
- Índices DB: (competition_id, status), (match_id, hole_number)
- Redis cache (TTL 30s) para matches live
- Eager loading (selectinload) - evitar N+1 queries
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

#### 🗄️ Nuevas Entidades (14 total)

**Domain Layer:**
- `Role`, `UserRole` - RBAC formal
- `GolfCourse`, `Tee`, `Hole` - Gestión campos (3 tablas)
- `Round`, `Match` - Planificación (2 tablas)
- `Invitation` - Sistema invitaciones (1 tabla)
- `HoleScore` - Anotación scores (1 tabla)

**Enums:** RoleName, GolfCourseType, TeeCategory, ApprovalStatus, MatchFormat, MatchStatus, InvitationStatus, ScoreStatus

---

#### ✅ Acceptance Criteria

**Funcionalidad:**
- 30 endpoints implementados + Swagger docs
- RBAC funcional (ADMIN, CREATOR, PLAYER)
- Playing handicaps auto-calculados (WHS)
- Validación dual (player + marker)
- Leaderboard público real-time

**Testing:**
- ≥85% coverage
- 75+ tests (unit + integration)
- 0 failing en CI/CD

**Performance:**
- API p95 < 200ms
- Eager loading + Redis cache
- Índices DB críticos

**Security:**
- Authorization checks todos endpoints
- Pydantic validation
- CORS configurado

**Documentation:**
- Swagger completo (descriptions, examples)
- 3 ADRs nuevos (031, 032, 033)
- 10 Alembic migrations

---

#### 🔄 Handoffs con Frontend

| Sprint | Backend Entrega | Frontend Consume | Sync Point |
|--------|----------------|------------------|------------|
| Sprint 1 | RBAC + Golf Courses | User Management + Course Selector | Vie 31 Ene |
| Sprint 2 | Scheduling | Drag-drop + Match Wizard | Vie 14 Feb |
| Sprint 3 | Invitations | Invitation Cards | Vie 21 Feb |
| Sprint 4 | Scoring | 3 Tabs + Validation | Vie 7 Mar |
| Sprint 5 | Leaderboards | Public Leaderboard + Polling | Vie 14 Mar |

**Protocolo:** Backend despliega a dev → actualiza Swagger → notifica Frontend (viernes) → integración (lunes)

---

#### 🔗 ADRs Relacionados

**Existentes:**
- **ADR-020:** Competition Module Domain Design (v1.x baseline)
- **ADR-025:** Competition Module Evolution v2.1.0 (umbrella ADR - 9 Ene 2026)
- **ADR-026:** Playing Handicap WHS Calculation (9 Ene 2026)

**Nuevos (Sprint 1):**
- **ADR-031:** Match Play Scoring Calculation (27 Ene 2026)
- **ADR-032:** Golf Course Approval Workflow Details (27 Ene 2026)
- **ADR-033:** Invitation Token Security and Auto-Enrollment (27 Ene 2026)

---

### v1.14.0 - Compliance & Features (2-3 semanas)

**Objetivo:** GDPR compliance + UX improvements

**Features:**
1. **GDPR Compliance** (8-10h):
   - GET `/api/v1/users/me/export` (JSON completo)
   - DELETE `/api/v1/users/me` (soft delete)
   - Anonimización datos, consent logging, retention policies (90 días)

2. **Audit Logging** (6-8h):
   - Modelo `AuditLog` en BD (user_id, action, resource, changes, timestamp, ip)
   - Retención 90 días, exportación CSV/JSON

3. **Sistema Avatares** (4-6h):
   - Campo `avatar_url`, storage Cloudinary/S3
   - PUT `/api/v1/users/me/avatar`, DELETE `/api/v1/users/me/avatar`
   - Validación: max 2MB, jpg/png/webp

4. **Error Handling Unificado** (3-4h):
   - Exception handlers centralizados
   - Formato estándar: `{"error": {"code": "...", "message": "...", "details": {}}}`
   - ErrorCode enum (40+ códigos), i18n (ES/EN)

**Total:** ~21-28 horas

---

### v1.15.0 - AI & RAG Module (2-3 semanas)

**Objetivo:** Chatbot asistente de reglas de golf

**Stack:** LangChain + Pinecone + OpenAI GPT-4o-mini | **Costo:** $1-2/mes

**Features:**
- RAG chatbot con búsqueda semántica
- Solo disponible si `competition.status == IN_PROGRESS`
- Rate limiting dual-layer: 10/día global, 3/día player, 6/día creator
- Caché Redis (TTL 7 días, 80% hit rate esperado)
- Pre-FAQs (20-30 hardcodeadas), temperatura 0.3

**Arquitectura:**
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

**Tests:** 60+ tests (mocks OpenAI)

**Knowledge Base:** R&A Official Rules of Golf

---

### v2.0.0 - Major Release (BREAKING CHANGES) (4-6 meses)

**Objetivo:** Escalabilidad + Features avanzadas

**Breaking Changes:**
- ❌ Eliminar tokens del response body (solo httpOnly cookies)
- ❌ Eliminar compatibilidad headers Authorization (deprecation 6 meses)
- ❌ API v1 deprecada → API v2

**Security:**
- OAuth 2.0 / Social Login (Google, Apple, GitHub)
- WebAuthn (Hardware Security Keys)
- Advanced Threat Detection (ML-based anomaly)
- SOC 2 Compliance preparation

**Features:**
- Analytics y estadísticas avanzadas
- Integración USGA, Golf Australia
- Push notifications (Firebase)
- Sistema de pagos (Stripe)
- Rankings globales
- Galería de fotos (AWS S3 + CloudFront)

**Infrastructure:**
- Kubernetes deployment
- Blue-green deployments
- Auto-scaling (HPA)
- CDN para assets estáticos
- Database replication + read replicas
- Multi-region deployment

---

## 📅 Timeline Recomendado

```
2026 Q1  │ ✅ v1.13.0 - Security Hardening (COMPLETADO)
          │ ✅ v1.13.1 - Device Detection + HTTP Security (COMPLETADO)
          │ ⭐ v2.1.0 - Competition Module Evolution (27 Ene - 17 Mar) ← EN CURSO
2026 Q2  │ v1.14.0 - Compliance (GDPR, Audit Logging, Avatares)
          │ v1.15.0 - AI & RAG Module (Golf Rules Assistant)
2026 Q3  │ v2.1.1 - WebSocket, Puntos custom
          │ v2.1.2 - Stats avanzadas, Export PDF
2026 Q4+ │ v2.0.0 - Major Release (planificación + desarrollo)
```

---

## 🔗 Referencias

**Documentación:**
- **ADRs:** `docs/architecture/decisions/ADR-*.md` (33 ADRs totales)
- **CHANGELOG:** `CHANGELOG.md` (historial detallado de cambios)
- **CLAUDE:** `CLAUDE.md` (contexto completo del proyecto)
- **Frontend ROADMAP:** `../RyderCupWeb/ROADMAP.md`
- **DATABASE_ERD:** `docs/DATABASE_ERD.md`

**Standards:**
- **OWASP Top 10:** https://owasp.org/www-project-top-ten/
- **ASVS:** https://owasp.org/www-project-application-security-verification-standard/
- **WHS:** https://www.usga.org/handicapping.html
- **R&A Rules:** https://www.randa.org/en/rog/the-rules-of-golf

**ADRs Clave v2.1.0:**
- ADR-020: Competition Module Domain Design (baseline)
- ADR-025: Competition Module Evolution v2.1.0 (umbrella)
- ADR-026: Playing Handicap WHS Calculation
- ADR-031: Match Play Scoring Calculation
- ADR-032: Golf Course Approval Workflow Details
- ADR-033: Invitation Token Security

---

## 📜 Historial de Versiones Completadas

### v1.13.1 - Current Device Detection + HTTP Security (18 Ene 2026) ✅

**Cambios:**
- Campo `is_current_device` en GET /users/me/devices (UX improvement)
- Helper `http_context_validator.py` centralizado (306 líneas)
- IP spoofing prevention con whitelist `TRUSTED_PROXIES`
- Sentinel validation (rechaza "unknown", "", localhost)
- +36 tests de seguridad HTTP (100% passing)
- **OWASP:** 9.2 → 9.4 (+0.2) - A01(10/10), A03(10/10)

---

### v1.13.0 - Security Hardening (9 Ene 2026) ✅

**Features:**
1. **Account Lockout:** Bloqueo tras 10 intentos, auto-desbloqueo 30 min, endpoint manual unlock
2. **CSRF Protection:** Triple capa (header, cookie, SameSite), token 256-bit, middleware
3. **Password History:** Previene reutilización últimas 5 contraseñas, bcrypt hashes, GDPR compliant
4. **Device Fingerprinting:** SHA256 fingerprint, listado/revocación dispositivos, soft delete, auto-registro en login/refresh

**Tests:** 905 → 1,021 (+116 tests)
**OWASP:** 8.5 → 9.2 (+0.7)
**ADRs:** ADR-027, ADR-028, ADR-029, ADR-030

---

### v1.12.1 - Snyk Code SAST (5 Ene 2026) ✅

- Snyk Code (SAST) en CI/CD pipeline
- Detección: SQL Injection, XSS, Hardcoded secrets, Path Traversal, Weak Crypto
- Reportes separados: dependencies + code
- Artifacts retención 30 días

---

### v1.12.0 - Snyk Vulnerability Fixes (3 Ene 2026) ✅

- 6 CVEs resueltos: authlib, setuptools, zipp, marshmallow
- Snyk integration en CI/CD (severity: HIGH)
- Tests: 905/905 (100%)

---

### Versiones Anteriores (v1.0.0 - v1.11.0)

| Versión | Fecha | Features Principales |
|---------|-------|---------------------|
| **v1.11.0** | 26 Dic 2025 | Password Reset System (token 256-bit, email bilingües, +51 tests) |
| **v1.10.0** | 30 Nov 2025 | CI/CD Pipeline GitHub Actions (7 jobs paralelos, Mypy, Gitleaks) |
| **v1.9.2** | 25 Nov 2025 | Refactorización complejidad cognitiva (competition_routes.py) |
| **v1.9.0** | 25 Nov 2025 | Aumento cobertura tests Enrollment (7 use cases) |
| **v1.8.1** | 25 Nov 2025 | BREAKING: Competiciones incluyen campo `countries` (array) |
| **v1.8.0** | 24 Nov 2025 | Security Enhancements (httpOnly Cookies, Refresh Tokens, Rate Limiting, CORS, Security Headers, Logging, Correlation IDs, Validation, Sentry) |
| **v1.7.0** | 23 Nov 2025 | User Nationality, Creator Nested, My Competitions Filter, Search Parameters |
| **v1.6.4** | 22 Nov 2025 | Soporte dual formatos: `number_of_players` → `max_players` |
| **v1.6.0** | 18 Nov 2025 | Competition Module API REST (20 endpoints: 10 Competition + 8 Enrollment + 2 Countries) |
| **v1.5.0** | 18 Nov 2025 | Competition Module Infrastructure (Alembic migrations: 4 tablas + 166 países + 614 fronteras) |
| **v1.3.0** | 18 Nov 2025 | Competition Module Domain + Application (173 tests, 11 domain events) |
| **v1.2.0** | 14 Nov 2025 | Email Verification (24 tests, Mailgun integration) |
| **v1.1.0** | 12 Nov 2025 | Email Verification System (tokens únicos, templates bilingües) |
| **v1.0.0** | 1 Nov 2025 | Clean Architecture + DDD, User Module, JWT Auth, Handicap RFEG, 420 tests |

**Ver detalles completos:** `CHANGELOG.md`

---

**Próxima Revisión:** v2.1.0 Sprint 1 (31 Ene 2026)
**Responsable:** Equipo Backend
