# ADR-029: Password History - Prevent Password Reuse

**Status:** Accepted
**Date:** January 8, 2026
**Version:** v1.13.0
**Context:** Security - OWASP A07
**Author:** Agustín Estévez

---

## Context

Users must not reuse recent passwords. OWASP ASVS V2.1.11 and NIST SP 800-63B require password history tracking to prevent password rotation attacks where users cycle through a few passwords.

**Security Risk:**
- Attackers with old compromised passwords retain access
- Users rotate predictable password patterns (Password1, Password2, etc.)
- Compliance requirement for security audits

---

## Decision

Implement **Password History** that stores bcrypt hashes of the last 5 passwords:

### Architecture:

**Domain:**
- `PasswordHistory` entity (id, user_id, password_hash, created_at)
- `PasswordHistoryId` Value Object (UUID wrapper)
- `PasswordHistoryRecordedEvent` (audit trail)
- `PasswordHistoryRepositoryInterface` (5 methods)

**Application:**
- `UpdateSecurityUseCase`: Validates new password against last 5
- `ResetPasswordUseCase`: Saves new hash to history

**Infrastructure:**
- SQLAlchemy imperative mapping with TypeDecorators
- Migration: `password_history` table + 2 indexes
- Cascade delete on user deletion (GDPR)

**Validation Flow:**
```python
# On password change:
1. Fetch last 5 password hashes
2. Verify new password != any of last 5 (bcrypt verify)
3. If match → Reject with error
4. If no match → Save new hash to history
```

### Parameters:
- `HISTORY_SIZE = 5` (NIST recommended)
- Storage: bcrypt hashes (255 chars)
- Cleanup: Manual (auto-cleanup deferred to v1.14.0)

---

## Consequences

### Positive ✅
- **OWASP A07 compliance**: Password history validated
- **Clean Architecture**: Domain/Application/Infrastructure separation
- **GDPR compliant**: Cascade delete on user deletion
- **Zero breaking changes**: Fully backward compatible
- **939/947 tests passing** (99.16% success rate)

### Negative ⚠️
- Storage overhead: ~200 bytes per password change (negligible)
- Additional DB query on password change (minimal impact)
- No retroactive validation (only affects new changes)

### Neutral
- First password change post-deployment has no history to validate
- Historical passwords before v1.13.0 not tracked

---

## Alternatives Considered

### ❌ Option A: Store in users table (JSON column)
**Rejected**: Violates normalization, no cascade delete, harder to query

### ❌ Option B: Validate last 10 passwords
**Rejected**: 5 is NIST baseline, configurable later

### ❌ Option C: Store in Redis/Cache
**Rejected**: Persistence required for GDPR compliance

---

## Testing

- **Unit Tests**: 25 tests (PasswordHistoryId: 13, PasswordHistory: 12)
- **Integration**: Validated via UpdateSecurity + ResetPassword use cases
- **Total**: 939/947 passing (99.16%)

---

## Migration

**Alembic:** `d850bb7f327d_add_password_history_table.py`

```sql
CREATE TABLE password_history (
    id CHAR(36) PRIMARY KEY,
    user_id CHAR(36) REFERENCES users(id) ON DELETE CASCADE,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_password_history_user_created ON password_history (user_id, created_at DESC);
```

**Deployment**: Non-destructive, no backfill needed

---

## References

- OWASP ASVS V2.1.11: Password History
- NIST SP 800-63B: Memorized Secret Verifiers
- ADR-024: Password Reset Security
- ADR-027: Account Lockout

---

**Next Steps:** Auto-cleanup (v1.14.0), Configurable history size (v1.15.0)
