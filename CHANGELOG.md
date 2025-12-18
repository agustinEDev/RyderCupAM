# Changelog

Todos los cambios notables en este proyecto serán documentados en este archivo.

El formato está basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.0.0/),
y este proyecto adhiere a [Semantic Versioning](https://semver.org/lang/es/).

## [Unreleased]

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
