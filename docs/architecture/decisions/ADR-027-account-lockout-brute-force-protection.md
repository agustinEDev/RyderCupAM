# ADR-027: Account Lockout - Brute Force Protection

**Date**: January 7, 2026
**Status**: Accepted
**Deciders**: Development Team

## Context and Problem

The system needs protection against brute force attacks on login. Must comply with OWASP A07 (Authentication Failures) without affecting legitimate user experience.

## Options Considered

1. **CAPTCHA after N attempts**: Friction, accessibility issues
2. **IP-based Rate Limiting only**: Bypassable with proxies
3. **Permanent Account Lockout**: DoS risk, poor UX
4. **Temporary Account Lockout + Auto-unlock**: Balance security-usability

## Decision

**Adopt Temporary Account Lockout with Auto-Unlock** (Option 4):

```
Flow:
├── Attempts 1-9: HTTP 401 (failure logging)
├── Attempt 10: HTTP 423 Locked (30 min lockout)
├── During lockout: HTTP 423 even with correct password
└── After 30 min: Auto-unlock + counter reset on successful login
```

### Parameters:
- `MAX_FAILED_ATTEMPTS = 10`
- `LOCKOUT_DURATION_MINUTES = 30`

### Architecture:
- **Domain**: 4 User entity methods + 2 events (AccountLocked/Unlocked)
- **Application**: Modified Login + UnlockAccountUseCase + 2 DTOs
- **Infrastructure**: Migration (2 fields + index)
- **API**: POST /unlock-account (Admin role implemented in v2.0.0 via `is_admin` flag)

## Rationale

### Security Features:
1. **Brute Force Prevention (A07)**: 10 attempts max
2. **Auto-Recovery**: Unlock after 30 min (no admin required)
3. **Persistence**: State in database (not memory)
4. **Dual Check**: Pre-password + post-password verification
5. **HTTP 423**: Semantically correct for lockout

### Technical Decisions:

**Integration in User Entity** (vs separate LoginAttempt):
- Cohesion: State belongs to User
- Performance: 1 query vs JOIN

**Naive Datetimes** (vs timezone-aware):
- Consistency with codebase (85% uses naive)
- Global migration pending v1.14.0

**Dual Check Pattern**:
```python
# Pre-check
if user.is_locked(): raise AccountLockedException

# Post-check (after record_failed_login)
if user.is_locked(): raise AccountLockedException  # Attempt 10
```

## Consequences

### Positive:
- ✅ Effective brute force mitigation (A07)
- ✅ 5/5 integration tests passing
- ✅ Compatible with rate limiting (defense in depth)
- ✅ Minimal impact on legitimate users

### Negative:
- ❌ Possible DoS (attacker locks accounts)
- ❌ Timezone naive (temporary trade-off)

### Risks Mitigated:
- Credential stuffing, dictionary attacks, automated brute force

## Validation

- [x] Complete tests (5/5 passing - 100%)
- [x] HTTP 423 at 10 attempts
- [x] Auto-unlock functional
- [x] Counter reset after successful login
- [x] Database persistence verified

## References

- [OWASP A07:2021](https://owasp.org/Top10/A07_2021-Identification_and_Authentication_Failures/)
- [OWASP Auth Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html#account-lockout)

## Implementation Notes

### Implemented (Jan 7, 2026):
- ✅ 3 commits (domain/app/infra + API/tests + fixes)
- ✅ 2 Domain Events + 1 exception
- ✅ 1 DB migration + 5 integration tests

### Lessons Learned:
- **Dual Check**: Avoids returning 401 when should be 423 on attempt 10
- **Test Strategy**: `X-Test-Client-ID` header bypasses rate limiting without modifying production
- **Timezone Trade-off**: Consistency > safety (global refactor pending)
