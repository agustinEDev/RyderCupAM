# 🗺️ Roadmap - RyderCupFriends Backend (API)

> **Versión:** 1.10.0
> **Última actualización:** 6 Dic 2025
> **Estado general:** ✅ Producción
> **Framework:** FastAPI + SQLAlchemy (Async)
> **Arquitectura:** Clean Architecture + DDD

---

## 📊 Resumen Ejecutivo

### ✅ Completado (v1.0.0 - v1.7.0)

| Componente | Estado | Descripción |
|-----------|--------|-------------|
| **Clean Architecture** | ✅ 100% | Bounded Contexts, Use Cases, Repositories |
| **SQLAlchemy ORM** | ✅ Implementado | Async, parametrización automática (anti-SQL injection) |
| **Autenticación** | ✅ JWT | Login, Register, Email Verification |
| **Competiciones** | ✅ Completo | CRUD, Estados, Transiciones, Países adyacentes |
| **Enrollments** | ✅ Completo | Solicitudes, Aprobaciones, Equipos, Custom Handicap |
| **Handicaps** | ✅ Completo | Manual + RFEG (solo usuarios españoles) |
| **Países** | ✅ Repository | 250+ países, códigos ISO, adyacencias geográficas |
| **HTTPS** | ✅ Habilitado | Render.com proporciona SSL automático |

### 📈 Métricas Clave

- **Endpoints:** 30+ rutas API
- **Tests:** 853 tests pasando (100%) en ~54s ⭐ ACTUALIZADO (19 Dic 2025)
- **Bounded Contexts:** 4 (User, Auth, Competition, Handicap)
- **Database:** PostgreSQL con migraciones Alembic
- **Deployment:** Render.com (contenedor Docker)
- **CI/CD:** GitHub Actions (7 jobs paralelos)

---

## 🔐 SEGURIDAD - Mejoras Prioritarias (v1.8.0)

> **Análisis OWASP Top 10 2021 completado:** 18 Dic 2025
> **Puntuación General Backend:** 10.0/10 ✅ (+0.5 Sentry Integration)
>
> **⚠️ IMPORTANTE:** Los detalles completos de implementación están en `docs/SECURITY_IMPLEMENTATION.md`
> **Este documento temporal debe ELIMINARSE cuando se completen todas las tareas.**
>
> **✨ PROGRESO v1.8.0:** 12/16 tareas completadas (Rate Limiting + Security Headers + Password Policy + httpOnly Cookies + Fix Tests + Session Timeout + CORS + Validaciones Pydantic + Security Logging + Correlation IDs + Sentry + Dependency Audit + Security Tests Suite)
> **⚠️ SIGUIENTE:** Testing exhaustivo e2e (opcional)

### Estado de Protecciones OWASP

| Categoría OWASP | Puntuación | Estado | Prioridad |
|-----------------|------------|--------|-----------|
| **A01: Broken Access Control** | 9/10 | ✅ Excelente (+3 Session Timeout) | 🟢 Baja |
| **A02: Cryptographic Failures** | 10/10 | ✅ Excelente (+2 Session Timeout) | 🟢 Baja |
| **A03: Injection** | 10/10 | ✅ Excelente (+0.5 Sanitización HTML) | 🟢 Baja |
| **A04: Insecure Design** | 9/10 | ✅ Excelente (+0.5 Límites de longitud) | 🟢 Baja |
| **A05: Security Misconfiguration** | 8.5/10 | ✅ Bien (+2 Security Headers, +0.3 CORS) | 🟢 Baja |
| **A06: Vulnerable Components** | 8.5/10 | ✅ Bien (+0.5 Dependency Audit) | 🟡 Media |
| **A07: Auth Failures** | 9.5/10 | ✅ Excelente (+1.5 Session Timeout + Rate Limiting) | 🟢 Baja |
| **A08: Data Integrity** | 7/10 | ⚠️ Parcial | 🟡 Media |
| **A09: Logging & Monitoring** | 10/10 | ✅ Excelente (+3 Security Logging, +0.5 Correlation IDs, +0.5 Sentry) | 🟢 Baja |
| **A10: SSRF** | 8/10 | ✅ Bien | 🟢 Baja |

### Estado Actual de Protecciones

| Protección | Estado | Prioridad | OWASP |
|------------|--------|-----------|-------|
| HTTPS | ✅ Habilitado | - | A02 |
| SQL Injection | ✅ Protegido (SQLAlchemy ORM) | - | A03 |
| Rate Limiting | ✅ Implementado (SlowAPI) | - | A04, A07 |
| Security Headers | ✅ Implementado (secure) | - | A02, A03, A04, A05, A07 |
| httpOnly Cookies | ✅ Implementado (dual support) | - | A01, A02 |
| CORS Configuration | ✅ Implementado (whitelist estricta) | - | A05, A01 |
| CSRF Protection | ⚠️ Parcial (SameSite=lax) | 🟡 Media | A01 |
| Input Validation | ✅ Implementado (sanitización HTML + validadores estrictos) | - | A03 |
| Security Logging | ✅ Implementado (8 eventos JSON) | - | A09 |
| Sentry Monitoring | ✅ Implementado (error tracking + APM + profiling) | - | A09 |
| Dependency Audit | ✅ Implementado (safety + pip-audit, 5/6 CVEs resueltos) ⭐ NUEVO | - | A06 |
| Password Policy | ✅ Implementado (OWASP ASVS V2.1) | - | A07 |
| 2FA/MFA | ❌ NO implementado | 🟠 Alta | A07 |
| Session Management | ✅ Implementado (refresh tokens, 15min/7días) ⭐ NUEVO | - | A01, A02, A07 |
| Audit Logging | ❌ NO implementado | 🟡 Media | A09 |
| API Versioning | ✅ Implementado | - | A08 |

### Vulnerabilidades Críticas Detectadas

1. ✅ **Tokens en response body** - ✨ RESUELTO con httpOnly cookies (A01, A02) - Fase transitoria
2. ✅ **Rate limiting implementado** - Protegido contra brute force (A04, A07) ✨ COMPLETADO
3. ✅ **Security headers implementados** - Protección completa (A02/A03/A04/A05/A07) ✨ COMPLETADO
4. ✅ **Validaciones Pydantic mejoradas** - Sanitización HTML + validadores estrictos ✨ COMPLETADO (A03)
5. ✅ **Security logging implementado** - Audit trail completo con 8 eventos JSON (A09) ✨ COMPLETADO
6. ❌ **No hay MFA/2FA** - Vulnerable a credential stuffing (A07)
7. ✅ **Password policy implementada** - OWASP ASVS V2.1 (12+ chars, complejidad completa) ✨ COMPLETADO
8. ✅ **Session timeout implementado** - Access 15 min + Refresh 7 días (A01/A02/A07) ✨ COMPLETADO

---

### Plan de Implementación (v1.8.0 - 3-4 semanas)

**Semana 1: Protecciones Inmediatas**
- [x] **1. Rate Limiting (SlowAPI)** - ✅ COMPLETADO (15 Dic 2025)
  - ✅ Login: 5/min, Register: 3/hour
  - ✅ RFEG API: 5/hour
  - ✅ Competiciones: 10/hour
  - ✅ Global: 100/minute
  - ✅ Tests de integración (5 tests)
  - ✅ Documentación en CLAUDE.md
  - **Puntuación mejorada:** 7.0/10 → 7.5/10 (+0.5)
- [x] **2. Security Headers (secure)** - ✅ COMPLETADO (15 Dic 2025)
  - ✅ HSTS (max-age=63072000; includeSubdomains)
  - ✅ X-Frame-Options (SAMEORIGIN)
  - ✅ X-Content-Type-Options (nosniff)
  - ✅ Referrer-Policy (no-referrer, strict-origin-when-cross-origin)
  - ✅ Cache-Control (no-store)
  - ✅ X-XSS-Protection (0 - desactivado, obsoleto)
  - ✅ Tests de integración (7 tests)
  - ✅ Documentación en CHANGELOG.md
  - **Puntuación mejorada:** 7.5/10 → 8.0/10 (+0.5)
- [x] **3. Password Policy Enforcement** - ✅ COMPLETADO (16 Dic 2025)
  - ✅ Mínimo 12 caracteres (ASVS V2.1.1)
  - ✅ Complejidad completa (mayúsculas + minúsculas + dígitos + símbolos)
  - ✅ Blacklist de contraseñas comunes (ASVS V2.1.7)
  - ✅ 681 tests actualizados (100% pasando)
  - ✅ Script de migración `fix_test_passwords.py`
  - ✅ Fix de paralelización (UUID único por BD de test)
  - **Puntuación mejorada:** 8.0/10 → 8.2/10 (+0.2)

**Semana 2: httpOnly Cookies + Session Management**
- [x] **4. httpOnly Cookies (JWT)** - ✅ COMPLETADO (16 Dic 2025)
  - ✅ Cookie Handler helper (`cookie_handler.py`)
  - ✅ Endpoint `/login` establece cookie httpOnly
  - ✅ Endpoint `/verify-email` establece cookie httpOnly
  - ✅ Endpoint `/logout` elimina cookie httpOnly
  - ✅ Middleware dual (cookies + headers) con prioridad a cookies
  - ✅ CORS con `allow_credentials=True` (ya existente)
  - ✅ Tests de integración (6/6 pasando - 100%)
  - ✅ Compatibilidad transitoria (dual support)
  - ✅ Documentación en CHANGELOG.md y CLAUDE.md
  - **Puntuación mejorada:** 8.2/10 → 8.5/10 (+0.3)
- [x] **4.1. Fix Tests httpOnly Cookies** - ✅ COMPLETADO (16 Dic 2025)
  - ✅ Arreglado `test_logout_deletes_httponly_cookie` (endpoint `/logout` con middleware dual)
  - ✅ Arreglado `test_verify_email_sets_httponly_cookie` (helper `get_user_by_email`)
  - ✅ 6/6 tests pasando en 5.90s
- [x] **5. Session Timeout with Refresh Tokens** ✅ COMPLETADO - 5h (100%) ⭐ FINAL
  - ✅ **Domain Layer:** RefreshToken entity + VOs (RefreshTokenId, TokenHash)
  - ✅ **Infrastructure:** Tabla refresh_tokens + Repository + Mapper
  - ✅ **Configuration:** Access 15min (reducido de 60min), Refresh 7 días
  - ✅ **JWT Handler:** Métodos create_refresh_token() y verify_refresh_token() + jti único
  - ✅ **Application Layer:** RefreshAccessTokenUseCase + DTOs
  - ✅ **Application Layer:** LoginUserUseCase modificado (genera refresh token)
  - ✅ **Application Layer:** LogoutUserUseCase modificado (revoca refresh tokens)
  - ✅ **API Layer:** Endpoint POST /api/v1/auth/refresh-token
  - ✅ **API Layer:** Endpoint /login actualizado (2 cookies httpOnly)
  - ✅ **API Layer:** Endpoint /logout actualizado (revoca + elimina cookies)
  - ✅ **Cookies:** Funciones set_refresh_token_cookie(), delete_refresh_token_cookie()
  - ✅ **Unit of Work:** Añadido refresh_tokens repository
  - ✅ **Documentation:** CHANGELOG.md, CLAUDE.md y ROADMAP.md actualizados
  - ✅ **Tests:** 722/722 pasando (100%) ⭐ SUITE COMPLETA (16 Dic 2025)
    - ✅ Sesión 1-2: Domain + Infrastructure + Application + API
    - ✅ Sesión 3: Correcciones (687/687 tests - 23 failures + 47 errors)
    - ✅ Sesión 4: Tests finales (722/722 tests - +35 nuevos) ⭐ COMPLETADO
      - ✅ 18 tests unitarios: RefreshToken entity
      - ✅ 10 tests unitarios: RefreshAccessTokenUseCase
      - ✅ 7 tests integración: POST /refresh-token endpoint
      - ✅ Bugs corregidos: find_by_token_hash (doble hash), InvalidUserIdError
      - ✅ Creado InMemoryRefreshTokenRepository (8 métodos)
  - **Resultado:** Feature 100% funcional con cobertura completa. OWASP Score: 8.5/10 → 9.0/10 (+0.5)
- [x] **6. CORS Configuration Mejorada** - ✅ COMPLETADO (17 Dic 2025)
  - ✅ Módulo `cors_config.py` con configuración centralizada
  - ✅ Función `get_cors_config()` para CORSMiddleware
  - ✅ Validación automática de orígenes (rechazo de wildcards, esquemas inválidos)
  - ✅ Separación clara desarrollo/producción
  - ✅ `allow_credentials=True` (requerido para cookies httpOnly)
  - ✅ Whitelist estricta de orígenes específicos
  - ✅ Tests de integración (11/11 tests pasando)
  - ✅ Suite completa: 733/733 tests pasando (100%)
  - ✅ Documentación en CHANGELOG.md y CLAUDE.md
  - **Puntuación mejorada:** 9.0/10 → 9.5/10 (+0.5)
- [x] Tests de autenticación - ✅ COMPLETADO (17 Dic 2025)
  - ✅ 789 tests pasando (100%)
  - ✅ Corregidos tests de integración con nombres válidos

**Semana 3: Validaciones + Logging**
- [x] **7. Validaciones Pydantic mejoradas** - ✅ COMPLETADO (17 Dic 2025) - 6h
  - ✅ Sanitización HTML en todos los inputs (sanitize_html, sanitize_all_fields)
  - ✅ Validación de email mejorada (EmailValidator con RFC 5322)
  - ✅ Límites de longitud estrictos (FieldLimits centralizados)
  - ✅ NameValidator (sin números, solo letras/espacios/guiones)
  - ✅ Prevención de ataques de homógrafos (normalize_unicode)
  - ✅ Tests unitarios (56/56 pasando)
  - ✅ DTOs actualizados con @field_validator y max_length
  - **Puntuación mejorada:** A03: 9.5/10 (+0.5 sanitización), A04: 8.5/10 (límites longitud)
- [x] **8. Security Logging avanzado** - ✅ COMPLETADO CON TESTS (17 Dic 2025) - 6h
  - ✅ Domain Events (8 eventos inmutables): LoginAttempt, Logout, RefreshTokenUsed, RefreshTokenRevoked, PasswordChanged, EmailChanged, AccessDenied, RateLimitExceeded
  - ✅ SecurityLogger service con archivo dedicado `logs/security_audit.log`
  - ✅ Formato JSON estructurado para análisis (jq, ELK, Splunk)
  - ✅ Rotación automática: 10MB x 5 backups
  - ✅ Severity levels (CRITICAL, HIGH, MEDIUM, LOW) con auto-ajuste
  - ✅ Contexto HTTP completo: IP (X-Forwarded-For, X-Real-IP), User-Agent
  - ✅ 4 use cases modificados: Login, Logout, RefreshToken, UpdateSecurity
  - ✅ DTOs actualizados con campos opcionales (backward compatibility)
  - ✅ Helper functions en routes: get_client_ip(), get_user_agent()
  - ✅ Tests: 816/816 pasando (100%) ⭐ +27 tests específicos
  - ✅ Tests unitarios: 14 (Domain Events) + 8 (SecurityLogger)
  - ✅ Tests integración: 5 (Audit Trail E2E)
  - ✅ 358+ eventos registrados durante test suite
  - ✅ Documentación completa: CHANGELOG.md, CLAUDE.md, ROADMAP.md
  - **Puntuación mejorada:** A09: 6/10 → 9/10 (+3.0) - Audit trail completo
- [x] **9. Structured Logging Enhancement** - ✅ COMPLETADO (17 Dic 2025) - 2h
  - ✅ Correlation IDs en todos los requests (UUID v4)
  - ✅ Header X-Correlation-ID en requests/responses
  - ✅ ContextVar para propagación async
  - ✅ Middleware posicionado como PRIMERO (antes de CORS)
  - ✅ Tests completos: 819/819 pasando (100%)
  - ✅ Preparación para OpenTelemetry
  - **Puntuación mejorada:** A09: 9.0/10 → 9.5/10 (+0.5)
- [ ] Frontend: migración a cookies - 4-6h (coordinado)

**Semana 4: Monitoring + Refinamiento**
- [x] **10. Sentry Backend Integration** - ✅ COMPLETADO (18 Dic 2025) - 3h
  - ✅ Error tracking automático con stack traces completos
  - ✅ Performance monitoring (APM) - sampling 10%
  - ✅ Profiling de código (CPU/memoria) - sampling 10%
  - ✅ Middleware de contexto de usuario (JWT)
  - ✅ Configuración por entorno (development, staging, production)
  - ✅ Filtros automáticos (health checks, OPTIONS, 404s)
  - ✅ 819/819 tests pasando (100%)
  - **Puntuación mejorada:** A09: 9.5/10 → 10/10 (+0.5)
- [x] **11. Dependency Audit** - ✅ COMPLETADO (19 Dic 2025) - 2h
  - ✅ Herramientas instaladas: safety 3.7.0 + pip-audit 2.10.0
  - ✅ 6 CVEs detectados, 5 resueltos (83.3% éxito)
  - ✅ Actualizaciones: fastapi 0.125.0, starlette 0.50.0, urllib3 2.6.0, filelock 3.20.1
  - ✅ 819/819 tests pasando (100%)
  - **Puntuación mejorada:** A06: 8.0/10 → 8.5/10 (+0.5)
- [x] **12. Security Tests Suite** - ✅ COMPLETADO (19 Dic 2025)
  - ✅ 34 tests de seguridad (100% pasando)
  - ✅ Tests de rate limiting (7 tests)
  - ✅ Tests de SQL injection attempts (5 tests)
  - ✅ Tests de XSS attempts (13 tests)
  - ✅ Tests de authentication bypass (9 tests)
  - ✅ Cobertura OWASP: A01, A03, A04, A07
  - **Puntuación mejorada:** 853 tests totales (+34)
- [ ] Testing exhaustivo e2e - 4h
- [ ] Deploy y monitoreo - 2h

**Total estimado:** 45-60 horas (3-4 semanas)

**OWASP Categories Addressed:**
- ✅ A01: Broken Access Control (httpOnly cookies, session timeout)
- ✅ A02: Cryptographic Failures (httpOnly cookies, JWT refresh)
- ✅ A03: Injection (validaciones mejoradas, tests)
- ✅ A04: Insecure Design (rate limiting)
- ✅ A05: Security Misconfiguration (headers, CORS, password policy)
- ✅ A06: Vulnerable Components (dependency audit)
- ✅ A07: Authentication Failures (password policy, session timeout, rate limiting)
- ✅ A09: Logging & Monitoring (security logging, Sentry)

---

### Tareas Adicionales (v1.9.0 - Security + Features)

**Security (Prioridad Alta):**
- [ ] **13. Autenticación 2FA/MFA (TOTP)** - 12-16h (CRÍTICO)
  - Modelo `TwoFactorSecret` en BD
  - Endpoints para enable/disable/verify 2FA
  - Integración con pyotp
  - Backup codes
  - Tests exhaustivos
- [ ] **14. Refresh Token Mechanism** - 6-8h
  - Modelo `RefreshToken` en BD
  - Access token corto (15 min)
  - Refresh token largo (7 días)
  - Token rotation automática
  - Revocación de tokens
- [ ] **15. Device Fingerprinting** - 4-6h
  - Modelo `UserDevice` en BD
  - Registro de dispositivos
  - Email de notificación en nuevo dispositivo
  - Endpoint para listar/revocar dispositivos
- [ ] **16. Account Lockout Policy** - 3-4h (NUEVO)
  - Bloqueo después de 10 intentos fallidos
  - Desbloqueo automático después de 30 min
  - Email de notificación de bloqueo
- [ ] **17. Password History** - 3-4h (NUEVO)
  - No permitir reutilizar últimas 5 contraseñas
  - Hash de passwords históricos
  - Limpieza automática de histórico antiguo
- [ ] **18. API Rate Limiting Avanzado** - 4-5h (NUEVO)
  - Rate limiting por usuario (no solo IP)
  - Rate limiting por endpoint
  - Whitelist de IPs confiables
  - Redis para contador distribuido
- [ ] **19. CSRF Protection** - 4-6h (evaluar necesidad después de cookies)
  - CSRF tokens con fastapi-csrf-protect
  - Double-submit cookie pattern
  - Tests de CSRF attempts

**Monitoring & Compliance:**
- [ ] **20. Audit Logging Completo** - 6-8h (NUEVO)
  - Modelo `AuditLog` en BD
  - Log de TODAS las acciones de usuario
  - Retención de logs (90 días)
  - Exportación para compliance
  - Dashboard de auditoría
- [ ] **21. GDPR Compliance Tools** - 8-10h (NUEVO)
  - Endpoint para exportar datos de usuario
  - Endpoint para eliminar cuenta (soft delete)
  - Anonimización de datos
  - Logs de consentimiento
- [ ] **22. Security Metrics Dashboard** - 4-6h (NUEVO)
  - Métricas de login attempts
  - Métricas de rate limiting
  - Alertas de comportamiento sospechoso
  - Integración con Sentry

**Otras Mejoras:**
- [ ] SQL Injection audit - 1h (verificación)
- [ ] Penetration testing manual - 8-10h

---

### 📖 Documentación Detallada

Ver implementación completa en: **`docs/SECURITY_IMPLEMENTATION.md`**

Incluye:
- Código completo de cada tarea
- Ejemplos de configuración
- Tests recomendados
- Rate limits específicos por endpoint
- Plan de migración para httpOnly cookies

**🗑️ RECORDATORIO:** Eliminar `docs/SECURITY_IMPLEMENTATION.md` cuando se completen todas las tareas.

---

## 🤖 IA & RAG - Módulo de Asistente Virtual

### RAG Chatbot v1.0 - Asistente de Reglamento de Golf
**Estado:** 📋 **PLANIFICADO** (v1.11.0)
**Prioridad:** 🟢 Alta
**Estimación:** 2-3 semanas
**Costo estimado:** $1-2/mes

---

#### **Objetivo:**
Chatbot RAG integrado en FastAPI para responder preguntas sobre:
- Reglas oficiales de golf (R&A/USGA)
- Formatos Ryder Cup (match play, foursome, fourball)
- Sistema de hándicap (WHS) - solo conceptual, NO cálculos

**Nota:** El cálculo de hándicap es determinista (RFEG API / manual / custom), no usa RAG.

---

#### **Stack Tecnológico:**

| Componente | Tecnología | Costo/mes |
|------------|-----------|-----------|
| Backend | FastAPI (mismo servicio) | $0 |
| Vector DB | Pinecone Free (100K vectores) | $0 |
| Embeddings | OpenAI text-embedding-3-small | $0 |
| LLM | OpenAI GPT-4o-mini | $1-2 |
| Cache | Redis Cloud Free (30MB) | $0 |

**Total: $1-2/mes** (con límites diarios + caché 80%)

---

#### **Reglas de Negocio:**

**1. Disponibilidad:**
- Solo si `competition.status == IN_PROGRESS`
- Usuario debe estar inscrito (`APPROVED`) o ser creador

**2. Rate Limiting (3 niveles):**
- **Por minuto:** 10 queries/min (anti-spam)
- **Global por usuario:** 10 queries/día totales
- **Por competición:**
  - Participante: 3 queries/día
  - Creador: 6 queries/día

**Ejemplo:**
```
Juan (4 competiciones):
- 6 queries en A (creador) ✅
- 3 queries en B (participante) ✅
- 1 query en C (participante) ✅
- Intenta query en D → ❌ 429 (límite global 10 alcanzado)
```

**3. Respuestas HTTP:**
- `200 OK` - Respuesta exitosa
- `403 Forbidden` - Competición no IN_PROGRESS o usuario no inscrito
- `429 Too Many Requests` - Límite global o por competición excedido

---

#### **Arquitectura:**

```
src/modules/ai/
├── domain/           # Entities, VOs, Interfaces
├── application/      # Use Cases, DTOs, Ports
└── infrastructure/   # Pinecone, Redis, OpenAI, API routes
```

**Ports principales:**
- `VectorRepositoryInterface` - Búsqueda en knowledge base
- `CacheServiceInterface` - Caché de respuestas (7 días TTL)
- `DailyQuotaServiceInterface` - Rate limiting dual-layer
- `LLMServiceInterface` - Generación de respuestas

---

#### **Optimizaciones de Costo:**

1. **Caché Redis:** 80% de queries cacheadas → $0
2. **Pre-FAQs:** 20-30 preguntas hardcodeadas → $0
3. **Límites diarios:** Máximo $1/mes garantizado
4. **Temperatura baja (0.3):** Respuestas consistentes

**Proyección realista:**
- 10 competiciones × 20 participantes × 50% uso = 345 queries/día
- Con caché 80% → 69 queries/día a OpenAI
- **Costo real: ~$0.50/mes**

---

#### **Plan de Implementación (3 semanas):**

**Semana 1: Domain Layer**
- Entities, VOs, Repository interfaces
- Tests unitarios (20-30 tests)

**Semana 2: Application + Infrastructure**
- Use Cases con validaciones completas
- Ports + Adapters (Pinecone, Redis, OpenAI)
- `RedisDailyQuotaService` (dual-layer rate limiting)
- Tests (50-60 tests)

**Semana 3: API + Deploy**
- Endpoints FastAPI
- SlowAPI rate limiting
- Script ingestión de documentos (50 docs)
- Deploy a Render
- Tests integración (15-20 tests)

---

#### **Métricas de Éxito:**
- [ ] 95%+ queries correctas (validación manual 100 queries)
- [ ] Latencia < 2 seg promedio
- [ ] Cache hit rate > 80% después de 1 mes
- [ ] Costo < $5/mes primeros 3 meses
- [ ] 90%+ usuarios satisfechos (feedback thumbs up/down)

---

#### **Dependencias:**
```txt
langchain>=0.1.0
openai>=1.0.0
pinecone-client>=3.0.0
tiktoken>=0.5.0
redis>=4.5.0
```

**Variables de entorno:**
```bash
REDIS_URL=redis://...
PINECONE_API_KEY=xxx
PINECONE_INDEX_NAME=rydercup-golf-rules
OPENAI_API_KEY=sk-xxx
RAG_CACHE_TTL=604800  # 7 días
RAG_TEMPERATURE=0.3
```

---

#### **Futuras Mejoras (v1.12.0+):**
- Asistente de configuración de torneos
- Widget de chat en frontend
- Soporte multilenguaje (EN/ES/PT)
- Fine-tuning con conversaciones reales
- Migrar a servicio separado si > 10K queries/mes


## 🛠️ Desarrollo - Tareas Pendientes

### Módulo de Usuario

#### Sistema de Avatares
**Estado:** ⏳ Pendiente
**Prioridad:** 🟡 Media
**Estimación:** 4-6 horas

**Requiere:**
1. Campo `avatar_url` en modelo User
2. Migración Alembic
3. Endpoint `PUT /api/v1/users/avatar` (multipart/form-data)
4. Endpoint `DELETE /api/v1/users/avatar`
5. Storage service (S3, Cloudinary, o local)

---

#### Sistema de Recuperación de Contraseña (Password Reset)
**Estado:** 🚧 EN PROGRESO (55% completado - 26 Dic 2025)
**Prioridad:** 🟠 Alta
**Estimación Total:** 12-14 horas | **Invertido:** ~7 horas | **Restante:** ~5-7 horas

**📋 Progreso por Capas:**

**✅ COMPLETADO (6/11 fases):**
1. ✅ **Domain Layer** - Password Reset Events & User Entity methods
   - `PasswordResetRequestedEvent` + `PasswordResetCompletedEvent`
   - `User.generate_password_reset_token()` - Token seguro 24h
   - `User.can_reset_password()` - Validación token + expiración
   - `User.reset_password()` - Cambio + invalidación + logout forzado

2. ✅ **Application Layer - DTOs** (6 DTOs creados)
   - `RequestPasswordResetRequestDTO` / `ResponseDTO`
   - `ResetPasswordRequestDTO` / `ResponseDTO`
   - `ValidateResetTokenRequestDTO` / `ResponseDTO` (opcional)

3. ✅ **Application Layer - Use Cases** (3 casos de uso)
   - `RequestPasswordResetUseCase` - Timing attack prevention
   - `ResetPasswordUseCase` - Token único + session invalidation
   - `ValidateResetTokenUseCase` - Pre-validación (mejor UX)

4. ✅ **Infrastructure - Database**
   - Migración Alembic: 2 campos (`password_reset_token`, `reset_token_expires_at`)
   - 2 índices: único en token, normal en expires_at
   - `UserRepository.find_by_password_reset_token()` (SQLAlchemy + InMemory)
   - Mapper actualizado con nuevos campos

5. ✅ **Infrastructure - Email Service**
   - `send_password_reset_email()` - Template HTML bilingüe (ES/EN)
   - `send_password_changed_notification()` - Template HTML bilingüe
   - Diseño profesional consistente con verify_email

6. ✅ **Ports/Interfaces**
   - `IEmailService` actualizado con 2 métodos async
   - `UserRepositoryInterface` con método abstracto

**⏳ PENDIENTE (5/11 fases - 45%):**

7. ⏳ **Infrastructure - Security Logging** (~30 min)
   - Añadir `SecurityLogger.log_password_reset_requested()`
   - Añadir `SecurityLogger.log_password_reset_completed()`
   - Eventos de seguridad en `security_events.py`

8. ⏳ **API Layer - REST Endpoints** (~1-2 horas)
   - `POST /api/v1/auth/forgot-password` - Solicitar reseteo
   - `POST /api/v1/auth/reset-password` - Completar reseteo
   - `GET /api/v1/auth/validate-reset-token/:token` - Validar token (opcional)
   - Rate limiting: 3 intentos/hora por email/IP
   - Dependency injection en `auth_routes.py`

9. ⏳ **Testing - Unit Tests** (~2-3 horas)
   - Tests de User Entity (3 métodos nuevos)
   - Tests de Use Cases (3 casos de uso)
   - Tests de Domain Events (2 eventos)
   - Estimado: ~40-50 tests

10. ⏳ **Testing - Integration Tests** (~1-2 horas)
    - Tests E2E de endpoints con BD + Email mock
    - Tests de rate limiting
    - Tests de timing attack prevention
    - Estimado: ~15-20 tests

11. ⏳ **Documentation** (~30 min)
    - Actualizar Swagger/OpenAPI con nuevos endpoints
    - Añadir entrada en CHANGELOG.md
    - Documentar contrato API en prompt original
    - Crear ADR-022 (Architecture Decision Record)

**🔐 Security Features Implementadas:**
- ✅ Token criptográficamente seguro (256 bits, `secrets.token_urlsafe`)
- ✅ Expiración automática (24 horas)
- ✅ Token de un solo uso (invalidación post-uso)
- ✅ Timing attack prevention (delay artificial si email no existe)
- ✅ Mensaje genérico anti-enumeración de usuarios
- ✅ Invalidación automática de TODAS las sesiones activas
- ✅ Templates de email bilingües con warnings de seguridad
- ✅ Política de contraseñas aplicada (OWASP ASVS V2.1)
- ⏳ Security logging completo (pendiente)
- ⏳ Rate limiting 3/hora por email (pendiente)

**📊 OWASP Coverage:**
- **A01: Broken Access Control** - ✅ Session invalidation, mensaje genérico
- **A02: Cryptographic Failures** - ✅ Token seguro, expiración, uso único
- **A03: Injection** - ✅ Email sanitization, Pydantic validation
- **A04: Insecure Design** - ⏳ Rate limiting (pendiente)
- **A07: Authentication Failures** - ✅ Password policy, token validation
- **A09: Security Logging** - ⏳ Audit trail (pendiente)

**📁 Archivos Creados/Modificados (21 archivos):**

**Domain Layer (3 archivos):**
- `password_reset_requested_event.py` (nuevo)
- `password_reset_completed_event.py` (nuevo)
- `user.py` (modificado: +3 métodos, +2 campos constructor)

**Application Layer (6 archivos):**
- `user_dto.py` (modificado: +6 DTOs)
- `email_service_interface.py` (modificado: +2 métodos abstractos)
- `request_password_reset_use_case.py` (nuevo)
- `reset_password_use_case.py` (nuevo)
- `validate_reset_token_use_case.py` (nuevo)

**Infrastructure Layer (7 archivos):**
- `3s4721zck3x7_add_password_reset_fields_to_users_table.py` (migración nueva)
- `mappers.py` (modificado: +2 columnas)
- `user_repository.py` (SQLAlchemy - modificado: +1 método)
- `in_memory_user_repository.py` (modificado: +1 método)
- `user_repository_interface.py` (modificado: +1 método abstracto)
- `email_service.py` (modificado: +2 métodos con templates HTML)

**Total líneas añadidas:** ~1,200 líneas de código + documentación

**🚀 Próximos Pasos (Nueva Sesión):**

**Pre-requisitos antes de continuar:**
1. Revisar código implementado (Domain, Application, Infrastructure)
2. Ejecutar suite de tests actual: `pytest tests/ -n auto`
3. Aplicar migración a BD de desarrollo:
   ```bash
   # Opción 1: Docker
   docker exec rydercupam-app-1 alembic upgrade head

   # Opción 2: Local
   alembic upgrade head
   ```
4. Verificar que todos los imports están correctos
5. Confirmar que no hay errores de sintaxis

**Implementación restante (orden sugerido):**
1. **FASE 7:** SecurityLogger (15-30 min)
   - Añadir 2 helper methods
   - Crear 2 security events en `security_events.py`

2. **FASE 8:** API Endpoints (1-2 horas)
   - Crear 3 endpoints en `auth_routes.py`
   - Configurar rate limiting específico
   - Dependency injection de Use Cases

3. **FASE 9-10:** Testing (3-5 horas)
   - Unit tests (Domain + Application)
   - Integration tests (API + BD + Email mock)

4. **FASE 11:** Documentation (30 min)
   - Swagger/OpenAPI
   - CHANGELOG.md
   - ADR-022

**Estimación para completar:** 5-7 horas adicionales

---

### Cross-Cutting Concerns

#### Gestión de Errores Unificada
**Estado:** ⏳ Pendiente
**Prioridad:** 🟡 Media
**Estimación:** 3-4 horas

**Objetivo:** Respuestas de error consistentes en toda la API

**Formato propuesto:**
```json
{
    "error": {
        "code": "VALIDATION_ERROR",
        "message": "Competition name is required",
        "details": {
            "field": "name",
            "constraint": "required"
        }
    }
}
```

---

## 🧪 Testing

### Estado Actual
- ✅ **681 tests pasando (100%)**
- ✅ Tiempo de ejecución: 44.95 segundos (con paralelización `-n auto`)
- ✅ Suite completa: unitarios, integración, end-to-end
- ✅ CI/CD automático con GitHub Actions
- ✅ Cobertura >90% en lógica de negocio
- ✅ Fix de paralelización (UUID único por BD test)

### Próximos Tests (v1.8.0 - Security)
1. Tests de rate limiting (verificar 429 después de límite)
2. Tests de httpOnly cookies (verificar flags httponly/secure)
3. Tests de validación de inputs (rechazar HTML, límites)
4. Tests de security headers (verificar presence)

---

## 📦 Infraestructura

### Completado
- ✅ Deploy en Render.com
- ✅ PostgreSQL database
- ✅ Docker containerization
- ✅ Migraciones Alembic
- ✅ HTTPS habilitado
- ✅ CI/CD con GitHub Actions (7 jobs paralelos)

### Futuras Mejoras
- Staging environment
- Database backups automáticos
- Monitoring (Sentry + métricas custom)

---

## 🚀 Roadmap de Versiones

### v1.8.0 (Próxima - Security Release)
**Estimación:** 3-4 semanas | **Total:** 45-60 horas

**Objetivo:** Securizar el backend contra ataques comunes (OWASP Top 10 2021)

**Tareas (12):**
1. ✅ Rate Limiting (SlowAPI) - 2-3h
2. ✅ Security Headers - 1-2h
3. ✅ Password Policy Enforcement - 2-3h
4. ✅ httpOnly Cookies (JWT) - 6-8h
5. ✅ Session Timeout + Refresh Tokens - 2-3h
6. ✅ CORS mejorado - 1h
7. ✅ Validaciones Pydantic mejoradas - 4-6h
8. ✅ Security Logging avanzado - 4-5h
9. ✅ Structured Logging (JSON) - 2-3h
10. ✅ Sentry Backend Integration - 3-4h
11. ✅ Dependency Audit - 2h
12. ✅ Security Tests Suite - 3-4h

**OWASP Categories Addressed (8/10):**
- ✅ A01: Broken Access Control
- ✅ A02: Cryptographic Failures
- ✅ A03: Injection
- ✅ A04: Insecure Design
- ✅ A05: Security Misconfiguration
- ✅ A06: Vulnerable Components
- ✅ A07: Authentication Failures
- ✅ A09: Logging & Monitoring

**Mejora esperada:** 7.0/10 → 8.5/10 📈

Ver plan detallado en sección [🔐 SEGURIDAD](#-seguridad---mejoras-prioritarias-v180)

---

### v1.9.0 (Security + Funcionalidad)
**Estimación:** 2-3 meses después de v1.8.0 | **Total:** 80-100 horas

**Security (Prioridad Alta):**
- 🔐 **2FA/MFA (TOTP)** - 12-16h (CRÍTICO)
- 🔐 Refresh Token Mechanism - 6-8h
- 🔐 Device Fingerprinting - 4-6h
- 🔐 Account Lockout Policy - 3-4h
- 🔐 Password History - 3-4h
- 🔐 API Rate Limiting Avanzado - 4-5h
- 🔐 CSRF Protection - 4-6h
- 🔐 Audit Logging Completo - 6-8h
- 🔐 GDPR Compliance Tools - 8-10h
- 🔐 Security Metrics Dashboard - 4-6h
- 🔐 Penetration Testing - 8-10h

**Features:**
- 👤 Sistema de avatares - 4-6h
- 📝 Gestión de errores unificada - 3-4h
- 🧪 Suite de tests ampliada - 6-8h

**OWASP Categories Addressed (10/10):**
- ✅ Todas las categorías cubiertas al 100%

**Mejora esperada:** 8.5/10 → 9.5/10 🚀

---

### v1.10.0 (Mantenimiento)
**Estimación:** 1 mes después de v1.9.0

- 🔧 Refactoring de código legacy
- 📚 Documentación API completa (OpenAPI)
- 🧹 Limpieza de código técnico
- 📊 Optimización de queries BD

---

### v1.11.0 (IA & RAG)
**Estimación:** 2-3 semanas | **Costo:** $1-2/mes

**Objetivo:** Chatbot RAG para asistencia de reglas de golf

Ver plan detallado en sección [🤖 IA & RAG](#-ia--rag---módulo-de-asistente-virtual)

---

### v2.0.0 (Mayor - Futuro)
**Estimación:** 4-6 meses | **Total:** 200+ horas

**BREAKING CHANGES (Migration from v1.8.0/v1.9.0):**
- [ ] **Eliminar token del response body (BREAKING)** - 4-6h
  - Eliminar campo `access_token` de `LoginResponseDTO`
  - Eliminar campo `access_token` de `VerifyEmailResponseDTO`
  - Solo httpOnly cookies (eliminar compatibilidad con headers)
  - Actualizar tests para solo usar cookies
  - **Requiere:** Frontend completamente migrado a cookies
  - **Deprecation period:** 6 meses desde v1.8.0

**Security:**
- 🔐 OAuth 2.0 / Social Login (Google, Apple)
- 🔐 Hardware Security Keys (WebAuthn)
- 🔐 Advanced Threat Detection (ML-based)
- 🔐 SOC 2 Compliance preparation
- 🔐 Security Champions program

**Features:**
- 📊 Analytics y estadísticas avanzadas
- 🌍 Integración con federaciones internacionales (USGA, Golf Australia)
- 📱 Push notifications con Firebase
- 🎮 Sistema de equipos mejorado con chat
- 💰 Sistema de pagos (Stripe)
- 🏆 Clasificaciones y rankings globales
- 📸 Galería de fotos de torneos

**Infrastructure:**
- 🚀 Kubernetes deployment
- 🔄 Blue-green deployments
- 📈 Auto-scaling
- 🌐 CDN para assets estáticos
- 🗄️ Database replication y read replicas

**Mejora esperada:** 9.5/10 → 10/10 🏆

---

## 🔗 Referencias

- [FastAPI Security Docs](https://fastapi.tiangolo.com/tutorial/security/)
- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [SQLAlchemy Security](https://docs.sqlalchemy.org/en/14/faq/security.html)
- [SlowAPI Documentation](https://slowapi.readthedocs.io/)
- [python-secure Documentation](https://secure.readthedocs.io/)
- Frontend ROADMAP: `../RyderCupWeb/ROADMAP.md`
- Frontend ADR-004: httpOnly Cookies Migration

---

**Última revisión:** 6 Dic 2025
**Próxima revisión:** Después de v1.8.0 (Security Release)
**Responsable:** Equipo de desarrollo backend
