# 🌐 API Reference

**Base URL**: `http://localhost:8000`
**Swagger UI**: `/docs` (auto-generated with interactive examples)
**ReDoc**: `/redoc` (alternative documentation)
**Total Endpoints**: 39 active
**Version**: v1.13.0
**Last Updated**: 9 January 2026

---

## 📋 Quick Reference

```
Authentication (11 endpoints)
├── POST /api/v1/auth/register           # User registration
├── POST /api/v1/auth/login              # JWT authentication (httpOnly cookies, lockout after 10 attempts)
├── GET  /api/v1/auth/current-user       # Get authenticated user info
├── POST /api/v1/auth/logout             # Session logout (revoke refresh tokens)
├── POST /api/v1/auth/verify-email       # Email verification
├── POST /api/v1/auth/resend-verification # Resend verification email
├── POST /api/v1/auth/refresh-token      # Renew access token
├── POST /api/v1/auth/forgot-password    # Request password reset (email with token)
├── POST /api/v1/auth/reset-password     # Complete password reset
├── GET  /api/v1/auth/validate-reset-token/:token # Validate reset token
└── POST /api/v1/auth/unlock-account     # Manual account unlock (Admin, v1.13.0)

User Management (3 endpoints)
├── GET   /api/v1/users/search           # Search users by email/name
├── PATCH /api/v1/users/profile          # Update profile (name/surname/country)
└── PATCH /api/v1/users/security         # Update security (email/password)

Device Management (2 endpoints) ⭐ v1.13.0
├── GET    /api/v1/users/me/devices      # List active devices
└── DELETE /api/v1/users/me/devices/{id} # Revoke device

Handicap Management (3 endpoints)
├── POST /api/v1/handicaps/update        # Update single user handicap (RFEG)
├── POST /api/v1/handicaps/update-multiple # Batch handicap updates
└── POST /api/v1/handicaps/update-manual # Manual handicap update

Competition Management (10 endpoints)
├── POST /api/v1/competitions            # Create competition
├── GET  /api/v1/competitions            # List competitions with filters
├── GET  /api/v1/competitions/{id}       # Get competition details
├── PUT  /api/v1/competitions/{id}       # Update competition (DRAFT only)
├── DELETE /api/v1/competitions/{id}     # Delete competition (DRAFT only)
├── POST /api/v1/competitions/{id}/activate         # DRAFT → ACTIVE
├── POST /api/v1/competitions/{id}/close-enrollments # ACTIVE → CLOSED
├── POST /api/v1/competitions/{id}/start            # CLOSED → IN_PROGRESS
├── POST /api/v1/competitions/{id}/complete         # IN_PROGRESS → COMPLETED
└── POST /api/v1/competitions/{id}/cancel           # Any state → CANCELLED

Enrollment Management (8 endpoints)
├── POST /api/v1/competitions/{id}/enrollments      # Request enrollment
├── POST /api/v1/competitions/{id}/enrollments/direct # Direct enroll (creator only)
├── GET  /api/v1/competitions/{id}/enrollments      # List enrollments
├── POST /api/v1/enrollments/{id}/approve           # Approve enrollment
├── POST /api/v1/enrollments/{id}/reject            # Reject enrollment
├── POST /api/v1/enrollments/{id}/cancel            # Cancel enrollment
├── POST /api/v1/enrollments/{id}/withdraw          # Withdraw from competition
└── PUT  /api/v1/enrollments/{id}/handicap          # Set custom handicap

Country Management (2 endpoints)
├── GET  /api/v1/countries               # List all countries
└── GET  /api/v1/countries/{code}/adjacent # List adjacent countries
```

---

## 🔐 Authentication

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/auth/register` | POST | No | User registration + email verification |
| `/auth/login` | POST | No | Login with JWT (httpOnly cookies) - **Lockout after 10 failed attempts** |
| `/auth/current-user` | GET | Yes | Get authenticated user |
| `/auth/logout` | POST | Yes | Logout with refresh token revocation |
| `/auth/refresh-token` | POST | No | Renew access token (uses refresh cookie) |
| `/auth/verify-email` | POST | No | Verify email with unique token |
| `/auth/resend-verification` | POST | No | Resend verification email |
| `/auth/forgot-password` | POST | No | Request password reset (sends email with token) |
| `/auth/reset-password` | POST | No | Complete password reset using token |
| `/auth/validate-reset-token/{token}` | GET | No | Validate reset token before showing form |
| `/auth/unlock-account` | POST | Yes | Manual account unlock (Admin) - **v1.13.0** |


### Main Fields

**Register Request:**
- `email` (string, required, max 254, unique)
- `password` (string, required, 12-128 chars, OWASP ASVS V2.1)
- `first_name` (string, required, max 100)
- `last_name` (string, required, max 100)
- `country_code` (string, optional, ISO 3166-1 alpha-2)

**Login Request:**
- `email` (string, required)
- `password` (string, required)

**Login Response:**
- `access_token` (string, JWT) - LEGACY, use cookie
- `refresh_token` (string, JWT) - LEGACY, use cookie
- `csrf_token` (string, 256-bit) - CSRF protection token (v1.13.0)
- `user` (object) - User data
- httpOnly Cookies: `access_token` (15 min), `refresh_token` (7 days)
- Cookie NO httpOnly: `csrf_token` (15 min, readable by JS)

**Forgot Password Request:**
- `email` (string, required)

**Forgot Password Response:**
- `message` (string) - Generic success message

**Reset Password Request:**
- `token` (string, required) - Token received via email
- `new_password` (string, required, 12-128 chars, OWASP ASVS V2.1)

**Reset Password Response:**
- `message` (string) - Confirmation message

**Validate Reset Token Response:**
- `valid` (bool) - Indicates if token is valid
- `message` (string) - Explanatory message

**Unlock Account Request:**
- `user_id` (string, required, UUID) - ID of user to unlock
- `unlocked_by_user_id` (string, auto-extracted from JWT) - ID of admin unlocking

**Unlock Account Response:**
- `success` (bool) - Indicates if unlock was successful
- `message` (string) - Confirmation message
- `user_id` (string) - ID of unlocked user
- `unlocked_by` (string) - ID of admin who performed unlock


### Security Notes

- **httpOnly Cookies:** JWT stored in cookies inaccessible from JavaScript
- **Dual Support:** Cookies (priority 1) + Headers (legacy)
- **Rate Limiting:** Login 5/min, Register 3/h, Resend 3/h, Forgot/Reset 3/h, Validate 10/h
- **Password Policy:** 12 chars min, full complexity, blacklist
- **Forgot/Reset:** Generic message, never reveals if email exists (prevents user enumeration)
- **Reset Token:** Single-use token, expires in 24h, invalidates all active sessions after change
- **Refresh Tokens:** SHA256 hash in DB, revocable on logout
- **Account Lockout (v1.13.0):** 10 failed attempts → 30 min lockout, auto-unlock, HTTP 423 Locked

**📋 See details:** `docs/modules/user-management.md`, `docs/SECURITY_IMPLEMENTATION.md`

---

## 👤 User Management

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/users/search` | GET | Yes | Search users by email/name |
| `/users/profile` | PATCH | Yes | Update profile (name, surname, country) |
| `/users/security` | PATCH | Yes | Change email or password |

### Query Parameters

**GET /users/search:**
- `query` (string, optional) - Partial search in email, first_name, last_name
- Returns array of users with basic data

### Notes

- Only authenticated users can search
- No sensitive information exposed (passwords, tokens)
- country_code can be null

**📋 See complete module:** `docs/modules/user-management.md`

---

## 📱 Device Management ⭐ v1.13.0

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/users/me/devices` | GET | Yes | List active devices for authenticated user |
| `/users/me/devices/{device_id}` | DELETE | Yes | Revoke device (soft delete) |

### Main Fields

**List Devices Response:**
- `devices` (array) - List of active devices
  - `id` (string, UUID) - Device ID
  - `device_name` (string) - Friendly name (e.g., "Chrome 120.0 on macOS")
  - `ip_address` (string) - Last known IP address
  - `last_used_at` (datetime) - Last login timestamp
  - `created_at` (datetime) - First seen timestamp
  - `is_active` (boolean) - Always `true` (revoked devices not shown)
- `total_count` (int) - Number of active devices

**Revoke Device Response:**
- `message` (string) - Success message
- `device_id` (string) - Revoked device ID

### Business Logic

- **Fingerprint Formula**: `SHA256(device_name + "|" + user_agent + "|" + ip_address)`
- **Auto-registration**: Devices automatically registered on login/refresh token
- **Soft delete**: Revoked devices marked as `is_active=FALSE` (audit trail preserved)
- **Ownership validation**: Users can only revoke their own devices
- **Partial unique index**: `(user_id, fingerprint_hash) WHERE is_active=TRUE`
- **Domain Events**: `NewDeviceDetectedEvent`, `DeviceRevokedEvent`

### Status Codes

- `200 OK` - Success (list/revoke)
- `401 Unauthorized` - Not authenticated
- `403 Forbidden` - Device belongs to another user
- `404 Not Found` - Device not found or invalid UUID
- `409 Conflict` - Device already revoked

### Examples

**GET /api/v1/users/me/devices**
```json
{
  "devices": [
    {
      "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
      "device_name": "Chrome 120.0 on macOS",
      "ip_address": "192.168.1.100",
      "last_used_at": "2026-01-09T10:30:00Z",
      "created_at": "2026-01-05T08:15:00Z",
      "is_active": true
    }
  ],
  "total_count": 1
}
```

**DELETE /api/v1/users/me/devices/a1b2c3d4-e5f6-7890-abcd-ef1234567890**
```json
{
  "message": "Dispositivo revocado exitosamente",
  "device_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
}
```

**📋 See ADR:** `docs/architecture/decisions/ADR-030-device-fingerprinting.md`

---

## ⛳ Handicap Management

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/handicaps/update` | POST | Yes | Get handicap from RFEG API (Spanish players only) |
| `/handicaps/update-manual` | POST | Yes | Update handicap manually |
| `/handicaps/update-multiple` | POST | Yes | Batch update (admin, cron job) |

### Main Fields

**Update Manual Request:**
- `handicap` (float, required, -10.0 to 54.0)

**Update RFEG Request:**
- `license_number` (string, required) - RFEG license

### Business Rules

- Only Spanish users (country_code=ES) can use RFEG
- RFEG API: 5 calls/hour per user (rate limiting)
- Handicap updates automatically + timestamp
- Domain event `HandicapUpdatedEvent` emitted

**📋 See complete module:** `docs/modules/user-management.md`

---

## 🏆 Competition Management

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/competitions` | POST | Yes | Create competition (DRAFT status) |
| `/competitions` | GET | No | List competitions with filters |
| `/competitions/{id}` | GET | No | Get competition by ID |
| `/competitions/{id}` | PUT | Yes | Update (DRAFT only, creator only) |
| `/competitions/{id}` | DELETE | Yes | Delete (DRAFT only, creator only) |
| `/competitions/{id}/activate` | POST | Yes | Transition DRAFT → ACTIVE |
| `/competitions/{id}/close-enrollments` | POST | Yes | Transition ACTIVE → CLOSED |
| `/competitions/{id}/start` | POST | Yes | Transition CLOSED → IN_PROGRESS |
| `/competitions/{id}/complete` | POST | Yes | Transition IN_PROGRESS → COMPLETED |
| `/competitions/{id}/cancel` | POST | Yes | Transition any status → CANCELLED |

### Main Fields (Create/Update)

**Competition Request:**
- `name` (string, required, 3-100 chars, unique)
- `start_date` (date, required, format YYYY-MM-DD)
- `end_date` (date, required, >= start_date)
- `country_code` (string, required, ISO 3166-1 alpha-2, main location)
- `secondary_country_code` (string, optional, must be adjacent)
- `tertiary_country_code` (string, optional, must be adjacent)
- `max_players` (int, required, 2-100)
- `handicap_type` (enum, required: "SCRATCH" | "PERCENTAGE")
- `handicap_percentage` (int, optional, 90/95/100, required if PERCENTAGE)
- `team_assignment` (enum, required: "RANDOM" | "MANUAL")
- `team_1_name` (string, optional, max 50)
- `team_2_name` (string, optional, max 50)

### Query Parameters (List)

**GET /competitions:**
- `status` (string, optional) - Filter by status (DRAFT, ACTIVE, CLOSED, IN_PROGRESS, COMPLETED, CANCELLED)
- `creator_id` (string, optional) - Filter by creator
- `my_competitions` (bool, optional) - Only competitions where user is creator or enrolled
- `search_name` (string, optional) - Partial search in name (case-insensitive)
- `search_creator` (string, optional) - Partial search in creator name

### Competition Response (Computed Fields)

- `is_creator` (bool) - Whether authenticated user is the creator
- `enrolled_count` (int) - Number of enrolled players (APPROVED)
- `location` (string) - Formatted country names (e.g.: "Spain, France")
- `creator` (object) - Complete creator data (nested object)
- `countries` (array) - List of countries with details (code, name_en, name_es)

### Status and Transitions

```
DRAFT → ACTIVE → CLOSED → IN_PROGRESS → COMPLETED
  ↓        ↓         ↓           ↓
  └────────┴─────────┴───────────┴─→ CANCELLED
```

**Rules:**
- Only creator can modify/delete/change status
- DRAFT: Only editable, not publicly visible
- ACTIVE: Enrollments open
- CLOSED: Enrollments closed, teams configured
- IN_PROGRESS: Tournament in progress
- COMPLETED: Tournament finished
- CANCELLED: Cancelled from any status

**📋 See complete module:** `docs/modules/competition-management.md`

---

## 📝 Enrollment Management

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/competitions/{id}/enrollments` | POST | Yes | Request enrollment (REQUESTED) |
| `/competitions/{id}/enrollments/direct` | POST | Yes | Direct enrollment by creator (APPROVED) |
| `/competitions/{id}/enrollments` | GET | Yes | List enrollments with filters |
| `/enrollments/{id}/approve` | POST | Yes | Approve request (creator only) |
| `/enrollments/{id}/reject` | POST | Yes | Reject request (creator only) |
| `/enrollments/{id}/cancel` | POST | Yes | Cancel request/invitation |
| `/enrollments/{id}/withdraw` | POST | Yes | Withdraw from competition |
| `/enrollments/{id}/handicap` | PUT | Yes | Set custom handicap |

### Main Fields

**Request Enrollment:**
- Only requires authentication
- Creates enrollment with REQUESTED status
- User can cancel before approval

**Direct Enroll:**
- `user_id` (string, required) - ID of user to enroll
- Only creator can execute
- Creates enrollment with APPROVED status directly

**Set Custom Handicap:**
- `custom_handicap` (float, required, -10.0 to 54.0)
- Only creator can set
- Override of user's official handicap

### Query Parameters (List)

**GET /competitions/{id}/enrollments:**
- `status` (string, optional) - Filter by status (REQUESTED, APPROVED, REJECTED, CANCELLED, WITHDRAWN)

### Enrollment States

```
REQUESTED → APPROVED → WITHDRAWN
    ↓           ↓
REJECTED    CANCELLED
```

**States:**
- `REQUESTED` - Pending approval request
- `INVITED` - Invited by creator (future)
- `APPROVED` - Enrollment approved
- `REJECTED` - Request rejected by creator
- `CANCELLED` - Cancelled by player (pre-enrollment)
- `WITHDRAWN` - Withdrawn by player (post-enrollment)

### Enrollment Response (Fields)

- `id` (string) - Enrollment UUID
- `competition_id` (string) - Competition ID
- `user_id` (string) - User ID
- `user` (object) - Complete user data (nested object)
- `status` (string) - Current status
- `custom_handicap` (float, nullable) - Custom handicap
- `team` (string, nullable) - Assigned team (1 or 2)
- `created_at` (datetime) - Request date

### Business Rules

- Competition must be in ACTIVE status for enrollments
- No duplicate enrollments allowed
- Only creator can approve/reject/enroll directly
- Only owner can cancel/withdraw
- custom_handicap is optional, if not set uses official handicap

**📋 See complete module:** `docs/modules/competition-management.md` (pending creation)

---

## 🌍 Country Management

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/countries` | GET | No | List all active countries |
| `/countries/{code}/adjacent` | GET | No | List adjacent countries |

### Country Response

**Structure:**
- `code` (string) - ISO 3166-1 alpha-2 code (e.g.: "ES")
- `name_en` (string) - Name in English (e.g.: "Spain")
- `name_es` (string) - Name in Spanish (e.g.: "España")

**Data:**
- 166 global countries (not only Europe)
- 614 bidirectional border relationships
- Support for tournaments in up to 3 adjacent countries

### Usage

- Country selectors in forms
- Adjacency validation in competition creation
- Multi-country location with bilingual names

---

## 📖 Swagger UI (Interactive Documentation)

### Access

**URL:** `http://localhost:8000/docs`
**Authentication:** HTTP Basic Auth
**Credentials:** Configured in `.env` (DOCS_USERNAME, DOCS_PASSWORD)

### Features

- ✅ Complete interactive JSON request/response examples
- ✅ "Try it out" - Execute requests directly from browser
- ✅ Auto-generated Pydantic schemas
- ✅ Documented validations and data types
- ✅ HTTP response codes (200, 400, 401, 403, 404, 422, 500)
- ✅ Authentication with Bearer token or cookies

**Recommendation:** Use Swagger UI to see complete JSON examples and test endpoints.

---

## 📬 Postman Collection

**File:** `docs/postman_collection.json`

**Features:**
- ✅ 33 pre-configured requests
- ✅ Environment variables (BASE_URL, ACCESS_TOKEN)
- ✅ Request/response examples
- ✅ Automated tests on some endpoints
- ✅ Organized by modules (Auth, Users, Competitions, Enrollments)

**Import in Postman:**
1. Open Postman
2. File → Import
3. Select `docs/postman_collection.json`
4. Configure BASE_URL variable: `http://localhost:8000`

---

## 🔒 Security and Rate Limiting

### Rate Limits per Endpoint

| Endpoint | Limit | Reason |
|----------|--------|-------|
| Global | 100/minute | Basic DoS protection |
| POST /auth/login | 5/minute | Anti brute-force |
| POST /auth/register | 3/hour | Anti registration spam |
| POST /auth/resend-verification | 3/hour | Protect Mailgun |
| POST /handicaps/update | 5/hour | Protect RFEG API |
| POST /competitions | 10/hour | Anti competition spam |

### HTTP Status Codes

| Code | Description | When used |
|------|-------------|---------------|
| 200 | OK | Successful request (GET, PUT, PATCH) |
| 201 | Created | Resource created (POST) |
| 204 | No Content | Resource deleted (DELETE) |
| 400 | Bad Request | Invalid request (Pydantic validation) |
| 401 | Unauthorized | Not authenticated or invalid token |
| 403 | Forbidden | Authenticated but no permissions |
| 404 | Not Found | Resource not found |
| 409 | Conflict | Duplicate resource (email, competition name) |
| 422 | Unprocessable Entity | Domain validation failed |
| 429 | Too Many Requests | Rate limit exceeded |
| 500 | Internal Server Error | Unhandled server error |

### Security Headers

**All responses include:**
- `Strict-Transport-Security` - HSTS (2 years)
- `X-Frame-Options` - SAMEORIGIN (prevents clickjacking)
- `X-Content-Type-Options` - nosniff (prevents MIME-sniffing XSS)
- `Referrer-Policy` - no-referrer, strict-origin-when-cross-origin
- `Cache-Control` - no-store (prevents caching sensitive data)
- `X-Correlation-ID` - Unique UUID for traceability

**📋 See complete implementation:** `docs/SECURITY_IMPLEMENTATION.md`

---

## 🔗 Related Links

### Module Documentation
- **User Management:** `docs/modules/user-management.md`
- **Competition Management:** `docs/modules/competition-management.md` (pending)

### Technical Documentation
- **Security Implementation:** `docs/SECURITY_IMPLEMENTATION.md`
- **Multi-Environment Setup:** `docs/MULTI_ENVIRONMENT_SETUP.md`
- **Deployment:** `DEPLOYMENT.md`

### Source Code
- **User Module:** `src/modules/user/infrastructure/api/v1/`
- **Competition Module:** `src/modules/competition/infrastructure/api/v1/`

### Testing
- **Postman Collection:** `docs/postman_collection.json`
- **Integration Tests:** `tests/integration/api/v1/`

---

**Last Updated:** 8 January 2026
**Version:** v1.13.0
