# Changelog

Todos los cambios notables en este proyecto serán documentados en este archivo.

El formato está basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.0.0/),
y este proyecto adhiere a [Semantic Versioning](https://semver.org/lang/es/).

## [Unreleased]

### Planned - v2.1.0 - Competition Module Evolution (En Planificación - 7 semanas)

**🏌️ Sistema Completo de Gestión de Torneos Ryder Cup**

#### Added (Planificado)
- Sistema de roles formal (Admin, Creator, Player) con tablas dedicadas
- Gestión completa de campos de golf con tees y 18 hoyos
- Sistema de aprobación de campos (Creator → PENDING_APPROVAL → Admin aprueba)
- Planificación de jornadas (Rounds) y partidos (Matches)
- Sistema de invitaciones con token seguro y auto-registro
- Cálculo automático de Playing Handicap (WHS)
- Live scoring hoyo a hoyo con navegación libre
- Validación dual independiente (jugador vs marcador)
- Leaderboards en tiempo real (match + global)

#### Nuevas Entidades (9 bloques)
1. **Roles & Permissions**: `Role`, `UserRole`
2. **Golf Courses**: `GolfCourse`, `Tee` (múltiples por campo), `Hole` (18 por campo)
3. **Schedule**: `Round`, `Match` (Fourball, Foursomes, Singles, Greensome)
4. **Invitations**: `Invitation` (búsqueda + email + token)
5. **Scoring**: `HoleScore` (gross, net, strokes_received)

#### Nuevos Endpoints (~35 REST API)
- Golf Courses: CRUD Admin + búsqueda por país (Creator)
- Course Approval: Aprobar/rechazar + notificaciones email
- Rounds: CRUD jornadas por competición
- Matches: CRUD partidos + asignación jugadores/tees
- Invitations: Buscar usuarios + invitar (registrados y email) + responder
- Scoring: Anotar scores hoyo a hoyo + validación dual + entregar tarjeta
- Leaderboards: Match individual + Global por equipos

#### Changed (Planificado)
- Competition Module: Evolución de gestión básica a sistema completo profesional
- Playing Handicap: Pre-calculado y almacenado (WHS fórmula oficial)
- Validación de scores: Sistema dual independiente por jugador

#### Tests Esperados
- +355 tests nuevos (905 → 1,260 tests, +39% growth)
- Cobertura completa: Domain, Application, Infrastructure, API

#### Documentación
- ADR-025: Competition Module Evolution v2.1.0
- ADR-026: Playing Handicap WHS Calculation
- DATABASE_ERD.md: Diagrama completo (15 tablas)
- ROADMAP.md: Planificación detallada 7 semanas

**Ver detalles completos:** `ROADMAP.md`, `docs/DATABASE_ERD.md`, `docs/architecture/decisions/ADR-025*.md`

---

## [1.13.0] - 2026-01-07

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
