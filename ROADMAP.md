# Roadmap - RyderCupFriends Backend

> **Versión:** 2.0.12 | **Tests:** 1,873 unit + 252 integration (1 skipped) | **Endpoints:** 80 | **OWASP:** 9.4/10
>
> **Last Updated:** Feb 24, 2026

---

## Completado: Sprint 4 — Live Scoring + Leaderboard

### Scoring + Leaderboard ✅ (8 bloques)

```http
GET  /api/v1/competitions/matches/{id}/scoring-view         # Vista unificada de scoring
POST /api/v1/competitions/matches/{id}/scores/holes/{n}     # Registrar score hoyo a hoyo
POST /api/v1/competitions/matches/{id}/scorecard/submit     # Entregar tarjeta
GET  /api/v1/competitions/{id}/leaderboard                  # Leaderboard completo
PUT  /api/v1/competitions/matches/{id}/concede               # Conceder partido
```

- **Validación dual**: own_score (jugador) + marker_score (marcador) → PENDING/MATCH/MISMATCH
- **Pre-creación 18 HoleScores vacíos** al iniciar match (START)
- **Marker assignments**: recíproco (Singles), cruzado (Fourball), por equipo (Foursomes)
- **Foursomes**: cualquier jugador del equipo puede registrar scores (último gana)
- **Match Play standing**: N up con M remaining, early termination (is_decided)
- **Concesión**: jugadores conceden su propio equipo, creator puede conceder cualquier equipo
- **Scorecard submit**: requiere todos los hoyos en MATCH, auto-completa match/round
- **Scorecard locking**: tras entregar tarjeta, own_score se ignora silenciosamente; tras entregar tarjeta del marcado, marker_score se ignora
- **User search autocomplete**: `GET /users/search-autocomplete` — búsqueda parcial por nombre (max 10 resultados)
- **Leaderboard**: suma Ryder Cup points por equipo, resuelve nombres con first_name + last_name
- **ScoringService** (dominio puro): marker assignments, hole winner, standing, decided result, ryder cup points
- **HoleScore entity**: own_score, marker_score, own_submitted, marker_submitted, validation_status, net_score
- **MatchStatus CONCEDED**: nuevo estado terminal para concesión de partidos
- 222 unit tests nuevos + 16 integration tests

---

## Completado: Sprint 3 — Google OAuth + Invitations

### Bloque 1: Google OAuth (Social Login) ✅ v2.0.9 → v2.0.11

```http
POST /api/v1/auth/google                              # Login/registro con Google
POST /api/v1/auth/google/link                          # Vincular cuenta Google a usuario existente
DELETE /api/v1/auth/google/unlink                      # Desvincular cuenta Google
```

- OAuth 2.0 Authorization Code Flow con PKCE
- Tabla `user_oauth_accounts` (user_id, provider, provider_user_id, email)
- `auth_providers` + `has_password` en UserResponseDTO (v2.0.10)
- Hotfix: naive datetime en UserOAuthAccount (v2.0.11)

### Bloque 2: Invitations + Bilingual Emails ✅ v2.0.12

```http
POST /api/v1/competitions/{id}/invitations            # Invitar por user ID
POST /api/v1/competitions/{id}/invitations/by-email    # Invitar por email
GET  /api/v1/invitations/me                            # Mis invitaciones pendientes
POST /api/v1/invitations/{id}/respond                  # Aceptar/Rechazar
GET  /api/v1/competitions/{id}/invitations             # Vista creador
```

- Token 256-bit, SHA256 hash en BD, expira 7 días
- Aceptar invitación → Enrollment status APPROVED (bypasses approval flow)
- Rate limiting: max_players invitaciones por hora por competición
- **Emails bilingües ES/EN via Mailgun** (ISP: `IInvitationEmailService` port en Competition module)
- Email no bloquea creación de invitación (fire-and-forget con try/except)
- HTML escaping en templates (`html.escape()` para body, `_sanitize_name()` para headers)
- RFC 5322 display-name formatting para recipients
- Domain Events: `InvitationCreatedEvent`, `InvitationAcceptedEvent`, `InvitationDeclinedEvent`
- 194 unit tests nuevos, 4 rondas de code review

---

## Planificado

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

- Apple Sign In (requiere Apple Developer Program)
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
         │ v2.0.9 → v2.0.12   Sprint 3: Google OAuth + Invitations + Emails ✅
2026 Q1  │ Sprint 4             Live Scoring + Leaderboard (5 endpoints, 238 tests) ✅
2026 Q2  │ v2.1.0              Compliance (GDPR, Audit, Avatars)
         │ v2.2.0              AI & RAG Module
2026 Q3  │ v2.1.1 - v2.1.2    WebSocket, Stats, Export PDF
2026 Q4+ │ v3.0.0              Major Release
```

---

## Historial de Versiones

| Version | Fecha | Highlights |
|---------|-------|------------|
| **v2.0.12** | Feb 19, 2026 | Invitations Module + Bilingual Emails (5 endpoints, 194 tests) |
| **v2.0.11** | Feb 17, 2026 | Hotfix: naive datetime in UserOAuthAccount |
| **v2.0.10** | Feb 17, 2026 | auth_providers + has_password in UserResponseDTO |
| **v2.0.9** | Feb 16, 2026 | Google OAuth (login, link, unlink) + Invitations (5 endpoints) |
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
