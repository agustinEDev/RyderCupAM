# ADR-030: Device Fingerprinting - Track User Login Devices

**Status:** Accepted (Updated)
**Date:** January 9, 2026 (Updated: February 4, 2026)
**Version:** v1.13.0 → v2.0.4
**Context:** Security - OWASP A01
**Author:** Agustín Estévez

---

## Context

Users need visibility into active login sessions to detect unauthorized access. OWASP A01 requires session transparency: users must see all logged devices, revoke suspicious access, and receive new device alerts.

**Security Risk:** Undetected compromise from stolen credentials, lack of session control, no audit trail.

---

## Decision

### v1.13.0 (Original)

Implement **Device Fingerprinting** that identifies devices via SHA256 hash of (device_name + user_agent + IP).

### v2.0.4 (Evolution) ⭐

**Problem Identified:** IPv6 address rotation (common with dynamic ISPs like Cloudflare) caused duplicate device records. Same browser with different /64 IPs = two separate device records.

**Solution:** Cookie-based device identification. Use the existing `UserDevice.id` (UUID) stored in an httpOnly persistent cookie (1 year) as the primary device identifier. IP addresses become audit-only fields.

---

## Architecture

### Domain Layer
- `UserDevice` entity (id, user_id, fingerprint, last_used_at, is_active)
- `UserDeviceId`, `DeviceFingerprint` Value Objects
- `NewDeviceDetectedEvent`, `DeviceRevokedEvent` (audit trail)
- `UserDeviceRepositoryInterface` (6 methods - added `find_by_id_and_user`)
- **v2.0.4**: `update_ip_address()` method for audit trail updates

### Application Layer
- `RegisterDeviceUseCase`: Cookie-first identification (v2.0.4)
- `ListUserDevicesUseCase`: `is_current_device` via cookie match (v2.0.4)
- `RevokeDeviceUseCase`: Soft delete device (is_active=False)
- **v2.0.4**: DTOs updated with `device_id_from_cookie`, `set_device_cookie`

### Infrastructure Layer
- SQLAlchemy imperative mapping with TypeDecorators
- Migration: `user_devices` table + partial unique index
- Partial index: `(user_id, fingerprint_hash) WHERE is_active=TRUE`
- **v2.0.4**: Cookie handler functions (`set_device_id_cookie`, `delete_device_id_cookie`)

### API Layer
- `GET /api/v1/users/me/devices` - List active devices
- `DELETE /api/v1/users/me/devices/{device_id}` - Revoke device
- **v2.0.4**: Login/refresh endpoints set/read `device_id` cookie

---

## Identification Strategy

### v1.13.0 (Fingerprint-based)
```python
fingerprint_hash = SHA256(device_name + "|" + user_agent + "|" + ip_address)
```

### v2.0.4 (Cookie-based) ⭐
```python
# PRIMARY: Cookie httpOnly (1 year expiration)
device_id = request.cookies.get("device_id")

# If cookie present → find device by ID + user ownership
device = await repo.find_by_id_and_user(device_id, user_id)

# If no cookie → create new device, set cookie in response
if not device_id:
    device = UserDevice.create(...)
    response.set_cookie("device_id", str(device.id), ...)
```

**Cookie Security (OWASP Compliant):**
- `httpOnly=True`: XSS protection (no JS access)
- `secure=True`: HTTPS only in production
- `samesite="lax"`: CSRF protection
- `domain=COOKIE_DOMAIN`: Cross-subdomain support (`.rydercupfriends.com`)
- `max_age=31536000`: 1 year persistence

---

## Key Design Decisions

1. **v2.0.4: Cookie > Fingerprint**: Cookie is the primary identifier; fingerprint retained for device_name generation only
2. **IP for Audit Only**: IP addresses are stored for security logging but not used for identification
3. **Soft Delete**: `is_active=FALSE` instead of hard delete (audit trail)
4. **Partial Unique Index**: Prevents duplicate active devices, allows multiple revoked
5. **Auto-Registration**: Login/RefreshToken endpoints call RegisterDeviceUseCase
6. **User Ownership Validation**: All lookups validate `device.user_id == authenticated_user.id`

---

## Consequences

### Positive ✅
- **OWASP A01 compliance**: Session transparency validated
- **Clean Architecture**: Full 4-layer separation
- **No duplicate devices**: Cookie persists across IP changes (VPN, mobile, dynamic IPv6)
- **User empowerment**: Self-service device management
- **Better UX**: `is_current_device` reliably identifies current browser

### Negative ⚠️
- Storage overhead: ~150 bytes per device
- Cookie dependency: If user clears cookies, new device is created
- Additional DB query on login/refresh

---

## Alternatives Considered

- **❌ Fingerprint + IP normalization**: Helps with same /24 or /64 but doesn't solve cross-network scenarios
- **❌ Fingerprint without IP**: Same device from different networks bypasses detection
- **❌ Hard delete revoked devices**: Loses audit trail
- **❌ Store in Redis/Cache**: Persistence required for GDPR compliance
- **✅ Cookie-based identification**: Chosen - persistent, reliable, OWASP-compliant

---

## Testing

### v1.13.0
- **Unit Tests**: 86 tests (Domain: 66, Application: 20)
- **Integration Tests**: 13 tests (API endpoints with PostgreSQL)

### v2.0.4
- **Unit Tests**: Updated for cookie-based identification
- **Integration Tests**: Updated to verify cookie flow
- **New scenarios**: IP rotation tolerance, cookie persistence, is_current_device accuracy

---

## Migration

**v1.13.0 - Alembic:** `50ccf425ff32_add_user_devices_table.py`

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

**v2.0.4**: No database migration needed. Cookie is set client-side; `device.id` (existing column) is used as `device_id`.

---

## References

- OWASP A01: Broken Access Control
- ADR-019: httpOnly Cookies
- ADR-020: Session Timeout with Refresh Tokens
- ADR-027: Account Lockout

---

**Next Steps:** Email notifications on new device (v1.14.0), Auto-expiration (v1.15.0)
