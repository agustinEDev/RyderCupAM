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

**Estado:** 🔵 En Planificación (Ene 2026)

---

#### 📦 Bloques Funcionales

| # | Bloque | Semana | Tests | Descripción |
|---|--------|--------|-------|-------------|
| 1 | **Roles & Permisos** | 1-2 | ~40 | Sistema formal Admin/Creator/Player |
| 2 | **Golf Courses** | 1-2 | ~60 | CRUD campos con tees y hoyos (18) |
| 3 | **Course Approval** | 3 | ~30 | Creator crea campos → Admin aprueba |
| 4 | **Schedule** | 4 | ~50 | Rounds + Matches + asignación jugadores |
| 5 | **Invitations** | 4 | ~45 | Buscar/invitar usuarios + registro con token |
| 6 | **Playing Handicap** | 5 | ~25 | Cálculo WHS automático por tee |
| 7 | **Live Scoring** | 5 | ~40 | Anotación hoyo a hoyo con navegación libre |
| 8 | **Dual Validation** | 6-7 | ~35 | Validación independiente jugador vs marcador |
| 9 | **Leaderboards** | 6-7 | ~30 | Match + Global en tiempo real |

**Total:** 9 bloques | 7 semanas | ~355 tests nuevos | 35 endpoints | 14 entidades

---

#### 🗄️ Nuevas Entidades Principales

**Domain Layer:**
- `Role`, `UserRole` - Sistema de roles formal
- `GolfCourse`, `Tee`, `Hole` - Gestión de campos
- `Round`, `Match` - Planificación de jornadas
- `Invitation` - Sistema de invitaciones
- `HoleScore` - Anotación de scores
- `MatchResult`, `TeamStandings` - Leaderboards

**Enums clave:**
- `RoleName`: ADMIN, CREATOR, PLAYER
- `GolfCourseType`: STANDARD_18, PITCH_AND_PUTT, EXECUTIVE
- `TeeCategory`: CHAMPIONSHIP_MALE, AMATEUR_MALE, CHAMPIONSHIP_FEMALE, AMATEUR_FEMALE, BEGINNER, CUSTOM
- `ApprovalStatus`: PENDING_APPROVAL, APPROVED, REJECTED
- `MatchFormat`: FOURBALL, FOURSOMES, SINGLES, GREENSOME
- `MatchStatus`: SCHEDULED, IN_PROGRESS, COMPLETED, CANCELLED, WALKOVER_TEAM_A, WALKOVER_TEAM_B
- `InvitationStatus`: PENDING, ACCEPTED, REJECTED, EXPIRED
- `ScoreStatus`: DRAFT, SUBMITTED, VALIDATED, DISPUTED

---

#### ✅ Criterios de Aceptación Clave

**Admin:**
- CRUD campos (tees múltiples + 18 hoyos con plantillas)
- Aprobar/rechazar campos pendientes + email notificación
- Asignar roles a usuarios

**Creator:**
- Buscar campos por país + crear nuevos (PENDING_APPROVAL)
- Crear rounds/matches + asignar jugadores + seleccionar tees
- Invitar usuarios (registrados o por email con token)
- Cancelar matches o walkover
- Ver leaderboards

**Player:**
- Aceptar/rechazar invitaciones
- Registrarse con token (auto-inscripción)
- Anotar scores hoyo a hoyo (navegación libre ← →)
- Ver ✅/❌ coincidencia en tiempo real
- Entregar tarjeta solo si 18/18 ✅
- Ver scorecard (bruto/neto) + leaderboard

---

#### 🎯 UX Highlights

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

**Invitaciones:**
- Búsqueda por email/nombre
- Token 256-bit, expira 7 días
- Email bilingües (ES/EN)

---

#### 📈 Roadmap v2.1.x (Futuro)

**v2.1.1** - Plantillas schedule, WebSocket, Puntos custom, Notificaciones push
**v2.1.2** - Stats avanzadas, Export PDF, Google Maps, Weather API
**v2.1.3** - Cache Redis, Read replicas, CDN, Load testing

---

#### 🔗 ADRs a Crear

- `ADR-022` - Competition Module Evolution (visión general)
- `ADR-023` - Golf Course Approval Workflow
- `ADR-024` - Playing Handicap WHS Calculation
- `ADR-025` - Dual Validation Scoring System
- `ADR-026` - Invitation System Design

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

### v2.1.0 - Competition Module Evolution ⭐ PRIORIDAD MÁXIMA - 7 semanas

**Objetivo:** Sistema completo de gestión de torneos Ryder Cup: campos de golf, planificación, live scoring con validación dual y leaderboards en tiempo real.

**Estado:** 🔵 En Planificación (Ene 2026) | **Prioridad:** ⭐ MÁXIMA

**📋 Ver documentación completa:** `docs/DATABASE_ERD.md`, `docs/architecture/decisions/ADR-025*.md`

#### Bloques Funcionales (9 bloques, 7 semanas)

| # | Bloque | Semana | Tests | Descripción |
|---|--------|--------|-------|-------------|
| 1 | Roles & Permisos | 1-2 | ~40 | Sistema formal Admin/Creator/Player |
| 2 | Golf Courses | 1-2 | ~60 | CRUD campos con tees y hoyos (18) |
| 3 | Course Approval | 3 | ~30 | Creator crea → Admin aprueba |
| 4 | Schedule | 4 | ~50 | Rounds + Matches + asignación |
| 5 | Invitations | 4 | ~45 | Buscar/invitar + auto-registro token |
| 6 | Playing Handicap | 5 | ~25 | Cálculo WHS automático |
| 7 | Live Scoring | 5 | ~40 | Hoyo a hoyo + navegación libre |
| 8 | Dual Validation | 6-7 | ~35 | Validación independiente |
| 9 | Leaderboards | 6-7 | ~30 | Match + Global real-time |

**Total:** ~355 tests | 35 endpoints | 14 entidades

#### ADRs Pendientes
- ADR-022 a ADR-026 (Competition Evolution, Approval, WHS, Scoring, Invitations)

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
