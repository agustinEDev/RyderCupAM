# 🗺️ Roadmap - RyderCupFriends Backend

> **Versión Actual:** 1.13.0 (COMPLETADO)
> **Última actualización:** 9 Ene 2026
> **Estado:** ✅ Producción (v1.13.0)
> **OWASP Score:** 9.2/10 (Account Lockout + CSRF + Password History + Device Fingerprinting)

---

## 📊 Estado Actual

### Métricas
- **Tests:** 1021 (100% passing, ~61s) - +99 Device Fingerprinting, +11 CSRF, +5 Account Lockout
- **Endpoints:** 39 REST API - +2 device endpoints (/me/devices GET/DELETE)
- **Módulos:** User, Competition, Enrollment, Countries
- **CI/CD:** GitHub Actions (10 jobs paralelos, ~3min) - Security Tests + Trivy
- **Deployment:** Render.com + Docker + PostgreSQL

### Completado (v1.0.0 - v1.12.1)

| Componente | Features |
|-----------|----------|
| **User Module** | Login, Register, Email Verification, Password Reset, Handicap (RFEG), Profile |
| **Competition Module** | CRUD, State Machine (6 estados), Enrollments, Countries (166 + 614 fronteras) |
| **Security (v1.8.0 - v1.13.0)** | Rate Limiting, httpOnly Cookies, Session Timeout (15min/7d), CORS, XSS Protection, Security Logging, Sentry, Dependency Audit (Safety + pip-audit + Snyk Code SAST), **Account Lockout (v1.13.0)**, **CSRF Protection (v1.13.0)**, **Password History (v1.13.0)**, **Device Fingerprinting (v1.13.0)** |
| **Testing** | 1021 tests (unit + integration + security), CI/CD automático |

### OWASP Top 10 Coverage

| Categoría | Score | Protecciones |
|-----------|-------|--------------|
| A01: Access Control | 9.7/10 | JWT, Refresh Tokens, Session Timeout, Authorization, **CSRF Protection**, **Device Fingerprinting** |
| A02: Crypto Failures | 10/10 | bcrypt (12 rounds), httpOnly Cookies, HSTS, Tokens seguros |
| A03: Injection | 10/10 | SQLAlchemy ORM, HTML Sanitization, Pydantic Validation |
| A04: Insecure Design | 9/10 | Rate Limiting (5/min login), Field Limits, Password Policy |
| A05: Misconfiguration | 9.5/10 | Security Headers, CORS Whitelist, Secrets Management |
| A06: Vulnerable Components | 9.0/10 | Triple Audit (Safety + pip-audit + Snyk), Auto-updates, 6 CVEs resueltos |
| A07: Auth Failures | 9.5/10 | Password Policy (ASVS V2.1), Session Timeout, Rate Limiting, **Account Lockout**, **Password History** |
| A08: Data Integrity | 7/10 | API Versioning |
| A09: Logging | 10/10 | Security Audit Trail, Correlation IDs, Sentry (APM + Profiling) |
| A10: SSRF | 8/10 | Input Validation |
| **Promedio** | **9.2/10** | Suma: 91.7 puntos / 10 categorías = 9.17 |

---

## 🎯 Roadmap Futuro

### v1.13.0 - Security Hardening (EN PROGRESO - Ene 2026) ⏳

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
