# 🌐 API Reference

**Base URL**: `http://localhost:8000`
**Swagger UI**: `/docs` (auto-generado con ejemplos interactivos)
**ReDoc**: `/redoc` (documentación alternativa)
**Total Endpoints**: 33 active
**Version**: v1.8.0
**Last Updated**: 18 Dic 2025

---

## 📋 Quick Reference

```
Authentication (7 endpoints)
├── POST /api/v1/auth/register           # User registration
├── POST /api/v1/auth/login              # JWT authentication (httpOnly cookies)
├── GET  /api/v1/auth/current-user       # Get authenticated user info
├── POST /api/v1/auth/logout             # Session logout (revoke refresh tokens)
├── POST /api/v1/auth/verify-email       # Email verification
├── POST /api/v1/auth/resend-verification # Resend verification email
└── POST /api/v1/auth/refresh-token      # Renew access token

User Management (3 endpoints)
├── GET   /api/v1/users/search           # Search users by email/name
├── PATCH /api/v1/users/profile          # Update profile (name/surname/country)
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

---

## 🔐 Authentication

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/auth/register` | POST | No | Registro de usuario + email verification |
| `/auth/login` | POST | No | Login con JWT (httpOnly cookies) |
| `/auth/current-user` | GET | Yes | Obtener usuario autenticado |
| `/auth/logout` | POST | Yes | Logout con revocación de refresh tokens |
| `/auth/refresh-token` | POST | No | Renovar access token (usa refresh cookie) |
| `/auth/verify-email` | POST | No | Verificar email con token único |
| `/auth/resend-verification` | POST | No | Reenviar email de verificación |
| `/auth/forgot-password` | POST | No | Solicitar reseteo de contraseña (envía email con token) |
| `/auth/reset-password` | POST | No | Completar reseteo de contraseña usando token |
| `/auth/validate-reset-token/{token}` | GET | No | Validar token de reseteo antes de mostrar formulario |


### Campos Principales

**Register Request:**
- `email` (string, requerido, max 254, único)
- `password` (string, requerido, 12-128 chars, OWASP ASVS V2.1)
- `first_name` (string, requerido, max 100)
- `last_name` (string, requerido, max 100)
- `country_code` (string, opcional, ISO 3166-1 alpha-2)

**Login Request:**
- `email` (string, requerido)
- `password` (string, requerido)

**Login Response:**
- `access_token` (string, JWT) - LEGACY, usar cookie
- `refresh_token` (string, JWT) - LEGACY, usar cookie
- `user` (object) - Datos del usuario
- Cookies httpOnly: `access_token` (15 min), `refresh_token` (7 días)

**Forgot Password Request:**
- `email` (string, requerido)

**Forgot Password Response:**
- `message` (string) - Mensaje genérico de éxito

**Reset Password Request:**
- `token` (string, requerido) - Token recibido por email
- `new_password` (string, requerido, 12-128 chars, OWASP ASVS V2.1)

**Reset Password Response:**
- `message` (string) - Mensaje de confirmación

**Validate Reset Token Response:**
- `valid` (bool) - Indica si el token es válido
- `message` (string) - Mensaje explicativo


### Notas de Seguridad

- **httpOnly Cookies:** JWT almacenado en cookies inaccesibles desde JavaScript
- **Dual Support:** Cookies (prioridad 1) + Headers (legacy)
- **Rate Limiting:** Login 5/min, Register 3/h, Resend 3/h, Forgot/Reset 3/h, Validate 10/h
- **Password Policy:** 12 chars min, complejidad completa, blacklist
- **Forgot/Reset:** Mensaje genérico, nunca revela si el email existe (previene user enumeration)
- **Reset Token:** Token de un solo uso, expira en 24h, invalida todas las sesiones activas tras cambio
- **Refresh Tokens:** SHA256 hash en BD, revocables en logout

**📋 Ver detalles:** `docs/modules/user-management.md`, `docs/SECURITY_IMPLEMENTATION.md`

**📋 Ver detalles:** `docs/modules/user-management.md`, `docs/SECURITY_IMPLEMENTATION.md`

---

## 👤 User Management

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/users/search` | GET | Yes | Buscar usuarios por email/nombre |
| `/users/profile` | PATCH | Yes | Actualizar perfil (nombre, apellido, country) |
| `/users/security` | PATCH | Yes | Cambiar email o contraseña |

### Query Parameters

**GET /users/search:**
- `query` (string, optional) - Búsqueda parcial en email, first_name, last_name
- Retorna array de usuarios con datos básicos

### Notas

- Solo usuarios autenticados pueden buscar
- No se expone información sensible (passwords, tokens)
- country_code puede ser null

**📋 Ver módulo completo:** `docs/modules/user-management.md`

---

## ⛳ Handicap Management

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/handicaps/update` | POST | Yes | Obtener handicap desde RFEG API (solo españoles) |
| `/handicaps/update-manual` | POST | Yes | Actualizar handicap manualmente |
| `/handicaps/update-multiple` | POST | Yes | Actualización masiva (admin, cron job) |

### Campos Principales

**Update Manual Request:**
- `handicap` (float, required, -10.0 a 54.0)

**Update RFEG Request:**
- `license_number` (string, required) - Licencia RFEG

### Reglas de Negocio

- Solo usuarios españoles (country_code=ES) pueden usar RFEG
- RFEG API: 5 llamadas/hora por usuario (rate limiting)
- Handicap se actualiza automáticamente + timestamp
- Domain event `HandicapUpdatedEvent` emitido

**📋 Ver módulo completo:** `docs/modules/user-management.md`

---

## 🏆 Competition Management

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/competitions` | POST | Yes | Crear competición (estado DRAFT) |
| `/competitions` | GET | No | Listar competiciones con filtros |
| `/competitions/{id}` | GET | No | Obtener competición por ID |
| `/competitions/{id}` | PUT | Yes | Actualizar (solo DRAFT, solo creador) |
| `/competitions/{id}` | DELETE | Yes | Eliminar (solo DRAFT, solo creador) |
| `/competitions/{id}/activate` | POST | Yes | Transición DRAFT → ACTIVE |
| `/competitions/{id}/close-enrollments` | POST | Yes | Transición ACTIVE → CLOSED |
| `/competitions/{id}/start` | POST | Yes | Transición CLOSED → IN_PROGRESS |
| `/competitions/{id}/complete` | POST | Yes | Transición IN_PROGRESS → COMPLETED |
| `/competitions/{id}/cancel` | POST | Yes | Transición cualquier estado → CANCELLED |

### Campos Principales (Create/Update)

**Competition Request:**
- `name` (string, required, 3-100 chars, unique)
- `start_date` (date, required, formato YYYY-MM-DD)
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
- `status` (string, optional) - Filtrar por estado (DRAFT, ACTIVE, CLOSED, IN_PROGRESS, COMPLETED, CANCELLED)
- `creator_id` (string, optional) - Filtrar por creador
- `my_competitions` (bool, optional) - Solo competiciones donde usuario es creador o está inscrito
- `search_name` (string, optional) - Búsqueda parcial en nombre (case-insensitive)
- `search_creator` (string, optional) - Búsqueda parcial en nombre del creador

### Competition Response (Campos Calculados)

- `is_creator` (bool) - Si el usuario autenticado es el creador
- `enrolled_count` (int) - Cantidad de jugadores inscritos (APPROVED)
- `location` (string) - Nombres de países formateados (ej: "Spain, France")
- `creator` (object) - Datos completos del creador (nested object)
- `countries` (array) - Lista de países con detalles (code, name_en, name_es)

### Estados y Transiciones

```
DRAFT → ACTIVE → CLOSED → IN_PROGRESS → COMPLETED
  ↓        ↓         ↓           ↓
  └────────┴─────────┴───────────┴─→ CANCELLED
```

**Reglas:**
- Solo el creador puede modificar/eliminar/cambiar estado
- DRAFT: Solo editable, no visible públicamente
- ACTIVE: Inscripciones abiertas
- CLOSED: Inscripciones cerradas, equipos configurados
- IN_PROGRESS: Torneo en curso
- COMPLETED: Torneo finalizado
- CANCELLED: Cancelado desde cualquier estado

**📋 Ver módulo completo:** `docs/modules/competition-management.md` (pendiente de crear)

---

## 📝 Enrollment Management

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/competitions/{id}/enrollments` | POST | Yes | Solicitar inscripción (REQUESTED) |
| `/competitions/{id}/enrollments/direct` | POST | Yes | Inscripción directa por creador (APPROVED) |
| `/competitions/{id}/enrollments` | GET | Yes | Listar inscripciones con filtros |
| `/enrollments/{id}/approve` | POST | Yes | Aprobar solicitud (solo creador) |
| `/enrollments/{id}/reject` | POST | Yes | Rechazar solicitud (solo creador) |
| `/enrollments/{id}/cancel` | POST | Yes | Cancelar solicitud/invitación |
| `/enrollments/{id}/withdraw` | POST | Yes | Retirarse de competición |
| `/enrollments/{id}/handicap` | PUT | Yes | Establecer handicap personalizado |

### Campos Principales

**Request Enrollment:**
- Solo requiere autenticación
- Crea enrollment con estado REQUESTED
- Usuario puede cancelar antes de aprobación

**Direct Enroll:**
- `user_id` (string, required) - ID del usuario a inscribir
- Solo creador puede ejecutar
- Crea enrollment con estado APPROVED directamente

**Set Custom Handicap:**
- `custom_handicap` (float, required, -10.0 a 54.0)
- Solo creador puede establecer
- Override del handicap oficial del usuario

### Query Parameters (List)

**GET /competitions/{id}/enrollments:**
- `status` (string, optional) - Filtrar por estado (REQUESTED, APPROVED, REJECTED, CANCELLED, WITHDRAWN)

### Estados de Enrollment

```
REQUESTED → APPROVED → WITHDRAWN
    ↓           ↓
REJECTED    CANCELLED
```

**Estados:**
- `REQUESTED` - Solicitud pendiente de aprobación
- `INVITED` - Invitado por creador (futuro)
- `APPROVED` - Inscripción aprobada
- `REJECTED` - Solicitud rechazada por creador
- `CANCELLED` - Cancelada por jugador (pre-inscripción)
- `WITHDRAWN` - Retirado por jugador (post-inscripción)

### Enrollment Response (Campos)

- `id` (string) - UUID del enrollment
- `competition_id` (string) - ID de la competición
- `user_id` (string) - ID del usuario
- `user` (object) - Datos completos del usuario (nested object)
- `status` (string) - Estado actual
- `custom_handicap` (float, nullable) - Handicap personalizado
- `team` (string, nullable) - Equipo asignado (1 o 2)
- `created_at` (datetime) - Fecha de solicitud

### Reglas de Negocio

- Competición debe estar en estado ACTIVE para inscripciones
- No se permiten inscripciones duplicadas
- Solo creador puede aprobar/rechazar/inscribir directamente
- Solo dueño puede cancelar/retirarse
- custom_handicap es opcional, si no se establece usa el oficial

**📋 Ver módulo completo:** `docs/modules/competition-management.md` (pendiente de crear)

---

## 🌍 Country Management

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/countries` | GET | No | Listar todos los países activos |
| `/countries/{code}/adjacent` | GET | No | Listar países adyacentes |

### Country Response

**Estructura:**
- `code` (string) - Código ISO 3166-1 alpha-2 (ej: "ES")
- `name_en` (string) - Nombre en inglés (ej: "Spain")
- `name_es` (string) - Nombre en español (ej: "España")

**Datos:**
- 166 países globales (no solo Europa)
- 614 relaciones bidireccionales de fronteras
- Soporte para torneos en hasta 3 países adyacentes

### Uso

- Selectores de país en formularios
- Validación de adyacencia en creación de competiciones
- Location multi-país con nombres bilingües

---

## 📖 Swagger UI (Documentación Interactiva)

### Acceso

**URL:** `http://localhost:8000/docs`
**Autenticación:** HTTP Basic Auth
**Credenciales:** Configuradas en `.env` (DOCS_USERNAME, DOCS_PASSWORD)

### Features

- ✅ Ejemplos interactivos de requests/responses JSON completos
- ✅ "Try it out" - Ejecutar requests directamente desde el navegador
- ✅ Schemas de Pydantic auto-generados
- ✅ Validaciones y tipos de datos documentados
- ✅ Códigos de respuesta HTTP (200, 400, 401, 403, 404, 422, 500)
- ✅ Authentication con Bearer token o cookies

**Recomendación:** Usar Swagger UI para ver ejemplos JSON completos y probar endpoints.

---

## 📬 Postman Collection

**Archivo:** `docs/postman_collection.json`

**Features:**
- ✅ 33 requests pre-configurados
- ✅ Variables de entorno (BASE_URL, ACCESS_TOKEN)
- ✅ Ejemplos de requests/responses
- ✅ Tests automatizados en algunos endpoints
- ✅ Organizado por módulos (Auth, Users, Competitions, Enrollments)

**Importar en Postman:**
1. Abrir Postman
2. File → Import
3. Seleccionar `docs/postman_collection.json`
4. Configurar variable BASE_URL: `http://localhost:8000`

---

## 🔒 Seguridad y Rate Limiting

### Rate Limits por Endpoint

| Endpoint | Límite | Razón |
|----------|--------|-------|
| Global | 100/minuto | Protección DoS básica |
| POST /auth/login | 5/minuto | Anti brute-force |
| POST /auth/register | 3/hora | Anti spam de registros |
| POST /auth/resend-verification | 3/hora | Proteger Mailgun |
| POST /handicaps/update | 5/hora | Proteger RFEG API |
| POST /competitions | 10/hora | Anti spam de competiciones |

### HTTP Status Codes

| Code | Descripción | Cuándo se usa |
|------|-------------|---------------|
| 200 | OK | Request exitoso (GET, PUT, PATCH) |
| 201 | Created | Recurso creado (POST) |
| 204 | No Content | Recurso eliminado (DELETE) |
| 400 | Bad Request | Request inválido (validación Pydantic) |
| 401 | Unauthorized | No autenticado o token inválido |
| 403 | Forbidden | Autenticado pero sin permisos |
| 404 | Not Found | Recurso no encontrado |
| 409 | Conflict | Recurso duplicado (email, nombre competición) |
| 422 | Unprocessable Entity | Validación de dominio fallida |
| 429 | Too Many Requests | Rate limit excedido |
| 500 | Internal Server Error | Error no controlado del servidor |

### Headers de Seguridad

**Todos los responses incluyen:**
- `Strict-Transport-Security` - HSTS (2 años)
- `X-Frame-Options` - SAMEORIGIN (previene clickjacking)
- `X-Content-Type-Options` - nosniff (previene MIME-sniffing XSS)
- `Referrer-Policy` - no-referrer, strict-origin-when-cross-origin
- `Cache-Control` - no-store (previene cacheo de datos sensibles)
- `X-Correlation-ID` - UUID único para trazabilidad

**📋 Ver implementación completa:** `docs/SECURITY_IMPLEMENTATION.md`

---

## 🔗 Enlaces Relacionados

### Documentación de Módulos
- **User Management:** `docs/modules/user-management.md`
- **Competition Management:** `docs/modules/competition-management.md` (pendiente)

### Documentación Técnica
- **Security Implementation:** `docs/SECURITY_IMPLEMENTATION.md`
- **Multi-Environment Setup:** `docs/MULTI_ENVIRONMENT_SETUP.md`
- **Deployment:** `DEPLOYMENT.md`

### Código Fuente
- **User Module:** `src/modules/user/infrastructure/api/v1/`
- **Competition Module:** `src/modules/competition/infrastructure/api/v1/`

### Testing
- **Postman Collection:** `docs/postman_collection.json`
- **Integration Tests:** `tests/integration/api/v1/`

---

**Última actualización:** 18 de Diciembre de 2025
**Versión:** 1.8.0
