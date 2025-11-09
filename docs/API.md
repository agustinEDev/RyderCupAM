# 🌐 API Reference

**Base URL**: `http://localhost:8000`
**Docs**: `/docs` (Swagger UI)

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
- `404`: Not Found
- `422`: Unprocessable Entity
- `500`: Internal Server Error
