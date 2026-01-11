# ADR-030: Device Fingerprinting - Track User Login Devices

**Status:** Accepted
**Date:** January 9, 2026
**Version:** v1.13.0
**Context:** Security - OWASP A01
**Author:** Agustín Estévez

---

## Context

Users need visibility into active login sessions to detect unauthorized access. OWASP A01 requires session transparency: users must see all logged devices, revoke suspicious access, and receive new device alerts.

**Security Risk:** Undetected compromise from stolen credentials, lack of session control, no audit trail.

---

## Decision

Implement **Device Fingerprinting** that identifies devices via SHA256 hash of (device_name + user_agent + IP):

### Architecture:

**Domain:**
- `UserDevice` entity (id, user_id, fingerprint, last_used_at, is_active)
- `UserDeviceId`, `DeviceFingerprint` Value Objects
- `NewDeviceDetectedEvent`, `DeviceRevokedEvent` (audit trail)
- `UserDeviceRepositoryInterface` (5 methods)

**Application:**
- `RegisterDeviceUseCase`: Create or update device on login/refresh
- `ListUserDevicesUseCase`: List active devices for authenticated user
- `RevokeDeviceUseCase`: Soft delete device (is_active=False)

**Infrastructure:**
- SQLAlchemy imperative mapping with TypeDecorators
- Migration: `user_devices` table + partial unique index
- Partial index: `(user_id, fingerprint_hash) WHERE is_active=TRUE`

**API:**
- `GET /api/v1/users/me/devices` - List active devices
- `DELETE /api/v1/users/me/devices/{device_id}` - Revoke device

**Fingerprint Formula:**
```python
fingerprint_hash = SHA256(device_name + "|" + user_agent + "|" + ip_address)
```

### Key Design Decisions:

1. **IP Address Included**: Different networks = different devices (stricter security)
2. **Soft Delete**: `is_active=FALSE` instead of hard delete (audit trail)
3. **Partial Unique Index**: Prevents duplicate active devices, allows multiple revoked
4. **Auto-Registration**: Login/RefreshToken endpoints call RegisterDeviceUseCase
5. **User Ownership Validation**: Revoke checks device belongs to authenticated user

---

## Consequences

### Positive ✅
- **OWASP A01 compliance**: Session transparency validated
- **Clean Architecture**: Full 4-layer separation
- **910/910 tests passing** (100%)
- **User empowerment**: Self-service device management

### Negative ⚠️
- Storage overhead: ~150 bytes per device
- IP changes create new devices (VPN/mobile users affected)
- Additional DB query on login/refresh

---

## Alternatives Considered

- **❌ Exclude IP from fingerprint**: Same device from different networks bypasses detection
- **❌ Hard delete revoked devices**: Loses audit trail
- **❌ Store in Redis/Cache**: Persistence required for GDPR compliance

---

## Testing

- **Unit Tests**: 86 tests (Domain: 66, Application: 20)
- **Integration Tests**: 13 tests (API endpoints with PostgreSQL)
- **Total**: 910/910 passing (100%)

---

## Migration

**Alembic:** `50ccf425ff32_add_user_devices_table.py`

```sql
CREATE TABLE user_devices (
    id CHAR(36) PRIMARY KEY,
    user_id CHAR(36) REFERENCES users(id) ON DELETE CASCADE,
    fingerprint_hash CHAR(64) NOT NULL,
    device_name VARCHAR(255) NOT NULL,
    ip_address VARCHAR(45) NOT NULL,
    last_used_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE
);
CREATE UNIQUE INDEX idx_user_devices_unique_active ON user_devices (user_id, fingerprint_hash) WHERE is_active=TRUE;
CREATE INDEX idx_user_devices_user_active ON user_devices (user_id, is_active);
```

**Deployment**: Non-destructive, no backfill needed

---

## References

- OWASP A01: Broken Access Control
- ADR-019: httpOnly Cookies
- ADR-020: Session Timeout with Refresh Tokens
- ADR-027: Account Lockout

---

**Next Steps:** Email notifications on new device (v1.14.0), Auto-expiration (v1.15.0)
