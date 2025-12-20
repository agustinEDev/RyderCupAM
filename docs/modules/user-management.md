# Módulo: User Management

## 📋 Descripción

Módulo responsable de la gestión de usuarios, incluyendo registro, autenticación JWT, gestión de perfiles, handicaps y verificación de email. Implementa Clean Architecture con DDD.

**📋 Ver API completa:** `docs/API.md`

---

## 🎯 Casos de Uso Implementados

### Autenticación
1. **RegisterUserUseCase** - Registro de nuevo usuario
2. **LoginUserUseCase** - Autenticación con JWT
3. **LogoutUserUseCase** - Cierre de sesión con revocación de refresh tokens
4. **RefreshAccessTokenUseCase** - Renovación de access tokens
5. **VerifyEmailUseCase** - Verificación de email con token único
6. **ResendVerificationEmailUseCase** - Reenvío de email de verificación

### Gestión de Perfil
7. **GetCurrentUserUseCase** - Obtener datos del usuario autenticado
8. **UpdateProfileUseCase** - Actualizar información personal (nombre, apellido, country_code)
9. **UpdateSecurityUseCase** - Cambiar email o contraseña

### Gestión de Handicaps
10. **UpdateUserHandicapManuallyUseCase** - Actualizar handicap manualmente
11. **UpdateUserHandicapUseCase** - Obtener handicap desde RFEG API
12. **BatchUpdateHandicapsUseCase** - Actualización masiva de handicaps (cron job)

---

## 🗃️ Modelo de Dominio

### Entity: User (Agregado Raíz)

**Identificación:**
- `id`: UserId (Value Object - UUID)

**Datos Personales:**
- `email`: Email (Value Object con validación RFC 5322)
- `password`: Password (Value Object - bcrypt hashed, OWASP ASVS V2.1)
- `first_name`: str (100 chars max)
- `last_name`: str (100 chars max)
- `country_code`: CountryCode (Value Object - ISO 3166-1 alpha-2, opcional)

**Handicap:**
- `handicap`: Handicap (Value Object - float, rango -10.0 a 54.0, opcional)
- `handicap_updated_at`: datetime

**Verificación de Email:**
- `email_verified`: bool (default False)
- `verification_token`: str (UUID único, opcional)

**Timestamps:**
- `created_at`: datetime
- `updated_at`: datetime

### Value Objects

**Implementados:**
- `UserId` - UUID único del usuario
- `Email` - Validación RFC 5322, normalización lowercase
- `Password` - Validación OWASP ASVS V2.1 (12 chars min, complejidad, blacklist)
- `Handicap` - Validación de rango [-10.0, 54.0]
- `CountryCode` - Validación ISO 3166-1 alpha-2

**📋 Ver implementación:** `src/modules/user/domain/value_objects/`

### Domain Events

**Implementados:**
1. `UserCreatedEvent` - Usuario registrado
2. `EmailVerifiedEvent` - Email verificado
3. `HandicapUpdatedEvent` - Handicap actualizado
4. `LoginAttemptEvent` - Intento de login (éxito/fallo) - Security
5. `LogoutEvent` - Logout ejecutado - Security
6. `RefreshTokenUsedEvent` - Refresh token usado - Security
7. `RefreshTokenRevokedEvent` - Refresh token revocado - Security
8. `PasswordChangedEvent` - Contraseña cambiada - Security
9. `EmailChangedEvent` - Email cambiado - Security

**📋 Ver eventos de seguridad:** `src/shared/domain/events/security_events.py`

---

## 🏗️ Arquitectura

### Repository Pattern

**Interfaces (Domain Layer):**
- `UserRepositoryInterface` - CRUD de usuarios
  - find_by_id, find_by_email, add, update, delete, exists_by_email
- `RefreshTokenRepositoryInterface` - Gestión de refresh tokens
  - save, find_by_token_hash, revoke_all_for_user, delete_expired

**Implementaciones (Infrastructure Layer):**
- `SQLAlchemyUserRepository` - Persistencia async con PostgreSQL
- `SQLAlchemyRefreshTokenRepository` - Persistencia de refresh tokens

**📋 Ver implementación:** `src/modules/user/infrastructure/persistence/sqlalchemy/`

### Unit of Work Pattern

**Interface (Domain Layer):**
```python
UserUnitOfWorkInterface
├── users: UserRepositoryInterface
├── refresh_tokens: RefreshTokenRepositoryInterface
├── async commit()
├── async rollback()
└── async __aenter__() / __aexit__()
```

**Implementación (Infrastructure Layer):**
- `SQLAlchemyUserUnitOfWork` - Gestión de transacciones atómicas

**Beneficios:**
- Transacciones atómicas (commit/rollback)
- Múltiples repositorios en una sola transacción
- Aislamiento de la lógica de negocio de la persistencia

### Domain Services

**Implementados:**
- `UserFinder` - Búsqueda de usuarios con validaciones de negocio
- `PasswordHasher` (ABC) → `BcryptPasswordHasher` (Infrastructure)
  - hash_password(), verify_password()
  - bcrypt: 12 rounds (prod), 4 rounds (tests)

### Application Services (Ports)

**Interfaces (Application Layer):**
- `IEmailService` - Envío de emails (Port)
- `ITokenService` - Generación de tokens JWT (Port)

**Implementaciones (Infrastructure Layer):**
- `EmailService` - Mailgun API (región EU)
- `JWTTokenService` - python-jose, algoritmo HS256

**Inyección de Dependencias:**
- Configurado en `src/config/dependencies.py`
- Inversión de control completa (IoC)

**📋 Ver refactorización:** CLAUDE.md - Dependency Injection Refactoring (16 Nov 2025)

---

## 🔐 Seguridad Implementada

### JWT Authentication
- **Access Token:** 15 minutos (httpOnly cookie)
- **Refresh Token:** 7 días (httpOnly cookie, SHA256 hash en BD)
- **Algoritmo:** HS256
- **Revocación:** Logout invalida refresh tokens en BD

### Password Security (OWASP ASVS V2.1)
- Longitud mínima: 12 caracteres
- Complejidad: Mayúsculas + Minúsculas + Dígitos + Símbolos
- Blacklist de contraseñas comunes
- Hashing: bcrypt 12 rounds

### httpOnly Cookies
- Protección contra XSS (JavaScript no puede acceder)
- Flags: httponly=True, secure=production, samesite="lax"
- Dual support: cookies (prioridad 1) + headers (legacy)

### Rate Limiting
- Login: 5 intentos/minuto por IP
- Register: 3 intentos/hora por IP
- RFEG API: 5 llamadas/hora por usuario

### Security Logging (Audit Trail)
- Logs en `logs/security_audit.log` (JSON estructurado)
- 9 eventos de seguridad auditados
- Contexto HTTP: IP, User-Agent
- Severity levels: CRITICAL, HIGH, MEDIUM, LOW

**📋 Ver implementación completa:** `docs/SECURITY_IMPLEMENTATION.md`

---

## 📊 Esquema de Base de Datos

### Tabla: users
```sql
CREATE TABLE users (
    id UUID PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    handicap DECIMAL(4,1),
    handicap_updated_at TIMESTAMP,
    email_verified BOOLEAN DEFAULT FALSE,
    verification_token VARCHAR(255),
    country_code VARCHAR(2) REFERENCES countries(code),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

### Tabla: refresh_tokens
```sql
CREATE TABLE refresh_tokens (
    id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(36) REFERENCES users(id) ON DELETE CASCADE,
    token_hash VARCHAR(64) UNIQUE NOT NULL,
    expires_at DATETIME NOT NULL,
    created_at DATETIME DEFAULT NOW(),
    revoked BOOLEAN DEFAULT FALSE,
    revoked_at DATETIME
);
CREATE INDEX idx_refresh_tokens_user_id ON refresh_tokens(user_id);
CREATE INDEX idx_refresh_tokens_token_hash ON refresh_tokens(token_hash);
CREATE INDEX idx_refresh_tokens_expires_at ON refresh_tokens(expires_at);
```

**Mappers SQLAlchemy:**
- Imperative Mapping (no declarative base)
- TypeDecorators para Value Objects de 1 columna
- Composites para Value Objects de múltiples columnas

**📋 Ver mappers:** `src/modules/user/infrastructure/persistence/sqlalchemy/mappers.py`

---

## 📡 API Endpoints

### Autenticación
- `POST /api/v1/auth/register` - Registro de usuario
- `POST /api/v1/auth/login` - Login con JWT
- `POST /api/v1/auth/logout` - Logout con revocación
- `POST /api/v1/auth/refresh-token` - Renovar access token
- `POST /api/v1/auth/verify-email` - Verificar email con token
- `POST /api/v1/auth/resend-verification` - Reenviar email de verificación
- `GET /api/v1/auth/current-user` - Obtener usuario autenticado

### Gestión de Perfil
- `GET /api/v1/users/profile` - Obtener perfil
- `PUT /api/v1/users/profile` - Actualizar perfil (nombre, apellido, country_code)
- `PUT /api/v1/users/security` - Actualizar email o contraseña

### Gestión de Handicaps
- `PUT /api/v1/users/handicaps/manual` - Actualizar handicap manual
- `POST /api/v1/users/handicaps/update` - Obtener desde RFEG API
- `POST /api/v1/users/handicaps/batch-update` - Actualización masiva (admin)

**📋 Ver documentación completa:** `docs/API.md`

**📋 Ver Postman Collection:** `docs/postman_collection.json`

---

## 🧪 Testing

### Stack de Testing
- **pytest** - Framework de tests
- **pytest-asyncio** - Tests async
- **pytest-xdist** - Paralelización
- **httpx** - Cliente HTTP para tests de integración

### Estadísticas
- **Total User Module:** 507 tests (100% pasando)
- **Unit Tests:** 308 tests
  - Domain: 49 tests (entities)
  - Value Objects: Tests de validación completos
  - Use Cases: 83 tests
- **Integration Tests:** 72 tests (API endpoints)

### Estructura
```
tests/
├── unit/
│   └── modules/user/
│       ├── domain/entities/test_user.py
│       ├── domain/value_objects/test_*.py
│       ├── application/use_cases/test_*.py
│       └── infrastructure/test_*.py
└── integration/
    └── api/v1/
        ├── test_user_routes.py
        └── test_auth_routes.py
```

### Ejecución
```bash
# Todos los tests del módulo User
pytest tests/unit/modules/user/ tests/integration/api/v1/test_user_routes.py -v

# Solo tests unitarios (rápido, no requiere BD)
pytest tests/unit/modules/user/ -v

# Con paralelización
pytest tests/unit/modules/user/ -n auto
```

### Test Doubles (In-Memory)
- `InMemoryUserRepository` - Tests sin PostgreSQL
- `InMemoryRefreshTokenRepository` - Tests de refresh tokens
- `InMemoryUnitOfWork` - Tests de transacciones

**📋 Ver test doubles:** `tests/in_memory/`

---

## 🔄 Decisiones Arquitectónicas Clave

### 1. Handicap Value Object Mapping
**Decisión:** TypeDecorator (no composite())

**Razón:**
- Handicap es un Value Object de 1 columna opcional (NULL)
- composite() no maneja NULL correctamente
- TypeDecorator convierte transparentemente Handicap ↔ float

**📋 Ver ADR:** CLAUDE.md - Decisiones Arquitectónicas

### 2. Dependency Injection Refactoring
**Decisión:** Ports & Adapters (Hexagonal Architecture)

**Antes (❌):**
- Use cases importaban directamente EmailService, JWTTokenService
- Violación del Dependency Inversion Principle

**Después (✅):**
- Application Layer: IEmailService, ITokenService (Ports)
- Infrastructure Layer: EmailService, JWTTokenService (Adapters)
- Use cases dependen de abstracciones

**Resultado:** 440/440 tests passing - Clean Architecture 100%

### 3. Session Timeout with Refresh Tokens
**Decisión:** Patrón de access token corto + refresh token largo

**Antes (❌):**
- Access token: 60 minutos
- No revocación posible
- Logout solo eliminaba cookie del navegador

**Después (✅):**
- Access token: 15 minutos (-75% window de hijacking)
- Refresh token: 7 días (SHA256 hash en BD)
- Revocación en BD al logout
- 722/722 tests pasando (+35 nuevos)

**📋 Ver implementación:** CLAUDE.md - Session Timeout with Refresh Tokens

### 4. Password Policy (OWASP ASVS V2.1)
**Decisión:** Actualizar de 8 a 12 caracteres mínimos

**Antes (❌):**
- 8 caracteres mínimos (obsoleto según OWASP 2024)

**Después (✅):**
- 12 caracteres mínimos
- Complejidad completa obligatoria
- Blacklist de contraseñas comunes
- 681 tests actualizados (100%)

**📋 Ver migración:** CLAUDE.md - Password Policy

---

## 🔗 Enlaces Relacionados

### Documentación
- **API Endpoints:** `docs/API.md`
- **Security Implementation:** `docs/SECURITY_IMPLEMENTATION.md`
- **Postman Collection:** `docs/postman_collection.json`

### Código Fuente
- **Domain Layer:** `src/modules/user/domain/`
- **Application Layer:** `src/modules/user/application/`
- **Infrastructure Layer:** `src/modules/user/infrastructure/`

### ADRs (Architecture Decision Records)
- **ADR-002:** Value Objects
- **ADR-005:** Repository Pattern
- **ADR-006:** Unit of Work Pattern
- **ADR-007:** Domain Events Pattern
- **ADR-013:** External Services Pattern
- **ADR-015:** Session Management Progressive Strategy
- **ADR-019:** Email Verification System

### Testing
- **Tests Unitarios:** `tests/unit/modules/user/`
- **Tests Integración:** `tests/integration/api/v1/`
- **Test Doubles:** `tests/in_memory/`

---

## 💡 Tips para Desarrollo

### Crear Nuevo Use Case
1. Definir DTO de Request y Response en `application/dto/`
2. Crear Use Case en `application/use_cases/`
3. Inyectar dependencies (UoW, services) en constructor
4. Implementar lógica en método `execute()`
5. Usar `async with self._uow:` para transacciones
6. Emitir domain events si es necesario
7. Crear tests unitarios + integración

### Añadir Nuevo Value Object
1. Crear clase en `domain/value_objects/`
2. Heredar de clase base si aplica
3. Implementar validaciones en constructor
4. Añadir método `__eq__()` para comparaciones
5. Crear TypeDecorator en mapper (si 1 columna)
6. Crear tests de validación completos

### Añadir Nuevo Endpoint
1. Definir route en `infrastructure/api/v1/`
2. Inyectar Use Case con `Depends()`
3. Inyectar `get_current_user` si requiere auth
4. Manejar excepciones de dominio → HTTP status codes
5. Añadir rate limiting si aplica
6. Documentar en `docs/API.md`
7. Actualizar Postman collection

---

**Última actualización:** 18 de Diciembre de 2025
**Versión:** 1.8.0
