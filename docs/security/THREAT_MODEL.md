# Threat Models - Ryder Cup Amateur Manager

**Version:** 1.0
**Date:** January 29, 2026
**Last Review:** January 29, 2026
**OWASP Coverage:** A04: Insecure Design (Threat Modeling)

---

## Overview

This document describes threat models for critical business flows using the **STRIDE** methodology:
- **S**poofing - Impersonating someone
- **T**ampering - Modifying data or code
- **R**epudiation - Claiming not to have performed an action
- **I**nformation Disclosure - Exposing information to unauthorized users
- **D**enial of Service - Denying or degrading service to users
- **E**levation of Privilege - Gaining capabilities without authorization

---

## 1. Authentication Flow

### Assets
- User credentials (email, password)
- JWT access tokens (15 min)
- JWT refresh tokens (7 days)
- Session data (cookies, device fingerprints)
- User authentication state

### Data Flow
```
User → API (email + password) → Verify credentials → Generate JWT → Set httpOnly cookies → Return user data
```

### STRIDE Analysis

| Threat | Risk | Mitigation | Status |
|--------|------|------------|--------|
| **Spoofing**: Attacker impersonates legitimate user | ⚠️ MEDIUM | bcrypt password hashing (12 rounds), email verification | ✅ Mitigated |
| **Tampering**: Attacker modifies JWT token | ⚠️ MEDIUM | JWT signature verification (HS256), token validation on every request | ✅ Mitigated |
| **Repudiation**: User denies login action | 🟢 LOW | Security audit logs (`UserLoggedInEvent`), correlation IDs | ✅ Mitigated |
| **Information Disclosure**: JWT stolen from client | ⚠️ MEDIUM | httpOnly cookies (no JS access), HTTPS only, SameSite=lax | ✅ Mitigated |
| **Denial of Service**: Brute force login attempts | ⚠️ MEDIUM | Rate limiting (5/min), account lockout (10 attempts, 30 min) | ✅ Mitigated |
| **Elevation of Privilege**: Normal user becomes admin | 🔴 HIGH | RBAC checks, `is_admin` field in DB, no public admin creation endpoint | ✅ Mitigated |

### Residual Risks
- 🟡 **Session Hijacking**: If attacker gains physical access to device with active session → **Mitigation**: Session timeout (15 min), device fingerprinting, manual device revocation

---

## 2. Competition Creation Flow

### Assets
- Competition metadata (name, dates, location, settings)
- Creator permissions (competition ownership)
- System resources (database storage, API capacity)

### Data Flow
```
Creator → API (competition data) → Validate limits → Validate dates → Create competition → Assign creator ownership → Return competition
```

### STRIDE Analysis

| Threat | Risk | Mitigation | Status |
|--------|------|------------|--------|
| **Spoofing**: Non-creator modifies competition | ⚠️ MEDIUM | RBAC checks (`require_creator_or_admin`), JWT authentication | ✅ Mitigated |
| **Tampering**: Malicious modification of competition settings | ⚠️ MEDIUM | Input validation (Pydantic), business logic guards, value objects | ✅ Mitigated |
| **Repudiation**: Creator denies creating competition | 🟢 LOW | `CompetitionCreatedEvent`, audit logs, `creator_id` field | ✅ Mitigated |
| **Information Disclosure**: Unauthorized access to competition data | 🟢 LOW | Only creators/admins can view DRAFT competitions, public after ACTIVE | ✅ Mitigated |
| **Denial of Service**: Resource exhaustion (create 10000 competitions) | 🔴 HIGH | **NEW:** `CompetitionPolicy.can_create_competition` (limit: 50 per user) ⭐ | ✅ Mitigated |
| **Elevation of Privilege**: Non-creator gains creator permissions | ⚠️ MEDIUM | Immutable `creator_id` field, no transfer ownership endpoint | ✅ Mitigated |

### Residual Risks
- 🟡 **Malicious Competition Names**: Creator uses offensive names → **Mitigation**: Content moderation (manual review, future: AI filter)

---

## 3. Enrollment Flow

### Assets
- Enrollment status (REQUESTED, APPROVED, REJECTED)
- Competition capacity (max_players limit)
- User enrollment history
- Team assignments

### Data Flow
```
Player → API (enrollment request) → Validate competition status → Check duplicates → Check capacity → Check user limits → Create enrollment → Await approval
```

### STRIDE Analysis

| Threat | Risk | Mitigation | Status |
|--------|------|------------|--------|
| **Spoofing**: Bot enrollments (fake users) | 🔴 HIGH | **RISK**: No CAPTCHA or bot prevention implemented ⚠️ | ❌ Open Risk |
| **Tampering**: Modify enrollment status without approval | ⚠️ MEDIUM | State machine validation, RBAC checks, only creator/admin can approve | ✅ Mitigated |
| **Repudiation**: User denies enrollment action | 🟢 LOW | `EnrollmentRequestedEvent`, audit logs, timestamps | ✅ Mitigated |
| **Information Disclosure**: Leak of enrollment lists | 🟢 LOW | Only creator/admin/players can view enrollments | ✅ Mitigated |
| **Denial of Service**: Duplicate enrollments | ⚠️ MEDIUM | **NEW:** `CompetitionPolicy.can_enroll` (duplicate prevention) ⭐ | ✅ Mitigated |
| **Denial of Service**: Enrollment spam (enroll in 1000 competitions) | 🔴 HIGH | **NEW:** `CompetitionPolicy.can_enroll` (limit: 20 active enrollments) ⭐ | ✅ Mitigated |
| **Denial of Service**: Capacity bypass (enroll when full) | ⚠️ MEDIUM | **NEW:** `CompetitionPolicy.validate_capacity` (checks before approval) ⭐ | ✅ Mitigated |
| **Elevation of Privilege**: Self-approve enrollment | ⚠️ MEDIUM | Only creator/admin can approve, not the enrolled user | ✅ Mitigated |

### Residual Risks
- 🔴 **Bot Attacks**: Automated enrollment requests → **Mitigation Needed**: Implement CAPTCHA (Google reCAPTCHA v3) or rate limiting per IP
- 🟡 **Competition Start Bypass**: Enroll after competition started → **NEW:** Temporal validation in `CompetitionPolicy.can_enroll` ⭐ | ✅ Mitigated

---

## 4. Password Reset Flow

### Assets
- Password reset tokens (256-bit, 24h expiration)
- User email addresses
- New password (plaintext temporarily in memory)

### Data Flow
```
User → API (reset request) → Generate token → Send email → User clicks link → Submit new password → Validate token → Hash password → Invalidate old sessions
```

### STRIDE Analysis

| Threat | Risk | Mitigation | Status |
|--------|------|------------|--------|
| **Spoofing**: Attacker requests reset for victim's email | ⚠️ MEDIUM | Token sent only to registered email, timing attack prevention | ✅ Mitigated |
| **Tampering**: Token manipulation | ⚠️ MEDIUM | 256-bit secure random token, stored hashed (SHA256), single-use | ✅ Mitigated |
| **Repudiation**: User denies requesting reset | 🟢 LOW | `PasswordResetRequestedEvent`, audit logs | ✅ Mitigated |
| **Information Disclosure**: Token leaked in email | ⚠️ MEDIUM | HTTPS links only, token expires in 24h, single-use | ✅ Mitigated |
| **Denial of Service**: Reset spam | ⚠️ MEDIUM | Rate limiting (3/hour per email) | ✅ Mitigated |
| **Elevation of Privilege**: Reset admin password | 🟢 LOW | No special treatment, same flow for all users | ✅ Mitigated |

### Residual Risks
- 🟡 **Email Compromise**: If attacker has access to user's email, can reset password → **Inherent risk** (email security is user's responsibility)

---

## 5. API Rate Limiting

### Assets
- API availability
- Server resources (CPU, memory, DB connections)
- Fair usage across users

### STRIDE Analysis

| Threat | Risk | Mitigation | Status |
|--------|------|------------|--------|
| **Denial of Service**: API flooding (10000 requests/sec) | 🔴 HIGH | SlowAPI rate limiting (global 100/min, endpoint-specific limits) | ✅ Mitigated |
| **Denial of Service**: Slow loris attacks | ⚠️ MEDIUM | Uvicorn timeout configuration, reverse proxy (nginx) | ✅ Mitigated |
| **Denial of Service**: Database connection exhaustion | ⚠️ MEDIUM | SQLAlchemy pool limits, async operations | ✅ Mitigated |
| **Elevation of Privilege**: Bypass rate limits | 🟢 LOW | Rate limits applied before authentication (IP-based) | ✅ Mitigated |

### Rate Limits by Endpoint

| Endpoint | Limit | Reason |
|----------|-------|--------|
| `POST /auth/login` | 5/min | Prevent brute force |
| `POST /auth/register` | 3/hour | Prevent spam accounts |
| `POST /handicaps/update` | 5/hour | RFEG scraping rate limit |
| `POST /competitions` | 10/hour | Prevent spam competitions |
| **Global** | 100/min | General DoS protection |

---

## Summary of NEW Mitigations (v2.0.0)

This threat model documents **security improvements from A04: Insecure Design initiative**:

1. ⭐ **Business Logic Guards** (`CompetitionPolicy`)
   - Competition creation limit: 50 per user
   - Enrollment limit: 20 active enrollments per user
   - Duplicate enrollment prevention
   - Capacity validation (prevent enrolling when full)
   - Temporal validation (prevent enrolling after start date)

2. ⭐ **Resource Abuse Prevention**
   - Date range validation (max 365 days)
   - Enrollment state machine validation

3. ⭐ **Threat Modeling Documentation** (this document)
   - STRIDE analysis for 5 critical flows
   - Residual risk identification
   - Mitigation tracking

---

## Risk Matrix

| Risk Level | Count | Status |
|------------|-------|--------|
| 🔴 HIGH | 1 | **Bot Attacks** (Enrollment) - Future mitigation: CAPTCHA |
| 🟡 MEDIUM | 3 | Acceptable residual risks |
| 🟢 LOW | All others | Mitigated |

---

## Next Steps

1. **Priority 1**: Implement CAPTCHA for enrollment requests (Google reCAPTCHA v3)
2. **Priority 2**: Add content moderation for competition names
3. **Priority 3**: Monitor rate limit effectiveness in production

---

**Review Schedule**: Quarterly or after major security incidents
**Owner**: Development Team
**Approval**: Security Lead
