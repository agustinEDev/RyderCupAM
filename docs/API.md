# 🌐 API Reference

**Base URL**: `http://localhost:8000`
**Docs**: `/docs` (Swagger UI)
**Total Endpoints**: 32 active
**Version**: v1.6.4
**Last Updated**: 22 Nov 2025

## Quick Reference

```
Authentication (6 endpoints)
├── POST /api/v1/auth/register           # User registration
├── POST /api/v1/auth/login              # JWT authentication
├── GET  /api/v1/auth/current-user       # Get authenticated user info
├── POST /api/v1/auth/logout             # Session logout
├── POST /api/v1/auth/verify-email       # Email verification
└── POST /api/v1/auth/resend-verification # Resend verification email

User Management (3 endpoints)
├── GET   /api/v1/users/search           # Search users by email/name
├── PATCH /api/v1/users/profile          # Update profile (name/surname)
└── PATCH /api/v1/users/security         # Update security (email/password)

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

## Authentication

### Register User
```http
POST /api/v1/auth/register

Request:
{
  "first_name": "John",
  "last_name": "Doe",
  "email": "john@example.com",
  "password": "SecurePass123!"
}

Response: 201 Created
{
  "id": "uuid",
  "email": "john@example.com",
  "first_name": "John",
  "last_name": "Doe",
  "handicap": null,
  "email_verified": false,
  "created_at": "2025-11-09T10:00:00Z",
  "updated_at": "2025-11-09T10:00:00Z"
}

Notes:
- A verification email is automatically sent to the user's email
- The user must verify their email by clicking the link in the email
- email_verified will be false until verification is completed
```

### Login User
```http
POST /api/v1/auth/login

Request:
{
  "email": "john@example.com",
  "password": "SecurePass123!"
}

Response: 200 OK
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "user": {
    "id": "uuid",
    "email": "john@example.com",
    "first_name": "John",
    "last_name": "Doe",
    "handicap": 15.5,
    "email_verified": true,
    "created_at": "2025-11-09T10:00:00Z",
    "updated_at": "2025-11-09T10:00:00Z"
  }
}

Errors:
401 Unauthorized - Invalid credentials
```

### Get Current User
```http
GET /api/v1/auth/current-user
Authorization: Bearer {token}

Response: 200 OK
{
  "id": "uuid",
  "email": "john@example.com",
  "first_name": "John",
  "last_name": "Doe",
  "handicap": 15.5,
  "email_verified": true,
  "created_at": "2025-11-09T10:00:00Z",
  "updated_at": "2025-11-09T10:00:00Z"
}

Errors:
401 Unauthorized - Invalid or missing token
```

### Logout User
```http
POST /api/v1/auth/logout
Authorization: Bearer {token}

Request:
{
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."  // Optional
}

Response: 200 OK
{
  "message": "Logout exitoso",
  "logged_out_at": "2025-11-09T10:00:00Z"
}

Errors:
401 Unauthorized - Invalid or missing token
404 Not Found - User not found
```

### Verify Email
```http
POST /api/v1/auth/verify-email

Request:
{
  "token": "verification-token-from-email"
}

Response: 200 OK
{
  "message": "Email verificado exitosamente",
  "email_verified": true
}

Errors:
400 Bad Request - Token inválido o no encontrado

Notes:
- Los tokens no expiran actualmente (sin TTL implementado)
- El email enviado es bilingüe (Español/Inglés)
- El usuario puede usar la app sin verificar, pero algunas funcionalidades estarán limitadas en el futuro
```

### Resend Verification Email
```http
POST /api/v1/auth/resend-verification

Request:
{
  "email": "john@example.com"
}

Response: 200 OK
{
  "message": "Email de verificación reenviado exitosamente"
}

Notes:
- Siempre retorna 200 OK con mensaje genérico (independiente del resultado)
- No revela si el email existe en el sistema (previene user enumeration)
- No revela si el email ya está verificado
```

## User Management

### Search Users
```http
GET /api/v1/users/search?email=john@example.com&full_name=John%20Doe
Authorization: Bearer {token}

Response: 200 OK
{
  "id": "uuid",
  "email": "john@example.com",
  "first_name": "John",
  "last_name": "Doe"
}

Errors:
400 Bad Request - At least one search parameter required
```

### Update Profile
```http
PATCH /api/v1/users/profile
Authorization: Bearer {token}

Request:
{
  "first_name": "John",
  "last_name": "Doe"
}

Response: 200 OK
{
  "id": "uuid",
  "email": "john@example.com",
  "first_name": "John",
  "last_name": "Doe",
  "handicap": 15.5,
  "email_verified": true,
  "created_at": "2025-11-09T10:00:00Z",
  "updated_at": "2025-11-09T10:00:00Z"
}

Errors:
400 Bad Request - Validation error
401 Unauthorized - Invalid token
```

### Update Security
```http
PATCH /api/v1/users/security
Authorization: Bearer {token}

Request:
{
  "current_password": "OldPass123!",
  "new_email": "newemail@example.com",
  "new_password": "NewSecurePass123!",
  "confirm_password": "NewSecurePass123!"
}

Response: 200 OK
{
  "id": "uuid",
  "email": "newemail@example.com",
  "first_name": "John",
  "last_name": "Doe",
  "handicap": 15.5,
  "email_verified": false,
  "created_at": "2025-11-09T10:00:00Z",
  "updated_at": "2025-11-09T10:00:00Z"
}

Notes:
- current_password is always required
- At least one of new_email or new_password must be provided
- If changing password, confirm_password must match new_password
- Email verification will be required for new email addresses
```

## Handicap Management

### Update Handicap (RFEG)
```http
POST /api/v1/handicaps/update
Authorization: Bearer {token}

Request:
{
  "user_email": "john@example.com",
  "manual_handicap": 15.5  // Optional fallback
}

Response: 200 OK
{
  "id": "uuid",
  "email": "john@example.com",
  "first_name": "John",
  "last_name": "Doe",
  "handicap": 15.5,
  "email_verified": true,
  "created_at": "2025-11-09T10:00:00Z",
  "updated_at": "2025-11-09T10:00:00Z"
}

Notes:
- Queries RFEG for current handicap
- If user not found in RFEG and manual_handicap provided, uses manual value
- If user not found in RFEG and no manual_handicap, returns error
```

### Update Multiple Handicaps
```http
POST /api/v1/handicaps/update-multiple
Authorization: Bearer {token}

Request:
{
  "user_emails": ["john@example.com", "jane@example.com"]
}

Response: 200 OK
{
  "updated_users": [
    {
      "id": "uuid",
      "email": "john@example.com",
      "first_name": "John",
      "last_name": "Doe",
      "handicap": 15.5
    }
  ],
  "failed_updates": [
    {
      "email": "jane@example.com",
      "error": "User not found in RFEG"
    }
  ]
}
```

### Update Handicap Manually
```http
POST /api/v1/handicaps/update-manual
Authorization: Bearer {token}

Request:
{
  "user_email": "john@example.com",
  "handicap": 15.5
}

Response: 200 OK
{
  "id": "uuid",
  "email": "john@example.com",
  "first_name": "John",
  "last_name": "Doe",
  "handicap": 15.5,
  "email_verified": true,
  "created_at": "2025-11-09T10:00:00Z",
  "updated_at": "2025-11-09T10:00:00Z"
}

Notes:
- Does NOT query RFEG, directly sets the provided handicap value
- Useful for administrators or non-federated players
```

## Competition Management

### Create Competition
```http
POST /api/v1/competitions
Authorization: Bearer {token}

Request:
{
  "name": "Ryder Cup 2025",
  "start_date": "2025-10-01",
  "end_date": "2025-10-03",
  "main_country": "ES",
  "adjacent_country_1": "FR",
  "adjacent_country_2": "PT",
  "handicap_type": "PERCENTAGE",
  "handicap_percentage": 95,
  "max_players": 24,
  "team_assignment": "MANUAL"
}

Alternative Request Format (Frontend Compatible):
{
  "name": "Ryder Cup 2025",
  "start_date": "2025-10-01",
  "end_date": "2025-10-03",
  "main_country": "ES",
  "countries": ["FR", "PT"],
  "handicap_type": "PERCENTAGE",
  "handicap_percentage": 95,
  "number_of_players": 24,
  "team_assignment": "manual"
}

Response: 201 Created
{
  "id": "uuid",
  "creator_id": "uuid",
  "name": "Ryder Cup 2025",
  "status": "DRAFT",
  "start_date": "2025-10-01",
  "end_date": "2025-10-03",
  "country_code": "ES",
  "secondary_country_code": "FR",
  "tertiary_country_code": "PT",
  "location": "Spain, France, Portugal",
  "countries": [
    {
      "code": "ES",
      "name_en": "Spain",
      "name_es": "España"
    },
    {
      "code": "FR",
      "name_en": "France",
      "name_es": "Francia"
    },
    {
      "code": "PT",
      "name_en": "Portugal",
      "name_es": "Portugal"
    }
  ],
  "handicap_type": "PERCENTAGE",
  "handicap_percentage": 95,
  "max_players": 24,
  "team_assignment": "MANUAL",
  "is_creator": true,
  "enrolled_count": 0,
  "created_at": "2025-11-19T10:00:00.000Z",
  "updated_at": "2025-11-19T10:00:00.000Z"
}

Notes:
- Competition is created in DRAFT state.
- Only the creator can modify a DRAFT competition.
- The API accepts both legacy format (adjacent_country_1/2) and frontend format (countries array, number_of_players alias).
- Countries are automatically validated for existence and adjacency.
```

### List Competitions
```http
GET /api/v1/competitions?status=DRAFT&limit=10&offset=0
Authorization: Bearer {token}

Response: 200 OK
[
  {
    "id": "uuid",
    "creator_id": "uuid",
    "name": "Ryder Cup 2025",
    "status": "DRAFT",
    "start_date": "2025-12-01",
    "end_date": "2025-12-03",
    "country_code": "ES",
    "secondary_country_code": "FR",
    "tertiary_country_code": "PT",
    "location": "Spain, France, Portugal",
    "countries": [
      {
        "code": "ES",
        "name_en": "Spain",
        "name_es": "España"
      },
      {
        "code": "FR",
        "name_en": "France",
        "name_es": "Francia"
      },
      {
        "code": "PT",
        "name_en": "Portugal",
        "name_es": "Portugal"
      }
    ],
    "handicap_type": "PERCENTAGE",
    "handicap_percentage": 95,
    "max_players": 24,
    "team_assignment": "MANUAL",
    "is_creator": false,
    "enrolled_count": 0,
    "created_at": "2025-11-09T10:00:00Z",
    "updated_at": "2025-11-09T10:00:00Z"
  }
]

Query Parameters:
- status: Filter by competition status (DRAFT, ACTIVE, CLOSED, IN_PROGRESS, COMPLETED, CANCELLED)
- limit: Maximum number of results (default: 50)
- offset: Pagination offset (default: 0)
```

### Get Competition
```http
GET /api/v1/competitions/{competition_id}
Authorization: Bearer {token}

Response: 200 OK
{
  "id": "uuid",
  "creator_id": "uuid",
  "name": "Ryder Cup 2025",
  "status": "DRAFT",
  "start_date": "2025-12-01",
  "end_date": "2025-12-03",
  "country_code": "ES",
  "secondary_country_code": "FR",
  "tertiary_country_code": "PT",
  "location": "Spain, France, Portugal",
  "countries": [
    {
      "code": "ES",
      "name_en": "Spain",
      "name_es": "España"
    },
    {
      "code": "FR",
      "name_en": "France",
      "name_es": "Francia"
    },
    {
      "code": "PT",
      "name_en": "Portugal",
      "name_es": "Portugal"
    }
  ],
  "handicap_type": "PERCENTAGE",
  "handicap_percentage": 95,
  "max_players": 24,
  "team_assignment": "MANUAL",
  "is_creator": false,
  "enrolled_count": 0,
  "created_at": "2025-11-09T10:00:00Z",
  "updated_at": "2025-11-09T10:00:00Z"
}
```

### Update Competition
```http
PUT /api/v1/competitions/{competition_id}
Authorization: Bearer {token}

Request:
{
  "name": "Updated Ryder Cup 2025",
  "start_date": "2025-12-01",
  "end_date": "2025-12-03",
  "main_country": "ES",
  "adjacent_country_1": "FR",
  "adjacent_country_2": "PT",
  "handicap_type": "PERCENTAGE",
  "handicap_percentage": 95,
  "max_players": 20,
  "team_assignment": "MANUAL"
}

Response: 200 OK
{
  "id": "uuid",
  "creator_id": "uuid",
  "name": "Updated Ryder Cup 2025",
  "status": "DRAFT",
  "start_date": "2025-12-01",
  "end_date": "2025-12-03",
  "country_code": "ES",
  "secondary_country_code": "FR",
  "tertiary_country_code": "PT",
  "location": "Spain, France, Portugal",
  "countries": [
    {
      "code": "ES",
      "name_en": "Spain",
      "name_es": "España"
    },
    {
      "code": "FR",
      "name_en": "France",
      "name_es": "Francia"
    },
    {
      "code": "PT",
      "name_en": "Portugal",
      "name_es": "Portugal"
    }
  ],
  "handicap_type": "PERCENTAGE",
  "handicap_percentage": 95,
  "max_players": 20,
  "team_assignment": "MANUAL",
  "is_creator": true,
  "enrolled_count": 0,
  "created_at": "2025-11-09T10:00:00Z",
  "updated_at": "2025-11-09T10:00:00Z"
}

Notes:
- Only competitions in DRAFT status can be updated
- Only the creator can update the competition
- Updatable fields: name, dates, countries, handicap settings, max_players, team_assignment
```

### Delete Competition
```http
DELETE /api/v1/competitions/{competition_id}
Authorization: Bearer {token}

Response: 204 No Content

Notes:
- Only competitions in DRAFT status can be deleted
- Only the creator can delete the competition
- Physical deletion (not soft delete)
```

### State Transitions

#### Activate Competition (DRAFT → ACTIVE)
```http
POST /api/v1/competitions/{competition_id}/activate
Authorization: Bearer {token}

Response: 200 OK
{
  "id": "uuid",
  "name": "Ryder Cup 2025",
  "status": "ACTIVE",
  "updated_at": "2025-11-09T10:00:00Z"
}

Notes:
- Opens competition for enrollments
- Only creator can activate
- Competition must be in DRAFT status
```

#### Close Enrollments (ACTIVE → CLOSED)
```http
POST /api/v1/competitions/{competition_id}/close-enrollments
Authorization: Bearer {token}

Response: 200 OK
{
  "id": "uuid",
  "name": "Ryder Cup 2025",
  "status": "CLOSED",
  "updated_at": "2025-11-09T10:00:00Z"
}

Notes:
- Closes enrollment period
- Only creator can close enrollments
- Competition must be in ACTIVE status
```

#### Start Competition (CLOSED → IN_PROGRESS)
```http
POST /api/v1/competitions/{competition_id}/start
Authorization: Bearer {token}

Response: 200 OK
{
  "id": "uuid",
  "name": "Ryder Cup 2025",
  "status": "IN_PROGRESS",
  "updated_at": "2025-11-09T10:00:00Z"
}

Notes:
- Begins the tournament
- Only creator can start
- Competition must be in CLOSED status
```

#### Complete Competition (IN_PROGRESS → COMPLETED)
```http
POST /api/v1/competitions/{competition_id}/complete
Authorization: Bearer {token}

Response: 200 OK
{
  "id": "uuid",
  "name": "Ryder Cup 2025",
  "status": "COMPLETED",
  "updated_at": "2025-11-09T10:00:00Z"
}

Notes:
- Finalizes the tournament
- Only creator can complete
- Competition must be in IN_PROGRESS status
```

#### Cancel Competition (Any State → CANCELLED)
```http
POST /api/v1/competitions/{competition_id}/cancel
Authorization: Bearer {token}

Response: 200 OK
{
  "id": "uuid",
  "name": "Ryder Cup 2025",
  "status": "CANCELLED",
  "updated_at": "2025-11-09T10:00:00Z"
}

Notes:
- Can be called from any status
- Only creator can cancel
- Competition becomes permanently cancelled
```

## Enrollment Management

### Request Enrollment
```http
POST /api/v1/competitions/{competition_id}/enrollments
Authorization: Bearer {token}

Response: 201 Created
{
  "id": "uuid",
  "competition_id": "uuid",
  "user_id": "uuid",
  "status": "REQUESTED",
  "custom_handicap": null,
  "created_at": "2025-11-09T10:00:00Z",
  "updated_at": "2025-11-09T10:00:00Z"
}

Notes:
- Current user enrolls themselves
- Status starts as REQUESTED
- Creator approval may be required
```

### Direct Enroll Player
```http
POST /api/v1/competitions/{competition_id}/enrollments/direct
Authorization: Bearer {token}

Request:
{
  "user_email": "john@example.com"
}

Response: 201 Created
{
  "id": "uuid",
  "competition_id": "uuid",
  "user_id": "uuid",
  "status": "APPROVED",
  "custom_handicap": null,
  "created_at": "2025-11-09T10:00:00Z",
  "updated_at": "2025-11-09T10:00:00Z"
}

Notes:
- Only competition creator can use this endpoint
- Player is directly approved (status: APPROVED)
- Bypasses the approval process
```

### List Enrollments
```http
GET /api/v1/competitions/{competition_id}/enrollments?status=APPROVED
Authorization: Bearer {token}

Response: 200 OK
[
  {
    "id": "uuid",
    "competition_id": "uuid",
    "user": {
      "id": "uuid",
      "email": "john@example.com",
      "first_name": "John",
      "last_name": "Doe",
      "handicap": 15.5
    },
    "status": "APPROVED",
    "custom_handicap": null,
    "created_at": "2025-11-09T10:00:00Z",
    "updated_at": "2025-11-09T10:00:00Z"
  }
]

Query Parameters:
- status: Filter by enrollment status (REQUESTED, APPROVED, REJECTED, CANCELLED, WITHDRAWN)
```

### Approve Enrollment
```http
POST /api/v1/enrollments/{enrollment_id}/approve
Authorization: Bearer {token}

Response: 200 OK
{
  "id": "uuid",
  "competition_id": "uuid",
  "user_id": "uuid",
  "status": "APPROVED",
  "updated_at": "2025-11-09T10:00:00Z"
}

Notes:
- Only competition creator can approve
- Changes status from REQUESTED to APPROVED
```

### Reject Enrollment
```http
POST /api/v1/enrollments/{enrollment_id}/reject
Authorization: Bearer {token}

Response: 200 OK
{
  "id": "uuid",
  "competition_id": "uuid",
  "user_id": "uuid",
  "status": "REJECTED",
  "updated_at": "2025-11-09T10:00:00Z"
}

Notes:
- Only competition creator can reject
- Changes status from REQUESTED to REJECTED
```

### Cancel Enrollment
```http
POST /api/v1/enrollments/{enrollment_id}/cancel?reason=Cannot%20attend
Authorization: Bearer {token}

Response: 200 OK
{
  "id": "uuid",
  "competition_id": "uuid",
  "user_id": "uuid",
  "status": "CANCELLED",
  "updated_at": "2025-11-09T10:00:00Z"
}

Notes:
- Only enrollment owner can cancel
- Valid from REQUESTED or INVITED status
- Optional reason parameter
```

### Withdraw from Competition
```http
POST /api/v1/enrollments/{enrollment_id}/withdraw?reason=Injury
Authorization: Bearer {token}

Response: 200 OK
{
  "id": "uuid",
  "competition_id": "uuid",
  "user_id": "uuid",
  "status": "WITHDRAWN",
  "updated_at": "2025-11-09T10:00:00Z"
}

Notes:
- Only enrollment owner can withdraw
- Valid only from APPROVED status
- Optional reason parameter
```

### Set Custom Handicap
```http
PUT /api/v1/enrollments/{enrollment_id}/handicap
Authorization: Bearer {token}

Request:
{
  "custom_handicap": 18.5
}

Response: 200 OK
{
  "id": "uuid",
  "competition_id": "uuid",
  "user_id": "uuid",
  "status": "APPROVED",
  "custom_handicap": 18.5,
  "updated_at": "2025-11-09T10:00:00Z"
}

Notes:
- Only competition creator can set custom handicaps
- Value must be between -10.0 and 54.0
- Overrides the player's default handicap for this competition
```

## Country Management

### List Countries
```http
GET /api/v1/countries?language=en

Response: 200 OK
[
  {
    "code": "ES",
    "name": "Spain",
    "flag": "🇪🇸"
  },
  {
    "code": "FR",
    "name": "France",
    "flag": "🇫🇷"
  }
]

Query Parameters:
- language: Language for sorting (en/es, default: en)
```

### List Adjacent Countries
```http
GET /api/v1/countries/{country_code}/adjacent

Response: 200 OK
[
  {
    "code": "FR",
    "name": "France",
    "flag": "🇫🇷"
  },
  {
    "code": "PT",
    "name": "Portugal",
    "flag": "🇵🇹"
  }
]

Notes:
- Returns countries that share borders with the specified country
- Used for populating secondary/tertiary country selectors in competition forms
```

## Using Authenticated Endpoints
```http
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

## Error Codes

- `400`: Bad Request (validation errors)
- `401`: Unauthorized (invalid credentials or missing token)
- `403`: Forbidden (insufficient permissions)
- `404`: Not Found (resource doesn't exist)
- `409`: Conflict (duplicate email, invalid state transition, etc.)
- `422`: Unprocessable Entity (Pydantic validation: invalid email format, etc.)
- `503`: Service Unavailable (external service down, e.g., RFEG API)
- `500`: Internal Server Error

## Session Management

**Current Implementation**: Phase 1 - Client-side logout
- JWT tokens remain valid until expiration (24h)
- Client should remove token locally on logout
- Server registers logout events for auditing

**Future Implementation**: Phase 2 - Token blacklist
- Immediate token invalidation
- "Logout from all devices" functionality
- See [ADR-015](architecture/decisions/ADR-015-session-management-progressive-strategy.md)

## Authentication

### Register User
```http
POST /api/v1/auth/register

Request:
{
  "first_name": "John",
  "last_name": "Doe",
  "email": "john@example.com",
  "password": "SecurePass123!"
}

Response: 201 Created
{
  "id": "uuid",
  "email": "john@example.com",
  "first_name": "John",
  "last_name": "Doe",
  "handicap": null,
  "email_verified": false,
  "created_at": "2025-11-09T10:00:00Z",
  "updated_at": "2025-11-09T10:00:00Z"
}

Notes:
- A verification email is automatically sent to the user's email
- The user must verify their email by clicking the link in the email
- email_verified will be false until verification is completed
```

### Login User
```http
POST /api/v1/auth/login

Request:
{
  "email": "john@example.com",
  "password": "SecurePass123!"
}

Response: 200 OK
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "user": {
    "id": "uuid",
    "email": "john@example.com",
    "first_name": "John",
    "last_name": "Doe",
    "handicap": 15.5,
    "email_verified": true,
    "created_at": "2025-11-09T10:00:00Z",
    "updated_at": "2025-11-09T10:00:00Z"
  }
}

Errors:
401 Unauthorized - Invalid credentials
```

### Logout User
```http
POST /api/v1/auth/logout
Authorization: Bearer {token}

Request:
{
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."  // Optional
}

Response: 200 OK
{
  "message": "Logout exitoso",
  "logged_out_at": "2025-11-09T10:00:00Z"
}

Errors:
401 Unauthorized - Invalid or missing token
404 Not Found - User not found
```

### Verify Email
```http
POST /api/v1/auth/verify-email

Request:
{
  "token": "verification-token-from-email"
}

Response: 200 OK
{
  "message": "Email verificado exitosamente",
  "email_verified": true
}

Errors:
400 Bad Request - Token inválido o no encontrado

Notes:
- Los tokens no expiran actualmente (sin TTL implementado)
- El email enviado es bilingüe (Español/Inglés)
- El usuario puede usar la app sin verificar, pero algunas funcionalidades estarán limitadas en el futuro
```

**Flow:**
1. User registers → Receives verification email
2. User clicks link in email → Frontend extracts token from URL
3. Frontend calls this endpoint with token → Email verified

**Link format**: `{FRONTEND_URL}/verify-email?token={token}`

### Using Authenticated Endpoints
```http
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

## Handicap Management

### Update Handicap (RFEG)
```http
POST /api/v1/handicaps/update
Authorization: Bearer {token}

Request:
{
  "user_id": "uuid",
  "manual_handicap": 15.5  // Optional fallback if RFEG returns no data
}

Response: 200 OK
{
  "id": "uuid",
  "handicap": 15.5,
  "handicap_updated_at": "2025-11-09T10:00:00Z",
  ...
}

Errors:
404 Not Found - User not found OR Player not found in RFEG (without manual_handicap)
503 Service Unavailable - RFEG service is down
```

**Behavior:**
- Searches player in RFEG database by full name
- If found: Updates handicap with RFEG value
- If NOT found and `manual_handicap` provided: Uses manual value
- If NOT found and NO `manual_handicap`: Returns 404 with clear error message

### Update Handicap (Manual)
```http
POST /api/v1/handicaps/update-manual

Request:
{
  "user_id": "uuid",
  "handicap": 15.5
}
```

### Batch Update
```http
POST /api/v1/handicaps/update-multiple

Request:
{
  "user_ids": ["uuid1", "uuid2", ...]
}

Response: 200 OK
{
  "total": 10,
  "updated": 7,
  "not_found": 1,
  "no_handicap_found": 1,
  "errors": 1
}
```

## Handicap Management

### Update Handicap (RFEG)
```http
POST /api/v1/handicaps/update
Authorization: Bearer {token}

Request:
{
  "user_id": "uuid",
  "manual_handicap": 15.5  // Optional fallback if RFEG returns no data
}

Response: 200 OK
{
  "id": "uuid",
  "handicap": 15.5,
  "handicap_updated_at": "2025-11-09T10:00:00Z",
  ...
}

Errors:
404 Not Found - User not found OR Player not found in RFEG (without manual_handicap)
503 Service Unavailable - RFEG service is down
```

**Behavior:**
- Searches player in RFEG database by full name
- If found: Updates handicap with RFEG value
- If NOT found and `manual_handicap` provided: Uses manual value
- If NOT found and NO `manual_handicap`: Returns 404 with clear error message

### Update Handicap (Manual)
```http
POST /api/v1/handicaps/update-manual

Request:
{
  "user_id": "uuid",
  "handicap": 15.5
}
```

### Batch Update
```http
POST /api/v1/handicaps/update-multiple

Request:
{
  "user_ids": ["uuid1", "uuid2", ...]
}

Response: 200 OK
{
  "total": 10,
  "updated": 7,
  "not_found": 1,
  "no_handicap_found": 1,
  "errors": 1
}
```

## Competition Management

### Create Competition
```http
POST /api/v1/competitions
Authorization: Bearer {token}

Request:
{
  "name": "Ryder Cup 2025",
  "start_date": "2025-10-01",
  "end_date": "2025-10-03",
  "main_country": "ES",
  "adjacent_country_1": "FR",
  "handicap_type": "PERCENTAGE",
  "handicap_percentage": 95,
  "max_players": 24,
  "team_assignment": "MANUAL"
}

Response: 201 Created
{
  "id": "uuid",
  "creator_id": "uuid",
  "name": "Ryder Cup 2025",
  "status": "DRAFT",
  "start_date": "2025-10-01",
  "end_date": "2025-10-03",
  "country_code": "ES",
  "secondary_country_code": "FR",
  "tertiary_country_code": null,
  "location": "Spain, France",
  "handicap_type": "PERCENTAGE",
  "handicap_percentage": 95,
  "max_players": 24,
  "team_assignment": "MANUAL",
  "is_creator": true,
  "enrolled_count": 0,
  "created_at": "2025-11-19T10:00:00.000Z",
  "updated_at": "2025-11-19T10:00:00.000Z"
}

Notes:
- Competition is created in DRAFT state.
- Only the creator can modify a DRAFT competition.
```

### Update Competition
```http
PUT /api/v1/competitions/{competition_id}
Authorization: Bearer {token}

Request:
{
  "name": "Updated Ryder Cup Name",
  "start_date": "2026-01-01",
  "end_date": "2026-01-03",
  "main_country": "US",
  "adjacent_country_1": null,
  "adjacent_country_2": null,
  "handicap_type": "SCRATCH",
  "handicap_percentage": null,
  "max_players": 50,
  "team_assignment": "AUTOMATIC",
  "team_1_name": "Team USA",
  "team_2_name": "Team World"
}

Response: 200 OK
{
  "id": "uuid",
  "creator_id": "uuid",
  "name": "Updated Ryder Cup Name",
  "status": "DRAFT",
  "start_date": "2026-01-01",
  "end_date": "2026-01-03",
  "country_code": "US",
  "secondary_country_code": null,
  "tertiary_country_code": null,
  "location": "United States",
  "handicap_type": "SCRATCH",
  "handicap_percentage": null,
  "max_players": 50,
  "team_assignment": "AUTOMATIC",
  "is_creator": true,
  "enrolled_count": 0,
  "created_at": "2025-11-19T10:00:00.000Z",
  "updated_at": "2025-11-19T10:00:00.000Z"
}

Notes:
- Only DRAFT competitions can be updated.
- Only the creator can update the competition.
- All fields in the request body are optional for partial updates.
- If updating dates, both `start_date` and `end_date` must be provided.
- If updating `handicap_type` to PERCENTAGE, `handicap_percentage` is required. If to SCRATCH, `handicap_percentage` must be null.
```

## User Management

### Update Profile
```http
PATCH /api/v1/users/profile
Authorization: Bearer {token}

Request:
{
  "first_name": "Jane",      // Optional - only if changing
  "last_name": "Smith"        // Optional - only if changing
}

Response: 200 OK
{
  "user": {
    "id": "uuid",
    "email": "john@example.com",
    "first_name": "Jane",
    "last_name": "Smith",
    "handicap": 15.5
  },
  "message": "Profile updated successfully"
}

Errors:
401 Unauthorized - Missing or invalid token
404 Not Found - User not found
422 Unprocessable Entity - Validation error (name too short)
```

### Update Security Settings
```http
PATCH /api/v1/users/security
Authorization: Bearer {token}

Request:
{
  "current_password": "OldPass123!",     // Required
  "new_email": "newemail@example.com",   // Optional - only if changing email
  "new_password": "NewPass456!",         // Optional - only if changing password
  "confirm_password": "NewPass456!"      // Required if new_password provided
}

Response: 200 OK
{
  "user": {
    "id": "uuid",
    "email": "newemail@example.com",
    "first_name": "Jane",
    "last_name": "Smith",
    "handicap": 15.5,
    "email_verified": false  // Will be false if email was changed
  },
  "message": "Security settings updated successfully"
}

Errors:
401 Unauthorized - Missing or invalid token / Current password incorrect
404 Not Found - User not found
409 Conflict - Email already in use
422 Unprocessable Entity - Validation error (password too short, etc.)
```

**Notes:**
- **Profile Update**: Does NOT require password - only JWT authentication
- **Security Update**: Requires current password for verification
- **Email Change**: When email is updated:
  - `email_verified` is set to `false`
  - Verification email is sent to the NEW email address
  - User must verify the new email to restore full access
  - Frontend will show verification banner until email is verified
- Both endpoints can update single or multiple fields
- Leave fields as `null` or omit them to keep current values

### Find User
```http
GET /api/v1/users/search?email=john@example.com
GET /api/v1/users/search?full_name=John Doe
Authorization: Bearer {token}

Response: 200 OK
{
  "id": "uuid",
  "email": "john@example.com",
  "first_name": "John",
  "last_name": "Doe",
  "handicap": 15.5
}

Errors:
401 Unauthorized - Missing or invalid token
404 Not Found - User not found
```

## Error Codes

- `400`: Bad Request (validación)
- `401`: Unauthorized (credenciales inválidas o token missing)
- `404`: Not Found (usuario no existe, jugador no en RFEG, etc.)
- `409`: Conflict (email duplicado)
- `422`: Unprocessable Entity (validación Pydantic: formato email inválido, password muy corto, etc.)
- `503`: Service Unavailable (servicio externo RFEG caído)
- `500`: Internal Server Error

## Session Management

**Current Implementation**: Phase 1 - Client-side logout
- JWT tokens remain valid until expiration (24h)
- Client should remove token locally on logout
- Server registers logout events for auditing

**Future Implementation**: Phase 2 - Token blacklist
- Immediate token invalidation
- "Logout from all devices" functionality
- See [ADR-015](architecture/decisions/ADR-015-session-management-progressive-strategy.md)
