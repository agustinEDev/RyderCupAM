# 🌐 API Reference

**Base URL**: `http://localhost:8000`
**Docs**: `/docs` (Swagger UI)
**Total Endpoints**: 10 active

## Quick Reference

```
Authentication
├── POST /api/v1/auth/register       # User registration
├── POST /api/v1/auth/login          # JWT authentication
├── POST /api/v1/auth/verify-email   # Email verification
└── POST /api/v1/auth/logout         # Session logout

User Profile Management
├── PATCH /api/v1/users/profile    # Update name/surname (no password required)
├── PATCH /api/v1/users/security   # Update email/password (password required)
└── GET   /api/v1/users/search     # Search by email/name

Handicap Management
├── POST /api/v1/handicaps/update          # RFEG lookup + optional fallback
├── POST /api/v1/handicaps/update-manual   # Manual update
└── POST /api/v1/handicaps/update-multiple # Batch processing
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
    "handicap": 15.5
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
