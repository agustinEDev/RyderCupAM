# 🗺️ Roadmap - RyderCupFriends Backend

> **Versión Actual:** 1.13.1 (COMPLETADO)
> **Última actualización:** 18 Ene 2026
> **Estado:** ✅ Producción (v1.13.1 - Current Device Detection + HTTP Security Enhancements)
> **OWASP Score:** 9.4/10 (Account Lockout + CSRF + Password History + Device Fingerprinting + IP Spoofing Prevention)

---

## 📊 Estado Actual

### Métricas
- **Tests:** 1,066 (99.9% passing, ~60s) - +36 HTTP Security, +99 Device Fingerprinting, +11 CSRF, +5 Account Lockout
- **Endpoints:** 39 REST API - +2 device endpoints (/me/devices GET/DELETE)
- **Módulos:** User, Competition, Enrollment, Countries
- **CI/CD:** GitHub Actions (10 jobs paralelos, ~3min) - Security Tests + Trivy
- **Deployment:** Render.com + Docker + PostgreSQL

### Completado (v1.0.0 - v1.13.1)

| Componente | Features |
|-----------|----------|
| **User Module** | Login, Register, Email Verification, Password Reset, Handicap (RFEG), Profile |
| **Competition Module** | CRUD, State Machine (6 estados), Enrollments, Countries (166 + 614 fronteras) |
| **Security (v1.8.0 - v1.13.1)** | Rate Limiting, httpOnly Cookies, Session Timeout (15min/7d), CORS, XSS Protection, Security Logging, Sentry, Dependency Audit (Safety + pip-audit + Snyk Code SAST), Account Lockout (v1.13.0), CSRF Protection (v1.13.0), Password History (v1.13.0), Device Fingerprinting (v1.13.0), **IP Spoofing Prevention (v1.13.1)**, **HTTP Validation (v1.13.1)** |
| **Testing** | 1,066 tests (unit + integration + security), CI/CD automático |

### OWASP Top 10 Coverage

| Categoría | Score | Protecciones |
|-----------|-------|--------------|
| A01: Access Control | **10/10** | JWT, Refresh Tokens, Session Timeout, Authorization, CSRF Protection, Device Fingerprinting, **IP Spoofing Prevention (v1.13.1)** ⭐ |
| A02: Crypto Failures | 10/10 | bcrypt (12 rounds), httpOnly Cookies, HSTS, Tokens seguros |
| A03: Injection | 10/10 | SQLAlchemy ORM, HTML Sanitization, Pydantic Validation, **Sentinel Validation (v1.13.1)** ⭐ |
| A04: Insecure Design | 9/10 | Rate Limiting (5/min login), Field Limits, Password Policy |
| A05: Misconfiguration | 9.5/10 | Security Headers, CORS Whitelist, Secrets Management |
| A06: Vulnerable Components | 9.0/10 | Triple Audit (Safety + pip-audit + Snyk), Auto-updates, 6 CVEs resueltos |
| A07: Auth Failures | 9.5/10 | Password Policy (ASVS V2.1), Session Timeout, Rate Limiting, Account Lockout, Password History |
| A08: Data Integrity | 7/10 | API Versioning |
| A09: Logging | 10/10 | Security Audit Trail, Correlation IDs, Sentry (APM + Profiling) |
| A10: SSRF | 8/10 | Input Validation |
| **Promedio** | **9.4/10** | Suma: 94.0 puntos / 10 categorías = 9.40 ⭐ |

---

## 🎯 Roadmap Futuro

### v1.13.1 - Bugfix + Security Enhancements ✅ COMPLETADO - 18 Ene 2026

**Objetivo:** Añadir campo `is_current_device` + mejoras críticas de seguridad HTTP.

**Estado:** ✅ Completado (18 Ene 2026)

**Branch:** `feature/detect-current-device`

---

#### 📋 Tareas de Implementación

| # | Tarea | Archivos | Tiempo | Estado |
|---|-------|----------|--------|--------|
| 1 | Añadir campo `is_current_device` a UserDeviceDTO | `device_dto.py` | 5 min | ✅ Completado |
| 2 | Actualizar ListUserDevicesRequestDTO con contexto HTTP | `device_dto.py` | 5 min | ✅ Completado |
| 3 | Modificar ListUserDevicesUseCase para calcular dispositivo actual | `list_user_devices_use_case.py` | 15 min | ✅ Completado |
| 4 | Actualizar endpoint GET /users/me/devices para pasar contexto HTTP | `device_routes.py` | 10 min | ✅ Completado |
| 5 | **NUEVO:** Helper centralizado de validación HTTP (IP spoofing prevention) | `http_context_validator.py` | 2h | ✅ Completado |
| 6 | **NUEVO:** Refactorizar routes (eliminar código duplicado) | `*_routes.py` | 1h | ✅ Completado |
| 7 | Actualizar tests unitarios de ListUserDevicesUseCase | `test_list_user_devices_use_case.py` | 20 min | ✅ Completado |
| 8 | **NUEVO:** Tests de seguridad HTTP (36 tests) | `test_http_context_validator.py` | 1.5h | ✅ Completado |
| 9 | Actualizar tests de integración del endpoint | `test_device_routes.py` | 15 min | ✅ Completado |
| 10 | Actualizar documentación API | `docs/API.md` | 5 min | ✅ Completado |
| 11 | Actualizar Postman collection | `postman_collection.json` | 5 min | ✅ Completado |

**Total:** 11 tareas | ~6 horas | 9 archivos modificados + 2 nuevos creados

---

#### 🔍 Problemas Identificados

**1. UX - Dispositivo Actual no Marcado:**
- El endpoint `GET /api/v1/users/me/devices` no indicaba cuál es el dispositivo actual
- Frontend no podía resaltar visualmente el dispositivo en uso
- Sin advertencia al revocar el dispositivo actual

**2. CRÍTICO - Valores Sentinel sin Validación (OWASP A03):**
- `DeviceFingerprint.create()` fallaba con `ValueError` si recibía `user_agent="unknown"` o `ip_address=""`
- Causaba HTTP 500 en endpoint `/users/me/devices` si AsyncClient no enviaba headers
- **Impacto:** Endpoint inestable en testing/production con clientes sin headers

**3. CRÍTICO - IP Spoofing Vulnerability (OWASP A01):**
- Funciones `get_client_ip()` confiaban ciegamente en headers `X-Forwarded-For` sin validar proxy
- **Ataque:** Cliente malicioso podía falsificar su IP enviando header manipulado
- **Impacto:** Bypass de rate limiting, device fingerprinting incorrecto, sesiones compartidas
- Código duplicado en 3 archivos (90 líneas)

---

#### 💡 Solución Implementada

**1. Campo `is_current_device` (Bugfix UX):**
- ✅ Extracción de `user_agent` + `ip_address` del request en endpoint
- ✅ Creación de `DeviceFingerprint` y comparación de hashes
- ✅ Marcado de dispositivo actual con `is_current_device=True`

**2. Validación de Valores Sentinel (Security Fix):**
- ✅ `validate_ip_address()`: Rechaza "unknown", "", whitespace, "0.0.0.0", "127.0.0.1", formato inválido
- ✅ `validate_user_agent()`: Rechaza "unknown", "", whitespace, < 10 chars, > 500 chars
- ✅ Graceful degradation: Retorna `None` en lugar de lanzar excepciones
- ✅ Logs de debug/warning apropiados

**3. Prevención de IP Spoofing (Security Critical):**
- ✅ Helper centralizado `http_context_validator.py` (306 líneas)
- ✅ `get_trusted_client_ip()`: Valida proxy contra whitelist `TRUSTED_PROXIES`
- ✅ Solo confía en `X-Forwarded-For` si proxy es confiable
- ✅ Fallback a `request.client.host` si proxy no confiable
- ✅ Aplicación de `validate_ip_address()` al resultado
- ✅ Eliminación de código duplicado en 3 archivos (-90 líneas)

**Configuración de Producción:**
```bash
# .env (Render.com)
TRUSTED_PROXIES=10.0.0.1,10.0.0.2  # IPs de load balancers

# .env (Local)
TRUSTED_PROXIES=  # Vacío = NO confiar en headers
```

---

#### 📊 Resultados

**Tests:**
- ✅ +36 tests de seguridad HTTP (100% passing)
- ✅ Suite completa: 1,066/1,066 tests (99.9% passing)
- ✅ Tiempo: ~60 segundos con paralelización

**Seguridad OWASP:**
- ✅ **A01 (Access Control):** 9.7/10 → **10/10** (+0.3) - IP Spoofing Prevention
- ✅ **A03 (Injection):** 10/10 (mantenido) - Sentinel Validation
- ✅ **Score Global:** 9.2/10 → **9.4/10** (+0.2)

**Código:**
- ✅ 2 archivos nuevos: `http_context_validator.py` (306 líneas) + tests (674 líneas)
- ✅ 9 archivos modificados
- ✅ -90 líneas de código duplicado
- ✅ Centralización total de validación HTTP

---

#### 📝 Checklist de Completado

- [x] Helper centralizado de validación HTTP creado
- [x] Validación de valores sentinel implementada
- [x] Prevención de IP spoofing con whitelist de proxies
- [x] Código duplicado eliminado (3 archivos)
- [x] 36 tests de seguridad (100% passing)
- [x] Tests de integración actualizados
- [x] OWASP score mejorado (9.2 → 9.4)
- [x] Documentación actualizada (ROADMAP + CHANGELOG)

---

### v2.1.0 - Competition Module Evolution ⭐ PRIORIDAD MÁXIMA - 7 semanas

**Objetivo:** Sistema completo de gestión de torneos Ryder Cup: campos de golf, planificación, live scoring con validación dual y leaderboards en tiempo real.

**Estado:** 🔵 En Planificación (27 Ene - 17 Mar 2026)

**Timeline:** 7 semanas | **Esfuerzo:** 330h (~47h/semana) | **Tests:** 75+ | **Endpoints:** 30 | **Entidades:** 14

**Coordinación con Frontend:** Sync points semanales (viernes) - Ver sección "🔄 Handoffs con Frontend"

---

## 📅 Sprint Breakdown - Backend API v2.1.0

---

### 📌 Sprint 1: RBAC Foundation & Golf Courses (1.5 semanas)

**Fechas:** 27 Ene - 6 Feb 2026 | **Esfuerzo:** 60h | **Tests:** 15+
**Owner:** Backend Dev | **Sync Point:** 🔄 Viernes 31 Ene 2026 (entrega endpoints roles)

#### Endpoints a Implementar (10 total)

**1.1 RBAC Endpoints (4 endpoints - Prioridad P0):**

```
POST   /api/v1/admin/users/{user_id}/roles
DELETE /api/v1/admin/users/{user_id}/roles/{role_name}
GET    /api/v1/users/me/roles
GET    /api/v1/admin/users (con filtro ?role=ADMIN|CREATOR|PLAYER)
```

**DTOs/Schemas:**
```python
# Request
class AssignRoleRequest(BaseModel):
    role_name: Literal["ADMIN", "CREATOR", "PLAYER"]

# Response
class UserRoleResponse(BaseModel):
    id: UUID
    name: str  # "ADMIN" | "CREATOR" | "PLAYER"
    assigned_at: datetime

class UserWithRolesResponse(BaseModel):
    id: UUID
    email: EmailStr
    first_name: str
    last_name: str
    roles: list[UserRoleResponse]
```

**Validaciones Pydantic:**
- ✅ `role_name` debe ser enum válido (ADMIN, CREATOR, PLAYER)
- ✅ Solo ADMIN puede asignar/remover roles
- ✅ No permitir auto-asignación de ADMIN
- ✅ Mantener al menos 1 ADMIN en el sistema

**Tests requeridos:**
- ✅ Assign role to user (happy path)
- ✅ Remove role from user
- ✅ Prevent non-admin from assigning roles (403)
- ✅ Prevent self-assignment of ADMIN (422)

---

**1.2 Golf Courses Endpoints (6 endpoints - Prioridad P0):**

```
POST /api/v1/golf-courses/request          # Creator solicita campo
GET  /api/v1/golf-courses/{id}             # Detalle completo (tees + holes)
GET  /api/v1/golf-courses                  # Lista (filtro: ?approval_status=APPROVED)
GET  /api/v1/admin/golf-courses/pending    # Admin lista pendientes
PUT  /api/v1/admin/golf-courses/{id}/approve
PUT  /api/v1/admin/golf-courses/{id}/reject
```

**DTOs/Schemas:**
```python
class HoleDTO(BaseModel):
    hole_number: int = Field(ge=1, le=18)
    par: int = Field(ge=3, le=5)
    stroke_index: int = Field(ge=1, le=18)

class TeeDTO(BaseModel):
    identifier: str = Field(max_length=50)  # "Championship", "Medal", etc.
    category: str = Field(max_length=20)    # "Yellow", "White", "Red"
    slope_rating: int = Field(ge=55, le=155)
    course_rating: float = Field(ge=60.0, le=80.0)
    gender: Literal["MALE", "FEMALE", "UNISEX"]

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

class GolfCourseResponse(BaseModel):
    id: UUID
    name: str
    country_code: str
    course_type: str
    approval_status: Literal["PENDING_APPROVAL", "APPROVED", "REJECTED"]
    tees: list[TeeDTO]  # Nested
    holes: list[HoleDTO]  # Nested
    requested_by: UUID
    requested_at: datetime
    approved_by: UUID | None
    approved_at: datetime | None
```

**Validaciones Pydantic:**
- ✅ Exactamente 18 hoyos
- ✅ Stroke index 1-18 únicos
- ✅ Par total 66-76
- ✅ Mínimo 2 tees, máximo 6
- ✅ Solo CREATOR puede solicitar
- ✅ Solo ADMIN puede aprobar/rechazar

**Tests requeridos:**
- ✅ Request golf course (CREATOR)
- ✅ Approve/reject golf course (ADMIN)
- ✅ Validation: duplicate stroke index (422)
- ✅ Validation: par out of range (422)
- ✅ Get golf course detail with nested tees/holes

---

### 📌 Sprint 2: Competition Scheduling (1.5 semanas)

**Fechas:** 7 Feb - 17 Feb 2026 | **Esfuerzo:** 70h | **Tests:** 18+
**Owner:** Backend Dev | **Sync Point:** 🔄 Viernes 14 Feb 2026 (entrega endpoints scheduling)

#### Endpoints a Implementar (10 total)

**2.1 Rounds Endpoints (4 endpoints - Prioridad P0):**

```
POST   /api/v1/competitions/{comp_id}/rounds
PUT    /api/v1/rounds/{round_id}
DELETE /api/v1/rounds/{round_id}
GET    /api/v1/competitions/{comp_id}/schedule  # Lista rounds + matches nested
```

**DTOs/Schemas:**
```python
class CreateRoundRequest(BaseModel):
    golf_course_id: UUID
    date: date
    session_type: Literal["MORNING", "AFTERNOON", "FULL_DAY"]

class RoundResponse(BaseModel):
    id: UUID
    golf_course: GolfCourseSummary  # Nested
    date: date
    session_type: str
    matches: list[MatchSummary]  # Nested
```

---

**2.2 Matches Endpoints (6 endpoints - Prioridad P0):**

```
POST   /api/v1/rounds/{round_id}/matches
GET    /api/v1/matches/{match_id}              # Detalle completo match
PUT    /api/v1/matches/{match_id}/players      # Asignar/reasignar jugadores
PUT    /api/v1/matches/{match_id}/status       # Manual IN_PROGRESS/COMPLETED
POST   /api/v1/matches/{match_id}/walkover     # Declarar walkover
DELETE /api/v1/matches/{match_id}
```

**DTOs/Schemas:**
```python
class CreateMatchRequest(BaseModel):
    format: Literal["FOURBALL", "FOURSOMES", "SINGLES", "GREENSOME"]
    team_a_player_1_id: UUID
    team_a_player_1_tee_id: UUID
    team_a_player_2_id: UUID | None  # Opcional para SINGLES
    team_a_player_2_tee_id: UUID | None
    team_b_player_1_id: UUID
    team_b_player_1_tee_id: UUID
    team_b_player_2_id: UUID | None
    team_b_player_2_tee_id: UUID | None

    @field_validator('team_a_player_2_id')
    def validate_singles_format(cls, v, info):
        if info.data.get('format') == 'SINGLES' and v is not None:
            raise ValueError("SINGLES format requires only 1 player per team")
        if info.data.get('format') != 'SINGLES' and v is None:
            raise ValueError(f"{info.data.get('format')} requires 2 players per team")
        return v

class MatchResponse(BaseModel):
    id: UUID
    format: str
    status: Literal["SCHEDULED", "IN_PROGRESS", "COMPLETED"]
    team_a_player_1: PlayerSummary
    team_a_player_1_playing_handicap: int  # ⚡ AUTO-CALCULADO
    team_a_player_2: PlayerSummary | None
    team_a_player_2_playing_handicap: int | None
    team_b_player_1: PlayerSummary
    team_b_player_1_playing_handicap: int
    team_b_player_2: PlayerSummary | None
    team_b_player_2_playing_handicap: int | None

class UpdateMatchStatusRequest(BaseModel):
    status: Literal["IN_PROGRESS", "COMPLETED"]

class DeclareWalkoverRequest(BaseModel):
    winning_team: Literal["TEAM_A", "TEAM_B"]
```

**Lógica de Negocio (Domain Layer):**
```python
# domain/services/handicap_calculator.py
class PlayingHandicapCalculator:
    """
    Calcula playing handicap según USGA WHS:
    PH = (Handicap Index × Slope Rating / 113) + (Course Rating - Par)
    """
    @staticmethod
    def calculate(
        handicap_index: float,
        tee: Tee,
        course_par: int
    ) -> int:
        slope_factor = tee.slope_rating / 113
        ph = (handicap_index * slope_factor) + (tee.course_rating - course_par)
        return round(ph)
```

**Validaciones Pydantic:**
- ✅ SINGLES: solo 1 jugador por equipo
- ✅ Otros formatos: exactamente 2 jugadores por equipo
- ✅ Tee ID debe existir en el golf course seleccionado
- ✅ Jugadores deben estar enrollados en la competición (status APPROVED)
- ✅ Solo CREATOR de la competición puede crear/modificar rounds/matches

**Tests requeridos:**
- ✅ Create round (happy path)
- ✅ Create match SINGLES (1 player per team)
- ✅ Create match FOURBALL (2 players per team)
- ✅ Validation: SINGLES with 2 players (422)
- ✅ Calculation: playing handicap is correct (WHS formula)
- ✅ Authorization: non-creator cannot schedule (403)
- ✅ Update match status manually
- ✅ Declare walkover (updates status + winner)

---

### 📌 Sprint 3: Invitations System (1 semana)

**Fechas:** 18 Feb - 24 Feb 2026 | **Esfuerzo:** 48h | **Tests:** 12+
**Owner:** Backend Dev | **Sync Point:** 🔄 Viernes 21 Feb 2026 (entrega endpoints invitations)

#### Endpoints a Implementar (5 total)

**3.1 Invitations Endpoints (5 endpoints - Prioridad P0):**

```
POST /api/v1/competitions/{comp_id}/invitations             # Invitar usuario registrado
POST /api/v1/competitions/{comp_id}/invitations/by-email    # Invitar por email
GET  /api/v1/invitations/me                                 # Invitaciones pendientes del usuario
POST /api/v1/invitations/{invitation_id}/respond            # Aceptar/declinar
GET  /api/v1/competitions/{comp_id}/invitations             # Lista invitaciones (creator view)
```

**DTOs/Schemas:**
```python
class InviteUserRequest(BaseModel):
    user_id: UUID

class InviteByEmailRequest(BaseModel):
    email: EmailStr
    # Backend busca user por email o crea invitación pendiente

class RespondInvitationRequest(BaseModel):
    response: Literal["ACCEPTED", "DECLINED"]

class InvitationResponse(BaseModel):
    id: UUID
    competition: CompetitionSummary
    invited_user_id: UUID
    invited_by: UUID
    status: Literal["PENDING", "ACCEPTED", "DECLINED", "EXPIRED"]
    invited_at: datetime
    responded_at: datetime | None
    expires_at: datetime  # 7 días desde invitación
```

**Lógica de Negocio:**
- ✅ Solo CREATOR puede invitar a su competición
- ✅ No permitir invitaciones duplicadas (mismo user + comp)
- ✅ Auto-expirar invitaciones después de 7 días
- ✅ Si user acepta → crear enrollment automáticamente con status APPROVED
- ✅ Enviar email de notificación (opcional v2.1.0, usar Mailgun templates existentes)

**Validaciones Pydantic:**
- ✅ Email válido (EmailStr)
- ✅ Response debe ser ACCEPTED o DECLINED
- ✅ Solo el invitado puede responder su propia invitación

**Tests requeridos:**
- ✅ Invite user by ID (happy path)
- ✅ Invite user by email (existing user)
- ✅ Accept invitation → creates enrollment with status APPROVED
- ✅ Decline invitation → status DECLINED
- ✅ Validation: duplicate invitation (409)
- ✅ Authorization: only invitee can respond (403)
- ✅ Auto-expiration after 7 days

---

### 📌 Sprint 4: Scoring System (2 semanas)

**Fechas:** 25 Feb - 10 Mar 2026 | **Esfuerzo:** 92h | **Tests:** 20+
**Owner:** Backend Dev | **Sync Point:** 🔄 Viernes 7 Mar 2026 (entrega scoring-view endpoint)

#### Endpoints a Implementar (4 total)

**4.1 Scoring Endpoints (4 endpoints - Prioridad P0):**

```
POST /api/v1/matches/{match_id}/scores/holes/{hole_number}  # Anotar score de un hoyo
GET  /api/v1/matches/{match_id}/scoring-view                # Vista unificada 3 tabs
POST /api/v1/matches/{match_id}/scorecard/submit            # Entregar tarjeta completa
GET  /api/v1/matches/{match_id}/scorecard                   # Ver tarjeta completa
```

**DTOs/Schemas:**
```python
class SubmitHoleScoreRequest(BaseModel):
    player_id: UUID  # Quien anota (puede ser jugador o marcador)
    score: int = Field(ge=1, le=15)  # Strokes en el hoyo

class HoleScoreDetail(BaseModel):
    hole_number: int
    par: int
    stroke_index: int
    player_score: int | None
    marker_score: int | None
    validation_status: Literal["match", "mismatch", "pending"]
    player_strokes_received: int  # Basado en playing handicap
    marker_strokes_received: int
    net_player: int | None  # gross - strokes_received
    net_marker: int | None

class MatchScoringView(BaseModel):
    """
    Vista unificada para los 3 tabs de frontend:
    - Tab 1 (Input): current_hole info
    - Tab 2 (Scorecard): hole-by-hole details
    - Tab 3 (Leaderboard): match standing
    """
    match_id: UUID
    current_hole: int  # Siguiente hoyo sin completar (1-18)
    hole_info: HoleScoreDetail  # Info del current_hole
    scorecard: list[HoleScoreDetail]  # Todos los 18 hoyos
    match_standing: MatchStanding
    can_submit: bool  # True si 18 hoyos validados (todos "match")

class MatchStanding(BaseModel):
    team_a_holes_won: int
    team_b_holes_won: int
    holes_halved: int
    status: str  # "Team A leads 2UP" | "All Square" | "Team B wins 3&2"
```

**Lógica de Negocio (Domain Layer):**
```python
# domain/services/scoring_validator.py
class ScoringValidator:
    @staticmethod
    def validate_dual_entry(player_score: int | None, marker_score: int | None) -> str:
        """Retorna: 'match' | 'mismatch' | 'pending'"""
        if player_score is None or marker_score is None:
            return "pending"
        return "match" if player_score == marker_score else "mismatch"

# domain/services/match_play_calculator.py
class MatchPlayCalculator:
    @staticmethod
    def calculate_standing(holes_data: list[HoleScoreDetail]) -> MatchStanding:
        """
        Calcula standing según reglas Match Play:
        - Comparar net score (gross - strokes received)
        - Menor net score gana el hoyo
        - Empate = halved
        """
        team_a_won = 0
        team_b_won = 0
        halved = 0

        for hole in holes_data:
            if hole.net_player is None or hole.net_marker is None:
                continue  # Hoyo no completado aún

            if hole.net_player < hole.net_marker:
                team_a_won += 1
            elif hole.net_marker < hole.net_player:
                team_b_won += 1
            else:
                halved += 1

        return MatchStanding(
            team_a_holes_won=team_a_won,
            team_b_holes_won=team_b_won,
            holes_halved=halved,
            status=_calculate_match_status(team_a_won, team_b_won, len(holes_data))
        )
```

**Validaciones Pydantic:**
- ✅ Score entre 1-15 (máximo razonable para golf)
- ✅ Hole number entre 1-18
- ✅ Solo jugadores asignados al match pueden anotar
- ✅ Submit scorecard solo si 18 hoyos validados (status "match")

**Tests requeridos:**
- ✅ Submit hole score (player perspective)
- ✅ Submit hole score (marker perspective)
- ✅ Validation: match (both scores equal)
- ✅ Validation: mismatch (scores differ)
- ✅ Calculation: match standing correct
- ✅ Submit scorecard: only when 18 holes validated
- ✅ Authorization: only assigned players can score (403)
- ✅ Get scoring view with current_hole tracking
- ✅ Navigation: frontend puede navegar libremente hoyos (← →)

---

### 📌 Sprint 5: Leaderboards & Optimization (1 semana)

**Fechas:** 11 Mar - 17 Mar 2026 | **Esfuerzo:** 60h | **Tests:** 10+
**Owner:** Backend Dev | **Sync Point:** 🔄 Viernes 14 Mar 2026 (entrega leaderboard público)

#### Endpoints a Implementar (2 total)

**5.1 Leaderboard Endpoints (2 endpoints - Prioridad P0):**

```
GET /api/v1/competitions/{comp_id}/leaderboard       # Leaderboard completo (público)
GET /api/v1/competitions/{comp_id}/leaderboard/live  # Solo matches activos (IN_PROGRESS)
```

**DTOs/Schemas:**
```python
class TeamStanding(BaseModel):
    team_name: str  # "Team A" | "Team B"
    points: float  # 1 point per win, 0.5 per halve
    matches_won: int
    matches_lost: int
    matches_halved: int

class MatchSummary(BaseModel):
    id: UUID
    format: str
    round_name: str  # "Round 1 - Morning"
    team_a_players: list[PlayerSummary]
    team_b_players: list[PlayerSummary]
    status: str  # "Team A wins 3&2" | "All Square thru 12" | "SCHEDULED"
    is_live: bool  # True si status == IN_PROGRESS

class LeaderboardResponse(BaseModel):
    competition_id: UUID
    team_a_standing: TeamStanding
    team_b_standing: TeamStanding
    matches: list[MatchSummary]
    has_live_matches: bool  # Para polling condicional en frontend
    last_updated: datetime
```

**Optimizaciones (Infrastructure Layer):**
```python
# infrastructure/repositories/leaderboard_repository.py
class LeaderboardRepository:
    async def get_leaderboard(self, comp_id: UUID) -> LeaderboardResponse:
        """
        Optimizaciones:
        - Query única con JOINs (evitar N+1)
        - Eager loading de relaciones (players, tees, scores)
        - Índices en DB: (competition_id, status), (match_id, hole_number)
        - Cache en Redis (TTL: 30s) si hay matches IN_PROGRESS
        """
        # Usar selectinload para relaciones
        query = (
            select(Match)
            .options(selectinload(Match.team_a_player_1))
            .options(selectinload(Match.team_a_player_2))
            .options(selectinload(Match.team_b_player_1))
            .options(selectinload(Match.team_b_player_2))
            .where(Match.competition_id == comp_id)
        )
        # ... calcular standings
```

**Validaciones Pydantic:**
- ✅ Endpoint público (no requiere auth)
- ✅ Competition debe existir y estar en status ACTIVE o IN_PROGRESS o COMPLETED
- ✅ Cache invalidado cuando se actualiza un score

**Tests requeridos:**
- ✅ Get leaderboard (public access, no auth required)
- ✅ Calculation: team points correct
- ✅ Filter: live matches only
- ✅ Performance: query < 200ms con 50+ matches
- ✅ Cache: Redis TTL 30s (si hay matches live)

---

**5.2 Performance Optimization (Prioridad P1):**

**Tasks:**
- ✅ Índices DB: (competition_id, status), (match_id, hole_number), (user_id, competition_id)
- ✅ Redis cache para leaderboard público (TTL: 30s)
- ✅ Eager loading con selectinload (evitar N+1 queries)
- ✅ API response time target: <200ms (p95)

---

## 📊 Resumen de Esfuerzo Backend v2.1.0

| Sprint | Duración | Horas | Endpoints | Tests |
|--------|----------|-------|-----------|-------|
| Sprint 1 | 1.5 sem | 60h | 10 (RBAC + Golf Courses) | 15+ |
| Sprint 2 | 1.5 sem | 70h | 10 (Rounds + Matches) | 18+ |
| Sprint 3 | 1 sem | 48h | 5 (Invitations) | 12+ |
| Sprint 4 | 2 sem | 92h | 4 (Scoring) | 20+ |
| Sprint 5 | 1 sem | 60h | 2 (Leaderboards) | 10+ |
| **TOTAL** | **7 sem** | **330h** | **30 endpoints** | **75+ tests** |

**Esfuerzo Promedio:** ~47 horas/semana (1.2 FTE)

---

## 🗄️ Nuevas Entidades Principales

**Domain Layer:**
- `Role`, `UserRole` - Sistema de roles formal (tabla roles + user_roles)
- `GolfCourse`, `Tee`, `Hole` - Gestión de campos (3 tablas)
- `Round`, `Match` - Planificación de jornadas (2 tablas)
- `Invitation` - Sistema de invitaciones (1 tabla)
- `HoleScore` - Anotación de scores (1 tabla)

**Enums clave:**
- `RoleName`: ADMIN, CREATOR, PLAYER
- `GolfCourseType`: STANDARD_18, PITCH_AND_PUTT, EXECUTIVE
- `TeeCategory`: CHAMPIONSHIP_MALE, AMATEUR_MALE, CHAMPIONSHIP_FEMALE, AMATEUR_FEMALE, BEGINNER, CUSTOM
- `ApprovalStatus`: PENDING_APPROVAL, APPROVED, REJECTED
- `MatchFormat`: FOURBALL, FOURSOMES, SINGLES, GREENSOME
- `MatchStatus`: SCHEDULED, IN_PROGRESS, COMPLETED, CANCELLED, WALKOVER_TEAM_A, WALKOVER_TEAM_B
- `InvitationStatus`: PENDING, ACCEPTED, DECLINED, EXPIRED
- `ScoreStatus`: DRAFT, SUBMITTED, VALIDATED, DISPUTED

**Total Entidades:** 14 | **Total Tablas DB:** 10 nuevas

---

## ✅ Acceptance Criteria Global (Backend v2.1.0)

### 1. Funcionalidad

- ✅ Todos los 30 endpoints implementados y documentados en Swagger
- ✅ RBAC funcional (ADMIN, CREATOR, PLAYER) con tabla roles
- ✅ Playing handicaps calculados automáticamente (USGA WHS formula)
- ✅ Validación dual de scores (player + marker independientes)
- ✅ Leaderboard público en tiempo real (sin auth)

### 2. Testing

- ✅ ≥85% test coverage (pytest)
- ✅ 0 tests failing en pipeline CI/CD
- ✅ 75+ tests nuevos (unit + integration)
- ✅ Integration tests con DB real (PostgreSQL testcontainer)

### 3. Performance

- ✅ API response time p95 <200ms
- ✅ Leaderboard query optimizada (eager loading + índices)
- ✅ Redis cache para endpoints públicos (TTL 30s)
- ✅ Índices DB en columnas críticas: (competition_id, status), (match_id, hole_number)

### 4. Security

- ✅ 0 vulnerabilities (Snyk, Safety)
- ✅ Authorization checks en todos los endpoints (admin/creator/player)
- ✅ Input validation con Pydantic (field validators)
- ✅ CORS configurado correctamente (solo frontend origin)

### 5. Documentation

- ✅ Swagger docs completos (descriptions, examples, request/response schemas)
- ✅ ADRs actualizados (ADR-022 a ADR-026)
- ✅ README con setup instructions
- ✅ Alembic migrations versionadas (10 nuevas migraciones)

---

## 🔄 Handoffs con Frontend

| Sprint | Backend Entrega | Frontend Consume | Sync Point |
|--------|----------------|------------------|------------|
| Sprint 1 | POST /admin/users/{id}/roles<br>GET /golf-courses | User Management page<br>Golf Course selector | Viernes 31 Ene |
| Sprint 2 | POST /competitions/{id}/rounds<br>POST /rounds/{id}/matches | Schedule drag-drop<br>Match creation wizard | Viernes 14 Feb |
| Sprint 3 | POST /invitations/{id}/respond | Invitation cards<br>Email notifications | Viernes 21 Feb |
| Sprint 4 | GET /matches/{id}/scoring-view | Scoring 3 tabs<br>Real-time validation | Viernes 7 Mar |
| Sprint 5 | GET /competitions/{id}/leaderboard | Public leaderboard<br>Polling (30s) | Viernes 14 Mar |

**Protocolo de Entrega:**
1. Backend despliega endpoints a dev environment (Render.com/Railway)
2. Backend actualiza Swagger docs en `/docs`
3. Backend notifica a Frontend vía Slack/Discord con ejemplos curl
4. Frontend integra endpoints (lunes siguiente)
5. Bug fixes prioritarios (si hay blockers críticos P0)

---

## 🛠️ Tech Stack Backend

```toml
# pyproject.toml (Poetry)
[tool.poetry.dependencies]
python = "^3.12"
fastapi = "^0.125.0"
sqlalchemy = "^2.0.25"
pydantic = "^2.6.1"
alembic = "^1.13.1"
asyncpg = "^0.29.0"         # PostgreSQL async driver
redis = "^5.0.1"            # Cache leaderboards
python-jose = "^3.3.0"      # JWT tokens
passlib = "^1.7.4"          # Password hashing
celery = "^5.3.6"           # Background tasks (emails)

[tool.poetry.group.dev.dependencies]
pytest = "^8.0.0"
pytest-asyncio = "^0.23.0"
pytest-cov = "^4.1.0"
httpx = "^0.26.0"           # Test client
faker = "^22.0.0"           # Test data
testcontainers = "^3.7.1"   # Docker containers en tests
```

---

## 📝 Notas Importantes

### 1. Clean Architecture:
- **Domain Layer:** Entities, Value Objects, Domain Services (PlayingHandicapCalculator, ScoringValidator, MatchPlayCalculator)
- **Application Layer:** Use Cases (un use case por endpoint principal)
- **Infrastructure Layer:** Repositories (SQLAlchemy), API (FastAPI)

### 2. Testing Strategy:
- **Unit tests:** Domain + Application (no DB, mocks)
- **Integration tests:** Infrastructure + API (con testcontainers PostgreSQL)
- **Target:** 75+ tests nuevos (vs 355 estimado inicial - reducción realista)

### 3. Database Migrations:
- Alembic para migraciones versionadas
- Naming convention: `{timestamp}_{sprint}_{feature}.py`
- Ejemplo: `20260127_sprint1_rbac_tables.py`

### 4. Error Handling:
- Custom exceptions por dominio: `DomainException`, `UnauthorizedException`, `ValidationException`
- HTTPException con status codes correctos (400, 403, 404, 422)
- Error responses consistentes: `{"detail": "...", "code": "..."}`

### 5. Swagger Documentation:
- Tags por módulo: "RBAC", "Golf Courses", "Scheduling", "Invitations", "Scoring", "Leaderboards"
- Examples en todos los schemas (request + response)
- Security schemes: Bearer token (JWT)

---

## 🎯 UX Highlights

**Scoring Interface:**
```
[← Hoyo 4]  HOYO 5  [Hoyo 6 →]
Par: 4 | 356m | SI: 3
Tu score: [5] | Marcador: [4]
✅ Coincide

Progreso: ✅✅✅❌⚪⚪⚪⚪⚪ | ⚪⚪⚪⚪⚪⚪⚪⚪⚪
          1 2 3 4 5 6 7 8 9   10...18

[🏁 Entregar] ← Solo si todos ✅
```

**Validación Dual:**
- Cada jugador valida SU tarjeta independientemente
- Bloqueo de entrega si hay discrepancias en tus scores
- Endpoint `GET /scoring-view` retorna `can_submit: bool`

**Invitaciones:**
- Búsqueda por email/nombre
- Token 256-bit, expira 7 días
- Email bilingües (ES/EN) usando templates Mailgun existentes

---

## 📈 Roadmap v2.1.x (Futuro)

**v2.1.1** (2 semanas) - Plantillas schedule, WebSocket, Puntos custom, Notificaciones push
**v2.1.2** (2 semanas) - Stats avanzadas, Export PDF, Google Maps, Weather API
**v2.1.3** (1 semana) - Cache Redis avanzado, Read replicas, CDN, Load testing

---

## 🔗 ADRs para v2.1.0

### ✅ ADRs Existentes (Ya Creados)

- **ADR-020** - Competition Module Domain Design (v1.x baseline - Nov 2025)
- **ADR-025** - Competition Module Evolution v2.1.0 (umbrella ADR - 9 Ene 2026)
  - Cubre: Roles, Tees, Playing Handicap pre-calculado, Dual Validation, Approval Workflow, Invitations
- **ADR-026** - Playing Handicap WHS Calculation (fórmula oficial + validaciones - 9 Ene 2026)

### 🆕 ADRs Nuevos (Creados Sprint 1)

- **ADR-031** - Match Play Scoring Calculation (standing calculation, hole winners - 27 Ene 2026)
- **ADR-032** - Golf Course Approval Workflow Details (visibility, notifications - 27 Ene 2026)
- **ADR-033** - Invitation Token Security and Auto-Enrollment (token 256-bit, expiration - 27 Ene 2026)

---

### v1.13.0 - Security Hardening ✅ **COMPLETADO** (9 Ene 2026)

**Objetivo:** Cerrar gaps de seguridad críticos | **Estado:** ✅ **COMPLETADO**

| Tarea | Estimación | OWASP | Prioridad | Estado |
|-------|-----------|-------|-----------|--------|
| ~~**Account Lockout**~~ | ~~3-4h~~ | A07 | 🟠 Alta | ✅ **COMPLETADO** (7 Ene) |
| ~~**CSRF Protection**~~ | ~~4-6h~~ | A01 | 🔴 CRÍTICA | ✅ **COMPLETADO** (8 Ene) |
| ~~**Password History**~~ | ~~3-4h~~ | A07 | 🟠 Alta | ✅ **COMPLETADO** (8 Ene) |
| ~~**Device Fingerprinting**~~ | ~~4-6h~~ | A01 | 🟠 Alta | ✅ **COMPLETADO** (9 Ene) |
| ~~**2FA/MFA (TOTP)**~~ | ~~12-16h~~ | A07 | 🔴 CRÍTICA | ❌ **REMOVIDO** (no necesario ahora) |

**Total:** ~14-20 horas (4/4 completados) | **OWASP Actual:** ✅ **9.2/10** (v1.13.0 FINALIZADO)

#### Cambios clave v1.13.0:
- **Account Lockout**: Bloqueo tras 10 intentos fallidos, auto-desbloqueo 30 min, endpoint manual, integración total (ver ADR-027)
- **CSRF Protection**: Triple capa (header, cookie, SameSite), middleware dedicado, tests exhaustivos (ver ADR-028)
- **Password History**: Previene reutilización últimas 5 contraseñas, bcrypt hashes en BD, GDPR compliant (ver ADR-029)
- **Device Fingerprinting**: SHA256 fingerprint, listado/revocación dispositivos, audit trail completo (ver ADR-030)
- **Security Tests**: 40+ tests nuevos (CSRF, XSS, SQLi, Auth Bypass, Rate Limiting)
- **CI/CD Pipeline**: Añadidos jobs de Security Tests y Trivy Container Scan (ver ADR-021)

**Cambios de Scope:**
- ❌ 2FA/MFA removido: No crítico para app actual (OWASP ya 10.0/10, no hay datos financieros sensibles)
- ✅ Focus en 4 features de alto impacto

#### 1. ~~Account Lockout Policy~~ ✅ **COMPLETADO (7 Ene 2026)**
- ✅ Bloqueo tras 10 intentos fallidos (HTTP 423 Locked)
- ✅ Desbloqueo automático (30 min)
- ✅ Endpoint manual unlock (POST /auth/unlock-account, Admin)
- ✅ Persistencia en BD (failed_login_attempts, locked_until)
- ✅ 5 tests integración pasando (100%)
- ✅ ADR-027 documentado
- ⚠️ Email notificación pendiente (opcional, no bloqueante)

**Implementación:** 3 commits (`a9fe089`, `e499add`, `14ecfd0`)
**Ver:** `docs/architecture/decisions/ADR-027-account-lockout-brute-force-protection.md`

#### 2. ~~CSRF Protection~~ ✅ **COMPLETADO (8 Ene 2026)**
- ✅ Triple capa: X-CSRF-Token header + double-submit cookie + SameSite="lax"
- ✅ Middleware CSRFMiddleware con timing-safe comparison
- ✅ Token 256-bit (secrets.token_urlsafe), 15 min duración
- ✅ Generación en login + refresh token
- ✅ Validación en POST/PUT/PATCH/DELETE (exime GET/HEAD/OPTIONS)
- ✅ Public endpoints exempt (/register, /login, /forgot-password, etc)
- ✅ 11 tests de seguridad pasando (10 passing + 1 skipped)
- ✅ ADR-028 documentado

#### 3. Password History ✅ COMPLETADO (8 Ene)
- ✅ Tabla `password_history` con migración Alembic
- ✅ Prevención de reutilización últimas 5 contraseñas
- ✅ Bcrypt hashes almacenados (255 chars)
- ✅ Cascade delete (GDPR compliance)
- ✅ Domain events (PasswordHistoryRecordedEvent)
- ✅ 25 unit tests (PasswordHistoryId + PasswordHistory)
- ✅ Validación en UpdateSecurity + ResetPassword
- ✅ ADR-029 documentado
- ⏳ Cleanup automático (diferido a v1.14.0)

#### 4. ~~Device Fingerprinting~~ ✅ **COMPLETADO (10 Ene 2026)**
- ✅ UserDevice entity (id, user_id, device_name, user_agent, ip, fingerprint_hash, is_active, last_used_at)
- ✅ DeviceFingerprint VO: SHA256 hash of User-Agent + IP
- ✅ **Auto-registro integrado** en LoginUserUseCase y RefreshAccessTokenUseCase (condicional)
- ✅ RegisterDeviceUseCase inyectado via DI (dependencies.py)
- ✅ 2 endpoints REST (GET /api/v1/users/me/devices list, DELETE revoke)
- ✅ 3 use cases (List, Register, Revoke)
- ✅ 99 tests (86 unit + 13 integration) - 100% passing
- ✅ Integración completa: 10 archivos modificados (LoginUserUseCase, RefreshAccessTokenUseCase, DTOs, tests)
- ✅ Partial unique index: (user_id, fingerprint_hash) WHERE is_active=TRUE
- ✅ Soft delete with audit trail
- ✅ Domain events: NewDeviceDetectedEvent, DeviceRevokedEvent
- ✅ Migration: 50ccf425ff32_add_user_devices_table.py
- ✅ ADR-030 documentado
- ⏳ Email notificación (diferido a v1.14.0)

---

### v1.14.0 - Compliance & Features - 2-3 semanas

**Objetivo:** GDPR compliance + UX improvements

| Tarea | Estimación | Categoría | Prioridad |
|-------|-----------|-----------|-----------|
| **GDPR Compliance** | 8-10h | Legal | 🟠 Alta |
| **Audit Logging** | 6-8h | Compliance | 🟡 Media |
| **Sistema Avatares** | 4-6h | UX | 🟡 Media |
| **Error Handling** | 3-4h | DX | 🟢 Baja |

**Total:** ~21-28 horas

#### 1. GDPR Compliance Tools
- Endpoint `GET /api/v1/users/me/export` (JSON completo)
- Endpoint `DELETE /api/v1/users/me` (soft delete)
- Anonimización de datos (GDPR Art. 17)
- Consent logging
- Data retention policies (90 días logs)

#### 2. Audit Logging Completo
- Modelo `AuditLog` en BD (user_id, action, resource, changes, timestamp, ip)
- Log de TODAS las acciones CRUD
- Retención 90 días
- Exportación CSV/JSON para compliance
- Dashboard básico (Sentry breadcrumbs)

#### 3. Sistema de Avatares
- Campo `avatar_url` en User
- Migración Alembic
- Endpoints: `PUT /api/v1/users/me/avatar`, `DELETE /api/v1/users/me/avatar`
- Storage: Cloudinary (5GB free) o AWS S3
- Validación: max 2MB, formatos (jpg/png/webp)
- Tests: 10+ tests

#### 4. Gestión de Errores Unificada
- Exception handlers centralizados
- Formato estándar:
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Competition name is required",
    "details": {"field": "name", "constraint": "required"}
  }
}
```
- ErrorCode enum (40+ códigos)
- Traducción i18n (ES/EN)

---

### v1.15.0 - AI & RAG Module - 2-3 semanas

**Objetivo:** Chatbot asistente de reglas de golf

**Stack:** LangChain + Pinecone + OpenAI GPT-4o-mini
**Costo:** $1-2/mes
**Knowledge Base:** R&A Official Rules of Golf

#### Features
- RAG chatbot con búsqueda semántica
- Solo disponible si `competition.status == IN_PROGRESS`
- Rate limiting dual-layer:
  - Global: 10 queries/día por usuario
  - Por competición: 3/día (participante), 6/día (creador)
  - Por minuto: 10 queries/min
- Caché Redis (TTL 7 días, 80% hit rate esperado)
- Pre-FAQs (20-30 hardcodeadas)
- Temperatura 0.3 (respuestas consistentes)

#### Arquitectura
```
src/modules/ai/
├── domain/           # Entities, VOs, Interfaces
├── application/      # Use Cases, DTOs, Ports
└── infrastructure/   # Pinecone, Redis, OpenAI, API
```

#### Ports
- `VectorRepositoryInterface` - Pinecone semantic search
- `CacheServiceInterface` - Redis caching
- `DailyQuotaServiceInterface` - Rate limiting dual-layer
- `LLMServiceInterface` - OpenAI GPT-4o-mini

#### Endpoints
- `POST /api/v1/competitions/{id}/ai/ask` - Query chatbot
- `GET /api/v1/competitions/{id}/ai/quota` - Remaining queries

#### Tests
- 60+ tests (unit + integration)
- Mocks para OpenAI (evitar costos)
- Tests de rate limiting

---

### v2.0.0 - Major Release (BREAKING CHANGES) - 4-6 meses

**Objetivo:** Escalabilidad + Features avanzadas

#### Breaking Changes
- ❌ Eliminar tokens del response body (solo httpOnly cookies)
- ❌ Eliminar compatibilidad con headers Authorization (deprecation period: 6 meses)
- ❌ API v1 deprecada → API v2

#### Security
- OAuth 2.0 / Social Login (Google, Apple, GitHub)
- WebAuthn (Hardware Security Keys)
- Advanced Threat Detection (ML-based anomaly detection)
- SOC 2 Compliance preparation

#### Features
- Analytics y estadísticas avanzadas
- Integración USGA, Golf Australia
- Push notifications (Firebase)
- Sistema de pagos (Stripe)
- Rankings globales
- Galería de fotos (AWS S3 + CloudFront)

#### Infrastructure
- Kubernetes deployment
- Blue-green deployments
- Auto-scaling (HPA)
- CDN para assets estáticos
- Database replication + read replicas
- Multi-region deployment

---

## 📅 Timeline Recomendado

```
2026 Q1  │ v1.13.0 - Security Hardening (Account Lockout + CSRF + Device Fingerprinting + Password History)
          │  🔹 Security Tests + Trivy (CI/CD)
2026 Q2  │ v1.14.0 - Compliance (GDPR, Audit Logging, Avatares)
2026 Q2  │ v1.15.0 - AI & RAG Module (Golf Rules Assistant)
2026 Q3  │ v2.1.0 - Competition Module Evolution (7 semanas) ⭐ PRIORIDAD MÁXIMA
2026 Q4+ │ v2.0.0 - Major Release (planificación + desarrollo)
```

---

## 🔗 Referencias

- **ADRs:** `docs/architecture/decisions/ADR-*.md`
- **CHANGELOG:** `CHANGELOG.md`
- **CLAUDE:** `CLAUDE.md` (contexto completo del proyecto)
- **Frontend ROADMAP:** `../RyderCupWeb/ROADMAP.md`
- **OWASP Top 10:** https://owasp.org/www-project-top-ten/
- **ASVS:** https://owasp.org/www-project-application-security-verification-standard/

**ADR relevantes:**
- ADR-027: Account Lockout (Brute Force Protection)
- ADR-028: CSRF Protection (Cross-Site Request Forgery)
- ADR-021: GitHub Actions CI/CD Pipeline (evolución security jobs)

**Cobertura de tests de seguridad:**
- 45+ tests de seguridad (CSRF, XSS, SQLi, Auth Bypass, Rate Limiting)
- 100% passing (CI/CD bloquea si falla alguno)

**Cobertura de middleware y cookies:**
- Middleware CSRF activo en todos los endpoints protegidos
- Cookie csrf_token (no httpOnly) + header X-CSRF-Token (double-submit)
- Renovación automática en login y refresh

---

**Próxima revisión:** ✅ v1.13.0 COMPLETADO (9 Ene 2026) - Iniciar v1.14.0 (Compliance & Features)
**Responsable:** Equipo Backend
