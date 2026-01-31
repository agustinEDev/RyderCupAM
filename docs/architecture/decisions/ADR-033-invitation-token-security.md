# ADR-033: Invitation Token Security and Auto-Enrollment

**Date**: January 27, 2026
**Status**: Accepted
**Decision Makers**: Development Team
**Sprint**: v2.0.0 - Sprint 3 (Invitations System)

## Context and Problem

Creators invite players (registered or not) to competitions.

**Need**: Secure invitation system with auto-enrollment and token-based registration.

## Decisions

### 1. Token Generation and Storage

**Generation**: 256-bit cryptographically secure token (`secrets.token_urlsafe(32)`).

**Storage**: SHA256 hash in database (defense in depth).

**Properties**: Unpredictable, collision-resistant, URL-safe.

### 2. Token Expiration

**Duration**: 7 days from creation.

**Handling**: Celery background task (every 6 hours) marks expired invitations as EXPIRED.

### 3. Invitation Types

**Type A (by user_id)**: Already registered user receives email, can accept/decline immediately.

**Type B (by email)**: Not registered. Backend searches by email:
- If exists → Type A flow
- If NOT exists → `invited_user_id=NULL`, send registration link

### 4. Auto-Enrollment on Acceptance

**Decision**: ACCEPTED invitation → Enrollment with `status=APPROVED` (bypass approval).

**Reason**: Invitation = pre-approval by Creator.

### 5. Invitation States

**States**: `PENDING`, `ACCEPTED`, `DECLINED`, `EXPIRED` (all final after PENDING).

**Transitions**: Creation → PENDING → ACCEPTED/DECLINED/EXPIRED (final).

### 6. Reinvitation Policy

**Decision**: Allow reinviting after DECLINED or EXPIRED.

**Duplicate prevention**: No multiple PENDING invitations for same user+competition.

### 7. Email Templates

**Bilingual** (ES/EN) via Mailgun. See `docs/email-templates.md`.

**Type A**: Invitation to registered user (competition details, accept/decline).
**Type B**: Invitation + registration (app description, registration link with token).

**Security**: Token only in email body (not URL GET params).

### 8. Background Task

**Technology**: Celery (existing stack).

**Schedule**: Every 6 hours, mark expired invitations.

## Consequences

### Positive ✅
- Cryptographically secure (256-bit hashed tokens)
- Smooth UX (auto-enrollment, reinvitation)
- Bilingual emails (ES/EN)
- Defense in depth (hashed storage)

### Negative ⚠️
- Requires Celery infrastructure
- Invitations can expire before seen (mitigated by 7 days)
- Token in email body (compromised email = leaked token)

## Alternatives Considered

- **JWT tokens** → Overkill for this use case
- **Plaintext storage** → Security risk
- **24-hour expiration** → Too short
- **Invitation needs approval** → Redundant, bad UX
- **No reinvitation** → Too restrictive

## References

- **ADR-024**: Password Reset Security (similar token pattern)
- **ADR-025**: Competition Module Evolution
- **ROADMAP.md**: v2.0.0 Sprint 3
- **Similar**: GitHub organization invitations
