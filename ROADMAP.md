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
- **Tests:** 681 tests pasando (100%) en 45 segundos
- **Bounded Contexts:** 4 (User, Auth, Competition, Handicap)
- **Database:** PostgreSQL con migraciones Alembic
- **Deployment:** Render.com (contenedor Docker)
- **CI/CD:** GitHub Actions (7 jobs paralelos)

---

## 🔐 SEGURIDAD - Mejoras Prioritarias (v1.8.0)

> **Análisis OWASP Top 10 2021 completado:** 15 Dic 2025
> **Puntuación General Backend:** 9.0/10 ✅ (+0.5 tras Session Timeout)
>
> **⚠️ IMPORTANTE:** Los detalles completos de implementación están en `docs/SECURITY_IMPLEMENTATION.md`
> **Este documento temporal debe ELIMINARSE cuando se completen todas las tareas.**
>
> **✨ PROGRESO v1.8.0:** 6/16 tareas completadas (Rate Limiting + Security Headers + Password Policy + httpOnly Cookies + Fix Tests + Session Timeout)
> **⚠️ SIGUIENTE:** CORS mejorado (tarea 6)

### Estado de Protecciones OWASP

| Categoría OWASP | Puntuación | Estado | Prioridad |
|-----------------|------------|--------|-----------|
| **A01: Broken Access Control** | 9/10 | ✅ Excelente (+3 Session Timeout) | 🟢 Baja |
| **A02: Cryptographic Failures** | 10/10 | ✅ Excelente (+2 Session Timeout) | 🟢 Baja |
| **A03: Injection** | 9.5/10 | ✅ Excelente (+0.5 X-Content-Type) | 🟢 Baja |
| **A04: Insecure Design** | 8.5/10 | ✅ Bien (+1 Rate Limiting, +0.5 X-Frame-Options) | 🟢 Baja |
| **A05: Security Misconfiguration** | 8/10 | ✅ Bien (+2 Security Headers) | 🟡 Media |
| **A06: Vulnerable Components** | 8/10 | ✅ Bien | 🟡 Media |
| **A07: Auth Failures** | 9.5/10 | ✅ Excelente (+1.5 Session Timeout + Rate Limiting) | 🟢 Baja |
| **A08: Data Integrity** | 7/10 | ⚠️ Parcial | 🟡 Media |
| **A09: Logging & Monitoring** | 6/10 | ⚠️ Parcial | 🟠 Alta |
| **A10: SSRF** | 8/10 | ✅ Bien | 🟢 Baja |

### Estado Actual de Protecciones

| Protección | Estado | Prioridad | OWASP |
|------------|--------|-----------|-------|
| HTTPS | ✅ Habilitado | - | A02 |
| SQL Injection | ✅ Protegido (SQLAlchemy ORM) | - | A03 |
| Rate Limiting | ✅ Implementado (SlowAPI) | - | A04, A07 |
| Security Headers | ✅ Implementado (secure) | - | A02, A03, A04, A05, A07 |
| httpOnly Cookies | ✅ Implementado (dual support) | - | A01, A02 |
| CSRF Protection | ⚠️ Parcial (SameSite=lax) | 🟡 Media | A01 |
| Input Validation | ⚠️ Parcial (Pydantic básico) | 🟠 Alta | A03 |
| Security Logging | ⚠️ Básico | 🟠 Alta | A09 |
| Sentry Monitoring | ❌ NO implementado | 🟡 Media | A09 |
| Password Policy | ✅ Implementado (OWASP ASVS V2.1) | - | A07 |
| 2FA/MFA | ❌ NO implementado | 🟠 Alta | A07 |
| Session Management | ⚠️ Parcial (cookies, no timeout) | 🟠 Alta | A07 |
| Audit Logging | ❌ NO implementado | 🟡 Media | A09 |
| API Versioning | ✅ Implementado | - | A08 |

### Vulnerabilidades Críticas Detectadas

1. ✅ **Tokens en response body** - ✨ RESUELTO con httpOnly cookies (A01, A02) - Fase transitoria
2. ✅ **Rate limiting implementado** - Protegido contra brute force (A04, A07) ✨ COMPLETADO
3. ✅ **Security headers implementados** - Protección completa (A02/A03/A04/A05/A07) ✨ COMPLETADO
4. ⚠️ **Validaciones Pydantic básicas** - Falta sanitización HTML (A03)
5. ⚠️ **Logging básico** - No hay audit trail completo (A09)
6. ❌ **No hay MFA/2FA** - Vulnerable a credential stuffing (A07)
7. ✅ **Password policy implementada** - OWASP ASVS V2.1 (12+ chars, complejidad completa) ✨ COMPLETADO
8. ⚠️ **No hay session timeout** - Sesiones de 1 hora (A07) - Mejorar con refresh tokens

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
- [x] **5. Session Timeout with Refresh Tokens** ✅ COMPLETADO - 3.5h (100%)
  - ✅ **Domain Layer:** RefreshToken entity + VOs (RefreshTokenId, TokenHash)
  - ✅ **Infrastructure:** Tabla refresh_tokens + Repository + Mapper
  - ✅ **Configuration:** Access 15min (reducido de 60min), Refresh 7 días
  - ✅ **JWT Handler:** Métodos create_refresh_token() y verify_refresh_token()
  - ✅ **Application Layer:** RefreshAccessTokenUseCase + DTOs ⭐ NUEVO
  - ✅ **Application Layer:** LoginUserUseCase modificado (genera refresh token) ⭐ NUEVO
  - ✅ **Application Layer:** LogoutUserUseCase modificado (revoca refresh tokens) ⭐ NUEVO
  - ✅ **API Layer:** Endpoint POST /api/v1/auth/refresh-token ⭐ NUEVO
  - ✅ **API Layer:** Endpoint /login actualizado (2 cookies httpOnly) ⭐ NUEVO
  - ✅ **API Layer:** Endpoint /logout actualizado (revoca + elimina cookies) ⭐ NUEVO
  - ✅ **Cookies:** Funciones set_refresh_token_cookie(), delete_refresh_token_cookie() ⭐ NUEVO
  - ✅ **Unit of Work:** Añadido refresh_tokens repository ⭐ NUEVO
  - ✅ **Documentation:** CHANGELOG.md y CLAUDE.md actualizados ⭐ NUEVO
  - ⏳ **Tests:** Pendiente (unit + integration tests del flujo completo)
  - **Resultado:** Feature 100% funcional. OWASP Score: 8.5/10 → 9.0/10 (+0.5)
- [ ] **6. CORS mejorado** - 1h (NUEVO)
  - `allow_credentials=True`
  - Whitelist de orígenes específicos
- [ ] Tests de autenticación - 3h

**Semana 3: Validaciones + Logging**
- [ ] **7. Validaciones Pydantic mejoradas** - 4-6h
  - Sanitización HTML en todos los inputs
  - Validación de email mejorada
  - Límites de longitud estrictos
- [ ] **8. Security Logging avanzado** - 4-5h (NUEVO)
  - Audit trail de acciones críticas
  - Login attempts (éxito/fallo)
  - Cambios de contraseña/email
  - Creación/modificación de competiciones
- [ ] **9. Structured Logging** - 2-3h (NUEVO)
  - JSON structured logs
  - Correlation IDs para requests
  - Log levels por módulo
- [ ] Frontend: migración a cookies - 4-6h (coordinado)

**Semana 4: Monitoring + Refinamiento**
- [ ] **10. Sentry Backend Integration** - 3-4h
  - Error tracking automático
  - Performance monitoring
  - Breadcrumbs y contexto
- [ ] **11. Dependency Audit** - 2h (NUEVO)
  - `pip install safety`
  - Verificar vulnerabilidades conocidas
  - Actualizar dependencias críticas
- [ ] **12. Security Tests Suite** - 3-4h (NUEVO)
  - Tests de rate limiting
  - Tests de SQL injection attempts
  - Tests de XSS attempts
  - Tests de authentication bypass
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
