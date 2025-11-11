# 🌐 API Reference

**Base URL**: `http://localhost:8000`
**Docs**: `/docs` (Swagger UI)
**Total Endpoints**: 7 active

## Quick Reference

```
Authentication
├── POST /api/v1/auth/register    # User registration
├── POST /api/v1/auth/login       # JWT authentication  
└── POST /api/v1/auth/logout      # Session logout

Handicap Management  
├── POST /api/v1/handicaps/update          # RFEG lookup + fallback
├── POST /api/v1/handicaps/update-manual   # Manual update
└── POST /api/v1/handicaps/update-multiple # Batch processing

User Management
└── GET /api/v1/users/search      # Search by email/name
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
  "created_at": "2025-11-09T10:00:00Z"
}
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
    "created_at": "2025-11-09T10:00:00Z"
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

### Using Authenticated Endpoints
```http
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

## Handicap Management

### Update Handicap (RFEG)
```http
POST /api/v1/handicaps/update

Request:
{
  "user_id": "uuid",
  "manual_handicap": 15.5  // Optional fallback
}

Response: 200 OK
{
  "id": "uuid",
  "handicap": 15.5,
  "handicap_updated_at": "2025-11-09T10:00:00Z",
  ...
}
```

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

### Find User
```http
GET /api/v1/users/search?email=john@example.com
GET /api/v1/users/search?full_name=John Doe

Response: 200 OK
{
  "id": "uuid",
  "email": "john@example.com",
  "first_name": "John",
  "last_name": "Doe",
  "handicap": 15.5
}
```

## Error Codes

- `400`: Bad Request (validación)
- `401`: Unauthorized (credenciales inválidas o token missing)
- `404`: Not Found
- `422`: Unprocessable Entity
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
