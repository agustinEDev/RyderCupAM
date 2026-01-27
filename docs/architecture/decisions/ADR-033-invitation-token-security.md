# ADR-033: Invitation Token Security and Auto-Enrollment

**Date**: January 27, 2026
**Status**: Accepted
**Decision Makers**: Development Team
**Sprint**: v2.0.0 - Sprint 3 (Invitations System)

## Context and Problem

Creators need to invite players to their competitions. Players may be:
- Already registered (invite by user ID)
- Not registered (invite by email, player registers via token)

**Need**: Secure invitation system with auto-enrollment and token-based registration.

## Decisions

### 1. Token Generation

**Algorithm**: 256-bit cryptographically secure token

```python
import secrets

def generate_invitation_token() -> str:
    return secrets.token_urlsafe(32)  # 256 bits = 32 bytes
```

**Properties**:
- Unpredictable (not sequential)
- Collision-resistant (UUID-like entropy)
- URL-safe (no special chars needing encoding)

### 2. Token Storage

**Decision**: Store SHA256 hash (NOT plaintext)

```python
import hashlib

def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()

# Database stores hash, token sent once via email
```

**Reason**: Defense in depth (if DB leaked, tokens not compromised)

**Alternative considered**: Plaintext storage → Descartado (security risk)

### 3. Token Expiration

**Duration**: 7 days from invitation creation

```python
class Invitation:
    expires_at: datetime  # invitation_created_at + timedelta(days=7)
```

**Expiration handling**:
- Background task (Celery) runs every 6 hours
- Marks invitations as EXPIRED if `expires_at < now()`
- EXPIRED invitations cannot be accepted

**Alternative considered**: 24 hours → Descartado (too short, players need time to register)

### 4. Invitation Types

**Type A: By User ID** (already registered)
```python
POST /api/v1/competitions/{comp_id}/invitations
Body: {"user_id": "uuid-here"}
```
- User receives email notification
- Can accept/decline immediately

**Type B: By Email** (not registered)
```python
POST /api/v1/competitions/{comp_id}/invitations/by-email
Body: {"email": "player@example.com"}
```
- Backend searches user by email
- If exists → Type A flow
- If NOT exists → Create invitation with `invited_user_id=NULL`, send registration link

### 5. Auto-Enrollment on Acceptance

**Decision**: ACCEPTED invitation → create Enrollment with status **APPROVED** (bypass approval workflow)

```python
# InvitationAcceptedEvent handler
async def handle_invitation_accepted(event: InvitationAcceptedEvent):
    enrollment = Enrollment.create(
        competition_id=event.competition_id,
        user_id=event.invitee_user_id,
        status=EnrollmentStatus.APPROVED  # Direct approval
    )
    await enrollment_repo.save(enrollment)
```

**Reason**: Invitation = pre-approval by Creator (no need for manual approval)

**Alternative considered**: ACCEPTED → REQUESTED (still needs approval) → Descartado (redundant, bad UX)

### 6. Invitation States

```python
class InvitationStatus(Enum):
    PENDING = "PENDING"      # Sent, awaiting response
    ACCEPTED = "ACCEPTED"    # Player accepted
    DECLINED = "DECLINED"    # Player declined
    EXPIRED = "EXPIRED"      # 7 days passed
```

**State transitions**:
- Creation → PENDING
- Player accepts → ACCEPTED (final)
- Player declines → DECLINED (final)
- Expiration job → EXPIRED (final)

### 7. Reinvitation Policy

**Decision**: Allow reinviting player after DECLINED or EXPIRED

```python
def can_reinvite(competition_id: UUID, user_id: UUID) -> bool:
    existing_invitations = await invitation_repo.find_by_user_and_competition(
        user_id, competition_id
    )
    # Allow if no PENDING/ACCEPTED invitations
    return all(inv.status in [InvitationStatus.DECLINED, InvitationStatus.EXPIRED]
               for inv in existing_invitations)
```

**Reason**: Players change their mind, emails get lost

**Duplicate prevention**: Cannot have multiple PENDING invitations for same user+competition

### 8. Email Templates

**Bilingual** (ES/EN) using Mailgun existing infrastructure

**Invitation email** (Type A - registered user):
```
Subject: 🏌️ You're invited to {competition_name}
Body:
- Creator name invited you
- Competition details (date, location)
- Link: {FRONTEND_URL}/invitations/{token}
- Expires in 7 days
```

**Invitation + Registration email** (Type B - not registered):
```
Subject: 🏌️ Join {competition_name} on Ryder Cup Friends
Body:
- Creator name invited you
- Brief app description
- Link: {FRONTEND_URL}/register?invitation_token={token}
- Expires in 7 days
```

**Token delivery**: Only via email (NOT in URL query params for GET request → security)

### 9. Background Task Configuration

**Technology**: Celery (already in stack)

**Schedule**: Every 6 hours

```python
@celery.task
def expire_old_invitations():
    expired_invitations = await invitation_repo.find_expired()
    for invitation in expired_invitations:
        invitation.mark_as_expired()
        await invitation_repo.save(invitation)
```

**Alternative considered**: Cron job → Descartado (Celery integrates better with Python)

## Consequences

### Positive ✅
- Cryptographically secure tokens (256-bit)
- Token hashing (defense in depth)
- Smooth UX (auto-enrollment on acceptance)
- Reinvitation allowed (flexible)
- Bilingual emails (ES/EN)

### Negative ⚠️
- Requires Celery (background task infrastructure)
- Invitations can expire before player sees email (mitigated by 7 days)
- Token in email body (if email compromised, token leaked)

## Alternatives Considered

1. **JWT tokens for invitations** → Descartado (overkill, not needed here)
2. **Plaintext token storage** → Descartado (security risk)
3. **24-hour expiration** → Descartado (too short)
4. **Invitation requires approval** → Descartado (redundant, bad UX)
5. **No reinvitation** → Descartado (too restrictive)

## References

- **ADR-024**: Password Reset Security (similar token generation pattern)
- **ADR-025**: Competition Module Evolution v2.0.0 (mentions invitations briefly)
- **ROADMAP.md**: v2.0.0 Sprint 3 (Invitations System)
- **Similar pattern**: GitHub organization invitations

---
**Lines**: 97 | **Immutable after acceptance**
