# 🌐 API Reference

**Base URL**: `http://localhost:8000`
**Swagger UI**: `/docs` (auto-generated with interactive examples)
**ReDoc**: `/redoc` (alternative documentation)
**Total Endpoints**: 80 active
**Version**: Sprint 4 (Live Scoring + Leaderboard)
**Last Updated**: 24 February 2026

---

## 📋 Quick Reference

```text
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

Google OAuth (3 endpoints) ⭐ Sprint 3
├── POST   /api/v1/auth/google           # Login/register with Google (public, auto-link/auto-register)
├── POST   /api/v1/auth/google/link      # Link Google account to existing user (auth + CSRF)
└── DELETE /api/v1/auth/google/unlink    # Unlink Google account (auth + CSRF)

User Management (5 endpoints)
├── GET   /api/v1/users/search-autocomplete # Autocomplete search by partial name ⭐ Sprint 4
├── GET   /api/v1/users/search           # Search users by email/name
├── PATCH /api/v1/users/profile          # Update profile (name/surname/country)
├── PATCH /api/v1/users/security         # Update security (email/password)
└── GET   /api/v1/users/me/roles/{id}    # Check user roles in a competition (v2.0.0)

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

Competition-GolfCourse Management (4 endpoints) ⭐ v2.0.2
├── POST   /api/v1/competitions/{id}/golf-courses    # Add golf course to competition
├── DELETE /api/v1/competitions/{id}/golf-courses/{gc_id} # Remove golf course
├── PUT    /api/v1/competitions/{id}/golf-courses/reorder # Reorder all courses
└── GET    /api/v1/competitions/{id}/golf-courses    # List competition's golf courses

Rounds & Schedule Management (4 endpoints) ⭐ Sprint 2
├── POST   /api/v1/competitions/{id}/rounds          # Create round/session
├── PUT    /api/v1/competitions/rounds/{id}           # Update round details
├── DELETE /api/v1/competitions/rounds/{id}           # Delete round + cascade matches
└── GET    /api/v1/competitions/{id}/schedule         # Get full schedule grouped by day

Match Management (4 endpoints) ⭐ Sprint 2
├── GET    /api/v1/competitions/matches/{id}          # Match detail with players/handicaps
├── PUT    /api/v1/competitions/matches/{id}/status   # Start or complete match
├── POST   /api/v1/competitions/matches/{id}/walkover # Declare walkover
└── PUT    /api/v1/competitions/matches/{id}/players  # Reassign players (recalc handicaps)

Teams & Generation (3 endpoints) ⭐ Sprint 2
├── POST   /api/v1/competitions/{id}/teams            # Assign teams (snake draft/manual)
├── POST   /api/v1/competitions/rounds/{id}/matches/generate # Generate matches for round
└── POST   /api/v1/competitions/{id}/schedule/configure # Configure schedule (auto/manual)

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

Golf Course Management (10 endpoints) ⭐ v2.0.1
├── POST /api/v1/golf-courses/request    # Request new golf course (Creator)
├── POST /api/v1/golf-courses/admin      # Create course directly (Admin, approved)
├── GET  /api/v1/golf-courses/{id}       # Get golf course details
├── GET  /api/v1/golf-courses            # List golf courses (filter by approval_status)
├── GET  /api/v1/golf-courses/admin/pending # List pending approvals (Admin)
├── PUT  /api/v1/golf-courses/admin/{id}/approve # Approve course (Admin)
├── PUT  /api/v1/golf-courses/admin/{id}/reject  # Reject course (Admin)
├── PUT  /api/v1/golf-courses/{id}       # Submit update (Creator, clone-based workflow)
├── PUT  /api/v1/golf-courses/admin/updates/{id}/approve # Approve update (Admin)
└── PUT  /api/v1/golf-courses/admin/updates/{id}/reject  # Reject update (Admin)

Invitation Management (5 endpoints) ⭐ v2.0.12
├── POST /api/v1/competitions/{id}/invitations          # Invite by user ID
├── POST /api/v1/competitions/{id}/invitations/by-email # Invite by email
├── GET  /api/v1/invitations/me                         # My pending invitations
├── POST /api/v1/invitations/{id}/respond               # Accept/Decline invitation
└── GET  /api/v1/competitions/{id}/invitations          # Creator view (all invitations)

Scoring & Leaderboard (5 endpoints) ⭐ Sprint 4
├── GET  /api/v1/competitions/matches/{id}/scoring-view          # Unified scoring view
├── POST /api/v1/competitions/matches/{id}/scores/holes/{n}      # Submit hole score
├── POST /api/v1/competitions/matches/{id}/scorecard/submit      # Submit scorecard
├── GET  /api/v1/competitions/{id}/leaderboard                   # Competition leaderboard
└── PUT  /api/v1/competitions/matches/{id}/concede               # Concede match

Support (1 endpoint) ⭐ v2.0.8
└── POST /api/v1/support/contact         # Submit contact form (creates GitHub Issue)
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
- `user` (object) - User data (see User Object below)
- httpOnly Cookies: `access_token` (15 min), `refresh_token` (7 days)
- Cookie NO httpOnly: `csrf_token` (15 min, readable by JS)

**User Object (UserResponseDTO):**
Returned in all endpoints that include user data (login, current-user, register, refresh-token, etc.)
- `id` (string, UUID) - User ID
- `email` (string) - User email
- `first_name` (string) - First name
- `last_name` (string) - Last name
- `country_code` (string, nullable) - ISO 3166-1 alpha-2
- `handicap` (float, nullable) - Golf handicap
- `handicap_updated_at` (datetime, nullable) - Last handicap update
- `email_verified` (bool) - Whether email is verified
- `is_admin` (bool) - Global admin flag
- `gender` (string, nullable) - "MALE" or "FEMALE"
- `auth_providers` (string[], default `[]`) - Linked OAuth providers (e.g. `["google"]`) ⭐ v2.0.10
- `has_password` (bool, default `true`) - Whether user has a password set ⭐ v2.0.10
- `created_at` (datetime) - Account creation timestamp
- `updated_at` (datetime) - Last update timestamp

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

## 🔐 Google OAuth ⭐ Sprint 3

| Endpoint | Method | Auth | Rate Limit | Description |
|----------|--------|------|------------|-------------|
| `/auth/google` | POST | No | 5/min | Login/register with Google OAuth |
| `/auth/google/link` | POST | Yes | - | Link Google account to existing user |
| `/auth/google/unlink` | DELETE | Yes | - | Unlink Google account |

### Login/Register with Google

**POST /api/v1/auth/google** (Public, CSRF exempt)

**Request:**
- `authorization_code` (string, required) - Google authorization code from OAuth consent screen

**Response (200 OK):**
- `access_token`, `refresh_token`, `csrf_token` - JWT tokens
- `token_type` - "bearer"
- `user` - User data (see User Object in Authentication section, includes `auth_providers` and `has_password`)
- `is_new_user` (bool) - True if user was auto-registered (frontend should redirect to "Complete Profile")
- `device_id`, `should_set_device_cookie` - Device registration info

**httpOnly Cookies set:** `access_token` (15 min), `refresh_token` (7 days), `csrf_token` (15 min), `device_id` (1 year, if new device)

### Three Login Flows

1. **Existing OAuth account** → Direct login (`is_new_user=false`)
2. **Email match (no OAuth)** → Auto-link Google account + login (`is_new_user=false`)
3. **New user** → Auto-register (no password, email verified) + login (`is_new_user=true`)

### Link/Unlink Google Account

**POST /auth/google/link** - Requires JWT auth + CSRF header (`X-CSRF-Token`)
- Links Google account to the authenticated user
- Errors if Google account already linked to another user, or user already has Google linked

**DELETE /auth/google/unlink** - Requires JWT auth + CSRF header (`X-CSRF-Token`)
- Unlinks Google account from the authenticated user
- **Guard:** Cannot unlink if user has no password (would lose only auth method)

### Error Codes

| Code | Meaning |
|------|---------|
| 400 | Invalid/expired authorization code, already linked, no Google linked |
| 401 | Not authenticated (link/unlink only) |
| 423 | Account locked (brute force protection) |
| 429 | Rate limit exceeded (login only) |

**📋 See frontend integration:** `docs/FRONTEND_INTEGRATION.md`

---

## 👤 User Management

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/users/search-autocomplete` | GET | Yes | Autocomplete search by partial name ⭐ Sprint 4 |
| `/users/search` | GET | Yes | Search users by email/name |
| `/users/profile` | PATCH | Yes | Update profile (name, surname, country) |
| `/users/security` | PATCH | Yes | Change email or password |

### Search Autocomplete ⭐ Sprint 4

**GET /api/v1/users/search-autocomplete** (Authenticated)

**Query Parameters:**
- `query` (string, required, 2-100 chars) - Partial name to search for

**Response (200 OK):**
- `users` (array, max 10 results)
  - `user_id` (string, UUID)
  - `email` (string)
  - `full_name` (string) - "first_name last_name"

**Business Rules:**
- Case-insensitive partial match on first_name or last_name
- Returns max 10 results
- Only authenticated users can search

### Search by Email/Name

**GET /users/search:**
- `query` (string, optional) - Partial search in email, first_name, last_name
- Returns array of users with basic data

### Notes

- Only authenticated users can search
- No sensitive information exposed (passwords, tokens)
- country_code can be null

**📋 See complete module:** `docs/modules/user-management.md`

---

## Role-Based Access Control (RBAC) ⭐ v2.0.0

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/users/me/roles/{competition_id}` | GET | Yes | Check roles for the authenticated user in a specific competition |

### Path Parameters

**GET /users/me/roles/{competition_id}:**
- `competition_id` (string, required, UUID format) - The ID of the competition to check roles against.

### Responses

**200 OK - Successful Response**
Returns a `UserRolesResponseDTO` object detailing the user's roles.
- `is_admin` (boolean) - True if the user is a global administrator.
- `is_creator` (boolean) - True if the user is the creator of the specified competition.
- `is_player` (boolean) - True if the user is an approved player in the specified competition.
- `competition_id` (string, UUID) - The ID of the competition for which roles were checked.

**Example:**
```json
{
  "is_admin": false,
  "is_creator": true,
  "is_player": true,
  "competition_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
}
```

**401 Unauthorized**
- The user is not authenticated (i.e., missing or invalid JWT).

**404 Not Found**
- The specified `competition_id` does not exist.

**422 Unprocessable Entity**
- The provided `competition_id` is not a valid UUID.

### Business Logic
- This endpoint provides a simple way for a frontend application to conditionally render UI elements based on the user's permissions in the context of a specific competition.
- The roles are derived dynamically at request time and are not stored in a dedicated database table, following the simplified RBAC architecture of v2.0.0.

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
- `play_mode` (enum, required: "SCRATCH" | "HANDICAP")
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

```text
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

## 📅 Rounds, Matches & Teams ⭐ Sprint 2

### Rounds & Schedule

| Endpoint | Method | Auth | Rate Limit | Description |
|----------|--------|------|------------|-------------|
| `/competitions/{id}/rounds` | POST | Creator | 10/min | Create round/session (CLOSED competition) |
| `/competitions/rounds/{id}` | PUT | Creator | 10/min | Update round details (PENDING_TEAMS/PENDING_MATCHES) |
| `/competitions/rounds/{id}` | DELETE | Creator | 10/min | Delete round + cascade matches |
| `/competitions/{id}/schedule` | GET | Auth | 20/min | Full schedule grouped by day |
| `/competitions/{id}/schedule/configure` | POST | Creator | 10/min | Configure schedule (auto/manual) |

### Matches

| Endpoint | Method | Auth | Rate Limit | Description |
|----------|--------|------|------------|-------------|
| `/competitions/matches/{id}` | GET | Auth | 20/min | Match detail with players/handicaps |
| `/competitions/matches/{id}/status` | PUT | Creator | 10/min | Start or complete match |
| `/competitions/matches/{id}/walkover` | POST | Creator | 10/min | Declare walkover |
| `/competitions/matches/{id}/players` | PUT | Creator | 10/min | Reassign players (recalculates handicaps) |
| `/competitions/rounds/{id}/matches/generate` | POST | Creator | 10/min | Generate matches for round |

### Teams

| Endpoint | Method | Auth | Rate Limit | Description |
|----------|--------|------|------------|-------------|
| `/competitions/{id}/teams` | POST | Creator | 10/min | Assign teams (snake draft or manual) |

### Round States
```text
PENDING_TEAMS → PENDING_MATCHES → SCHEDULED → IN_PROGRESS → COMPLETED
```

### Match States
```text
SCHEDULED → IN_PROGRESS → COMPLETED
                        → WALKOVER
                        → CONCEDED  ⭐ Sprint 4
```

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

```text
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

## ⛳ Golf Course Management ⭐ v2.0.1

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/golf-courses/request` | POST | Yes | Request new golf course (Creator) |
| `/golf-courses/{id}` | GET | No | Get golf course details (tees + holes) |
| `/golf-courses` | GET | No | List golf courses with filters |
| `/admin/golf-courses/pending` | GET | Yes | List pending approvals (Admin only) |
| `/admin/golf-courses/{id}/approve` | PUT | Yes | Approve golf course (Admin only) |
| `/admin/golf-courses/{id}/reject` | PUT | Yes | Reject golf course with reason (Admin only) |

### Main Fields

**Request Golf Course:**
- `name` (string, required, 3-200 chars)
- `country_code` (string, required, ISO 3166-1 alpha-2)
- `course_type` (enum, required: "STANDARD_18" | "PITCH_AND_PUTT" | "EXECUTIVE")
- `tees` (array, required, 2-10 tees)
  - `tee_category` (string, required: "CHAMPIONSHIP", "AMATEUR", "SENIOR", "FORWARD", "JUNIOR")
  - `tee_gender` (string, optional: "MALE", "FEMALE", or null)
  - `identifier` (string, required: "Amarillo", "Oro", "1", etc.)
  - `course_rating` (float, required, 50.0-90.0)
  - `slope_rating` (int, required, 55-155)
- `holes` (array, required, exactly 18 holes)
  - `hole_number` (int, required, 1-18)
  - `par` (int, required, 3-5)
  - `stroke_index` (int, required, 1-18, unique)

**Approve Golf Course:**
- `golf_course_id` (string, required, UUID)

**Reject Golf Course:**
- `golf_course_id` (string, required, UUID)
- `reason` (string, required, 10-500 chars)

### Query Parameters

**GET /golf-courses:**
- `approval_status` (string, optional) - Filter by status (PENDING_APPROVAL, APPROVED, REJECTED)
- `country_code` (string, optional) - Filter by country
- `creator_id` (string, optional) - Filter by creator

### Golf Course Response

**Structure:**
- `id` (string) - Golf course UUID
- `name` (string) - Course name
- `country_code` (string) - ISO country code
- `course_type` (string) - Type of course
- `creator_id` (string) - Creator UUID
- `tees` (array) - List of tees with WHS ratings
- `holes` (array) - List of 18 holes with par and stroke index
- `approval_status` (string) - Current approval status
- `rejection_reason` (string, nullable) - Reason for rejection if applicable
- `total_par` (int) - Computed total par (sum of all holes)
- `created_at` (datetime) - Creation timestamp
- `updated_at` (datetime) - Last update timestamp

### Approval Workflow

```text
PENDING_APPROVAL → APPROVED
                 ↓
              REJECTED
```

**States:**
- `PENDING_APPROVAL` - Awaiting admin approval after creation
- `APPROVED` - Approved by admin, available for competitions
- `REJECTED` - Rejected by admin with reason

### Business Rules

- **Creator permissions**: Any authenticated user can request a golf course
- **Admin permissions**: Only admins can approve/reject/view pending courses
- **Validation**:
  - Exactly 18 holes with unique stroke indices (1-18)
  - Total par between 66 and 76
  - 2-10 tees per course with valid WHS ratings (unique category+gender pairs)
  - Course rating: 50.0-90.0 (WHS standard)
  - Slope rating: 55-155 (WHS standard)
- **Tee categories normalized**: Uses WHS standard categories
- **Country validation**: Country code must exist in countries table
- **Immutability**: Once created, golf courses cannot be edited (re-request if needed)

### Domain Events

- `GolfCourseRequestedEvent` - Emitted when creator requests a new course
- `GolfCourseApprovedEvent` - Emitted when admin approves a course
- `GolfCourseRejectedEvent` - Emitted when admin rejects a course

**📋 See complete module:** `CLAUDE.md` (Golf Course Module section)

---

## 📨 Invitation Management ⭐ v2.0.12

| Endpoint | Method | Auth | Rate Limit | Description |
|----------|--------|------|------------|-------------|
| `/competitions/{id}/invitations` | POST | Creator | max_players/h | Invite user by ID |
| `/competitions/{id}/invitations/by-email` | POST | Creator | max_players/h | Invite user by email |
| `/invitations/me` | GET | Yes | 20/min | List my pending invitations |
| `/invitations/{id}/respond` | POST | Invitee | 10/min | Accept or decline invitation |
| `/competitions/{id}/invitations` | GET | Creator | 20/min | List all invitations for competition |

### Main Fields

**Invite by User ID:**
- `user_id` (string, required, UUID) - User to invite
- `personal_message` (string, optional, max 500)

**Invite by Email:**
- `email` (string, required, valid email) - Email of invitee
- `personal_message` (string, optional, max 500)

**Respond to Invitation:**
- `action` (enum, required: "ACCEPT" | "DECLINE")

### Invitation Response

- `id` (string, UUID) - Invitation ID
- `competition_id` (string, UUID) - Competition ID
- `competition_name` (string) - Competition name
- `inviter_name` (string) - Name of person who invited
- `invitee_email` (string) - Invitee email
- `invitee_user_id` (string, nullable) - Invitee user ID (if registered)
- `invitee_name` (string, nullable) - Invitee name (if registered)
- `status` (string) - PENDING, ACCEPTED, DECLINED, EXPIRED
- `personal_message` (string, nullable) - Personal message
- `expires_at` (datetime) - Expiration timestamp (7 days)
- `created_at` (datetime) - Creation timestamp

### Business Rules

- **Token**: 256-bit secure token, SHA256 hash stored in DB, expires in 7 days
- **Accept**: Creates enrollment with APPROVED status (bypasses approval flow)
- **Rate limiting**: max_players invitations per hour per competition
- **Bilingual emails**: ES/EN via Mailgun (fire-and-forget, failure doesn't block invitation)
- **Duplicate prevention**: Only one PENDING invitation per email per competition

### Invitation States

```text
PENDING → ACCEPTED
        → DECLINED
        → EXPIRED (automatic after 7 days)
```

---

## 🏌️ Scoring & Leaderboard ⭐ Sprint 4

| Endpoint | Method | Auth | Rate Limit | Description |
|----------|--------|------|------------|-------------|
| `/competitions/matches/{id}/scoring-view` | GET | Player | 20/min | Unified scoring view |
| `/competitions/matches/{id}/scores/holes/{n}` | POST | Player | 10/min | Submit hole score |
| `/competitions/matches/{id}/scorecard/submit` | POST | Player | 10/min | Submit scorecard |
| `/competitions/{id}/leaderboard` | GET | Yes | 20/min | Competition leaderboard |
| `/competitions/matches/{id}/concede` | PUT | Player/Creator | 10/min | Concede match |

### Get Scoring View

**GET /api/v1/competitions/matches/{match_id}/scoring-view** (Enrolled player)

Returns unified scoring data: hole-by-hole scores, validation statuses, match standing, marker assignments.

**Response (200 OK):**
- `match_id` (string, UUID)
- `round_info` (object) - Round details (format, handicap_mode, golf_course)
- `marker_assignments` (array) - Who marks whom
- `players` (array) - Player details (user_id, name, team, playing_handicap)
- `holes` (array of 18) - Per-hole data:
  - `hole_number` (int, 1-18)
  - `par` (int), `stroke_index` (int)
  - `scores` (array) - Per-player: `own_score`, `marker_score`, `own_submitted`, `marker_submitted`, `validation_status`, `net_score`, `strokes_received`
  - `result` (object) - Hole winner ("A"/"B"/"HALVED")
- `standing` (object) - `leading_team`, `holes_up`, `holes_played`, `holes_remaining`, `is_decided`
- `decided_result` (object, nullable) - `winner`, `score` (e.g., "3&2")
- `scorecards_submitted` (array) - User IDs that have submitted

### Submit Hole Score

**POST /api/v1/competitions/matches/{match_id}/scores/holes/{hole_number}** (Match player)

**Request:**
- `own_score` (int | null, 1-9 or null for picked up)
- `marked_player_id` (string, UUID) - The player being marked
- `marked_score` (int | null, 1-9 or null for picked up)

**Response (200 OK):** Returns full scoring-view (same as GET scoring-view).

**Business Rules:**
- Match must be IN_PROGRESS
- Scorer must be a player in the match
- `marked_player_id` must match marker assignments
- **Foursomes**: Any team player can submit (last write wins), affects both team members
- **Dual validation**: own_score → own_submitted, marked_score → marker_submitted
- **Auto-recalculation**: validation_status, net_score, standing, is_decided
- **Scorecard locking** (granular, silently skipped — no error):
  - If scorer submitted scorecard → `own_score` ignored, `marked_score` still processed
  - If marked player submitted scorecard → `marked_score` ignored, `own_score` still processed

### Submit Scorecard

**POST /api/v1/competitions/matches/{match_id}/scorecard/submit** (Match player)

**Response (200 OK):**
- `match_id` (string, UUID)
- `submitted_by` (string, UUID)
- `all_submitted` (bool) - True if all players have submitted
- `match_completed` (bool) - True if match auto-completed
- `result` (object, nullable) - Final match result

**Business Rules:**
- Match must be IN_PROGRESS
- All played holes must have `validation_status == MATCH`
- Each player submits once (no duplicates)
- When all players submit → match auto-completes with calculated result
- If all matches in round completed → round auto-completes

### Get Leaderboard

**GET /api/v1/competitions/{competition_id}/leaderboard** (Any authenticated user)

**Response (200 OK):**
- `competition_id` (string, UUID)
- `team_a` (object) - `name`, `points` (float)
- `team_b` (object) - `name`, `points` (float)
- `matches` (array) - Per match: `match_id`, `round_name`, `format`, `status`, `team_a_players`, `team_b_players`, `standing`, `result`, `points_a`, `points_b`

**Ryder Cup Points:**
- Win: 1.0 point
- Halved: 0.5 points each
- Loss: 0.0 points
- IN_PROGRESS matches: show live standing (no points yet)

### Concede Match

**PUT /api/v1/competitions/matches/{match_id}/concede** (Match player or Creator)

**Request:**
- `conceding_team` (string, required: "A" or "B")
- `reason` (string, optional)

**Authorization:**
- **Match players**: Can only concede their **own team**
- **Competition creator**: Can concede **any team**

**Business Rules:**
- Match must be IN_PROGRESS
- Sets match status to CONCEDED
- Auto-completes round if all matches finished

### Validation Status Flow

```text
PENDING → MATCH    (own_score == marker_score, including null==null)
        → MISMATCH (own_score != marker_score, including null vs number)
```

Both `own_submitted` AND `marker_submitted` must be true before validation resolves.

---

## 📨 Support ⭐ v2.0.8

| Endpoint | Method | Auth | Rate Limit | Description |
|----------|--------|------|------------|-------------|
| `/support/contact` | POST | No | 3/hour | Submit contact form (creates GitHub Issue) |

### Main Fields

**Contact Request:**
- `name` (string, required, 2-100 chars)
- `email` (string, required, valid email)
- `category` (enum, required: "BUG", "FEATURE", "QUESTION", "OTHER")
- `subject` (string, required, 3-200 chars)
- `message` (string, required, 10-5000 chars)

**Contact Response:**
- `message` (string) - Confirmation message

### Category → GitHub Label Mapping

| Category | GitHub Label |
|----------|-------------|
| BUG | `bug` |
| FEATURE | `enhancement` |
| QUESTION | `question` |
| OTHER | `other` |

### Business Rules

- **Public endpoint**: No authentication required
- **CSRF exempt**: No session to protect
- **Rate limited**: 3 requests/hour per IP (SlowAPI)
- **Input sanitization**: All fields sanitized via `sanitize_html()` before creating issue
- **GitHub Integration**: Creates issues in configured repo via REST API (`GH_ISSUES_TOKEN` + `GITHUB_ISSUES_REPO`)
- **Error handling**: Returns 502 Bad Gateway if GitHub API fails

### Architecture (Clean Architecture)

- **Domain**: `ContactCategory` value object (StrEnum with `to_github_label()`)
- **Application**: `SubmitContactUseCase` + `IGitHubIssueService` port + `ContactRequestDTO`/`ContactResponseDTO`
- **Infrastructure**: `GitHubIssueService` adapter (GitHub REST API) + `support_routes.py`

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
| POST /support/contact | 3/hour | Anti contact form spam |

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

**Last Updated:** 24 February 2026
**Version:** Sprint 4 (Live Scoring + Leaderboard — 80 endpoints)
