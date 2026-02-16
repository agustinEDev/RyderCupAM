# Roadmap - RyderCupFriends Backend

> **Version:** 2.0.8 | **Tests:** 1,567 (1 skipped) | **Endpoints:** 66 | **OWASP:** 9.4/10
>
> **Last Updated:** Feb 15, 2026

---

## En Progreso

### Clean Architecture Refactoring (PR #63)

- **Rama:** `refactor/clean-architecture-violations`
- **Objetivo:** Resolver violaciones DDD/Clean Architecture detectadas post-Sprint 2
- **Resultado:** 12/15 violaciones resueltas (97% compliance)
  - Zero framework imports en domain layer
  - Entidades encapsuladas (Competition, Enrollment)
  - DTO mappers movidos a application layer
  - Competition routes dividido en 3 ficheros (CRUD, State, GolfCourse)
  - Domain services inyectados via DI
  - Excepciones centralizadas

---

## Próximo: Sprint 3 — Invitations (1 semana)

**Objetivo:** Sistema de invitaciones para competiciones

### Endpoints (5)

```http
POST /api/v1/competitions/{id}/invitations            # Invitar por user ID
POST /api/v1/competitions/{id}/invitations/by-email    # Invitar por email
GET  /api/v1/invitations/me                            # Mis invitaciones pendientes
POST /api/v1/invitations/{id}/respond                  # Aceptar/Rechazar
GET  /api/v1/competitions/{id}/invitations             # Vista creador
```

### Reglas clave

- Token 256-bit (`secrets.token_urlsafe(32)`), SHA256 hash en BD, expira 7 días
- Aceptar invitación → Enrollment status APPROVED (bypasses approval flow)
- Emails bilingües ES/EN via Mailgun
- Limpieza automática de tokens expirados (Celery, cada 6h)

---

## Planificado

### Sprint 4 — Scoring (2 semanas)

**Objetivo:** Live scoring hoyo a hoyo con validación dual

| Endpoint | Descripción |
|----------|-------------|
| `POST /matches/{id}/scores/holes/{n}` | Registrar score de un hoyo |
| `GET /matches/{id}/scoring-view` | Vista unificada (3 tabs: input, scorecard, standing) |
| `POST /matches/{id}/scorecard/submit` | Entregar tarjeta (requiere 18/18 validados) |
| `GET /matches/{id}/scorecard` | Ver tarjeta completa |

- **Validación dual:** Cada jugador registra SU score + marcador registra el suyo
- **Match Play:** Net score = gross - strokes_received, lower net wins hole
- **Bloqueo entrega:** No se puede entregar si hay discrepancias sin resolver

### Sprint 5 — Leaderboards (1 semana)

**Objetivo:** Leaderboards en tiempo real

| Endpoint | Descripción |
|----------|-------------|
| `GET /competitions/{id}/leaderboard` | Leaderboard completo (público) |
| `GET /competitions/{id}/leaderboard/live` | Solo partidos en curso |

- Redis cache (TTL 30s) para live matches
- Eager loading + DB indexes para < 200ms p95
- Respuesta: standings por equipo, matches won/lost/halved, last_updated

---

### v2.1.0 — Compliance & Features (2-3 semanas)

| Feature | Descripción |
|---------|-------------|
| GDPR Compliance | Export datos, soft delete, anonymización, retention 90 días |
| Audit Logging | Tabla `audit_logs`, CSV/JSON export, retention 90 días |
| Avatar System | Cloudinary/S3, max 2MB, jpg/png/webp |
| Unified Error Handling | ErrorCode enum, formato estándar, i18n ES/EN |

### v2.2.0 — AI & RAG Module (2-3 semanas)

- Chatbot de reglas de golf (R&A Official Rules)
- LangChain + Pinecone + OpenAI GPT-4o-mini (~$1-2/mes)
- Solo disponible si `competition.status == IN_PROGRESS`
- Rate limiting: 10/día global, 3/día player, 6/día creator
- Redis cache (TTL 7 días), pre-FAQs hardcoded

### v3.0.0 — Major Release (4-6 meses)

- OAuth 2.0 / Social Login (Google, Apple)
- WebAuthn (Hardware Security Keys)
- Push notifications (Firebase)
- Payment system (Stripe)
- Database replication + read replicas
- Multi-region deployment
- API v2 (deprecate v1)

---

## Timeline

```text
2025 Q4  │ v1.0.0 → v1.8.0   Auth, Security, Email, Handicap
2026 Q1  │ v1.11.0 → v1.13.1  Password Reset, CI/CD, Security Hardening
         │ v2.0.0 → v2.0.8    RBAC, Golf Courses, Scheduling, Support
         │ ⭐ Sprint 3         Invitations ← NEXT
2026 Q2  │ Sprint 4-5          Scoring + Leaderboards
         │ v2.1.0              Compliance (GDPR, Audit, Avatars)
         │ v2.2.0              AI & RAG Module
2026 Q3  │ v2.1.1 - v2.1.2    WebSocket, Stats, Export PDF
2026 Q4+ │ v3.0.0              Major Release
```

---

## Historial de Versiones

| Version | Fecha | Highlights |
|---------|-------|------------|
| **v2.0.8** | Feb 9, 2026 | Support Module (contact form → GitHub Issues) |
| **v2.0.7** | Feb 8, 2026 | Gender-based tee categories, hotfixes |
| **v2.0.1-v2.0.6** | Feb 1-6, 2026 | Sprint 2: Rounds, Matches, Teams (11 endpoints, 422 tests) |
| **v2.0.0** | Jan 29, 2026 | Sprint 1: RBAC Foundation, Golf Course Module (10 endpoints) |
| **v1.13.1** | Jan 18, 2026 | Device Detection, HTTP Security, IP spoofing prevention |
| **v1.13.0** | Jan 9, 2026 | Account Lockout, CSRF, Password History, Device Fingerprinting |
| **v1.12.x** | Jan 3-5, 2026 | Snyk integration (SCA + SAST), CVE fixes |
| **v1.11.0** | Dec 26, 2025 | Password Reset (256-bit token, bilingual emails) |
| **v1.10.0** | Nov 30, 2025 | CI/CD Pipeline (GitHub Actions, 7 parallel jobs) |
| **v1.8.0** | Nov 24, 2025 | Security (httpOnly, Rate Limiting, CORS, Headers, Sentry) |
| **v1.6.0** | Nov 18, 2025 | Competition Module (20 endpoints, state machine, enrollments) |
| **v1.0.0** | Nov 1, 2025 | Clean Architecture, User Module, JWT Auth, 420 tests |

**Detalle completo:** `CHANGELOG.md`

---

## OWASP Top 10

| Categoría | Score | Mitigación |
|-----------|-------|------------|
| A01: Broken Access Control | 10/10 | JWT, CSRF, RBAC, Device Fingerprinting |
| A02: Cryptographic Failures | 10/10 | bcrypt 12 rounds, httpOnly cookies, HSTS |
| A03: Injection | 10/10 | Pydantic, sanitización XSS, SQLAlchemy ORM |
| A04: Insecure Design | 9/10 | Business logic guards, STRIDE threat model |
| A05: Security Misconfiguration | 9.5/10 | CORS whitelist, security headers |
| A06: Vulnerable Components | 9/10 | Snyk SCA + SAST, Dependabot |
| A07: Authentication Failures | 9.5/10 | Account lockout, password history, session timeout |
| A08: Software Integrity | 7/10 | GPG signed commits, SBOM |
| A09: Security Logging | 10/10 | Audit trail, correlation IDs, Sentry |
| A10: SSRF | 8/10 | Input validation, no user-controlled URLs |
| **Total** | **9.4/10** | |

---

## Referencias

- **ADRs:** `docs/architecture/decisions/ADR-*.md` (37 total)
- **CHANGELOG:** `CHANGELOG.md`
- **CLAUDE:** `CLAUDE.md` (contexto completo del proyecto)
- **Database ERD:** `docs/DATABASE_ERD.md`
- **Security:** `docs/SECURITY_IMPLEMENTATION.md`
- **WHS:** https://www.usga.org/handicapping.html
- **OWASP:** https://owasp.org/www-project-top-ten/
