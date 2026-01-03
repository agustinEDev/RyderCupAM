# 🗺️ Roadmap - RyderCupFriends Backend

> **Versión:** 1.12.0
> **Última actualización:** 3 Ene 2026
> **Estado:** ✅ Producción
> **OWASP Score:** 9.2/10 (promedio de 10 categorías, redondeado)

---

## 📊 Estado Actual

### Métricas
- **Tests:** 905 (100% passing, ~60s)
- **Endpoints:** 36 REST API
- **Módulos:** User, Competition, Enrollment, Countries
- **CI/CD:** GitHub Actions (8 jobs paralelos, ~3min)
- **Deployment:** Render.com + Docker + PostgreSQL

### Completado (v1.0.0 - v1.12.0)

| Componente | Features |
|-----------|----------|
| **User Module** | Login, Register, Email Verification, Password Reset, Handicap (RFEG), Profile |
| **Competition Module** | CRUD, State Machine (6 estados), Enrollments, Countries (166 + 614 fronteras) |
| **Security (v1.8.0 + v1.12.0)** | Rate Limiting, httpOnly Cookies, Session Timeout (15min/7d), CORS, XSS Protection, Security Logging, Sentry, Dependency Audit (Safety + pip-audit + Snyk) |
| **Testing** | 905 tests (unit + integration + security), CI/CD automático |

### OWASP Top 10 Coverage

| Categoría | Score | Protecciones |
|-----------|-------|--------------|
| A01: Access Control | 9.5/10 | JWT, Refresh Tokens, Session Timeout, Authorization |
| A02: Crypto Failures | 10/10 | bcrypt (12 rounds), httpOnly Cookies, HSTS, Tokens seguros |
| A03: Injection | 10/10 | SQLAlchemy ORM, HTML Sanitization, Pydantic Validation |
| A04: Insecure Design | 9/10 | Rate Limiting (5/min login), Field Limits, Password Policy |
| A05: Misconfiguration | 9.5/10 | Security Headers, CORS Whitelist, Secrets Management |
| A06: Vulnerable Components | 9.0/10 | Triple Audit (Safety + pip-audit + Snyk), Auto-updates, 6 CVEs resueltos |
| A07: Auth Failures | 9.5/10 | Password Policy (ASVS V2.1), Account Protection, Rate Limiting |
| A08: Data Integrity | 7/10 | API Versioning |
| A09: Logging | 10/10 | Security Audit Trail, Correlation IDs, Sentry (APM + Profiling) |
| A10: SSRF | 8/10 | Input Validation |
| **Promedio** | **9.2/10** | Suma: 91.5 puntos / 10 categorías = 9.15 (redondeado a 9.2) |

---

## 🎯 Roadmap Futuro

### v1.13.0 - Security Hardening (CRÍTICO) - 3-4 semanas

**Objetivo:** Cerrar gaps de seguridad críticos

| Tarea | Estimación | OWASP | Prioridad |
|-------|-----------|-------|-----------|
| **2FA/MFA (TOTP)** | 12-16h | A07 | 🔴 CRÍTICA |
| **CSRF Protection** | 4-6h | A01 | 🔴 CRÍTICA |
| **Account Lockout** | 3-4h | A07 | 🟠 Alta |
| **Password History** | 3-4h | A07 | 🟠 Alta |
| **Device Fingerprinting** | 4-6h | A01 | 🟠 Alta |

**Total:** ~30-40 horas | **OWASP Esperado:** 10.0/10 → 10/10 perfecto

#### 1. 2FA/MFA (TOTP)
- Modelo `TwoFactorSecret` en BD
- Endpoints: enable/disable/verify 2FA
- Integración `pyotp` (TOTP RFC 6238)
- Backup codes (10 códigos de un solo uso)
- QR code generation
- Tests: 20+ tests (unit + integration)

#### 2. CSRF Protection
- Implementar `fastapi-csrf-protect`
- Double-submit cookie pattern
- CSRF tokens en forms
- Tests de CSRF bypass attempts

#### 3. Account Lockout Policy
- Bloqueo tras 10 intentos fallidos
- Desbloqueo automático (30 min)
- Email de notificación
- Endpoint manual unlock (admin)

#### 4. Password History
- Modelo `PasswordHistory` en BD
- No reutilizar últimas 5 contraseñas
- Hash bcrypt de histórico
- Limpieza automática (1 año)

#### 5. Device Fingerprinting
- Modelo `UserDevice` en BD
- User-Agent + IP tracking
- Email de notificación (nuevo dispositivo)
- Endpoint listar/revocar dispositivos

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
2026 Q1  │ v1.13.0 - Security Hardening (2FA, CSRF, Account Protection)
2026 Q2  │ v1.14.0 - Compliance (GDPR, Audit Logging, Avatares)
2026 Q2  │ v1.15.0 - AI & RAG Module (Golf Rules Assistant)
2026 Q3+ │ v2.0.0 - Major Release (planificación + desarrollo)
```

---

## 🔗 Referencias

- **Documentación detallada:** `docs/SECURITY_IMPLEMENTATION.md`
- **Frontend ROADMAP:** `../RyderCupWeb/ROADMAP.md`
- **OWASP Top 10:** https://owasp.org/www-project-top-ten/
- **ASVS:** https://owasp.org/www-project-application-security-verification-standard/

---

**Próxima revisión:** Después de v1.13.0
**Responsable:** Equipo Backend
