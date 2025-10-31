# Módulo: User Management

## 📋 Descripción

Módulo responsable de la gestión de usuarios, incluyendo registro, autenticación y autorización.

## 🎯 Casos de Uso

### 1. Registro de Usuario (Register User)

**Actor**: Usuario no registrado

**Descripción**: Permite a un nuevo usuario crear una cuenta en el sistema.

**Precondiciones**: 
- El email no debe estar registrado previamente

**Flujo Principal**:
1. El usuario proporciona: email, nombre, apellido y contraseña
2. El sistema valida que el email tenga formato correcto
3. El sistema valida que la contraseña cumpla con los requisitos de seguridad
4. El sistema verifica que el email no esté ya registrado
5. El sistema hashea la contraseña usando bcrypt
6. El sistema crea el usuario en la base de datos PostgreSQL
7. El sistema devuelve los datos del usuario creado

**Flujos Alternativos**:
- **4a**: Si el email ya está registrado → Error: "User with email 'xxx' already exists" (HTTP 409)
- **2a**: Si el email no es válido → Error: "Invalid email format" (HTTP 400)
- **3a**: Si la contraseña no cumple requisitos → Error: "Password does not meet requirements" (HTTP 400)

**Postcondiciones**:
- Usuario creado en la tabla `users` de PostgreSQL
- Contraseña almacenada de forma segura (hasheada con bcrypt)
- Timestamps `created_at` y `updated_at` registrados

**Reglas de Negocio**:
- Email debe ser único en el sistema (constraint UNIQUE en BD)
- La contraseña debe tener mínimo 8 caracteres
- La contraseña debe contener al menos: 1 mayúscula, 1 minúscula, 1 número
- Nombre y apellido son obligatorios y no pueden exceder 100 caracteres

---

### 2. Login de Usuario (User Login)

**Actor**: Usuario registrado

**Descripción**: Permite a un usuario autenticarse en el sistema.

**Precondiciones**: 
- El usuario debe estar registrado

**Flujo Principal**:
1. El usuario proporciona: email y contraseña
2. El sistema busca el usuario por email en PostgreSQL
3. El sistema verifica que la contraseña sea correcta usando bcrypt
4. El sistema genera un token de acceso JWT
5. El sistema devuelve el token y los datos del usuario

**Flujos Alternativos**:
- **2a**: Si el usuario no existe → Error: "Invalid email or password" (HTTP 401)
- **3a**: Si la contraseña es incorrecta → Error: "Invalid email or password" (HTTP 401)

**Postcondiciones**:
- Token JWT válido generado con claims: user_id, email, exp, iat
- Usuario autenticado en el sistema

**Reglas de Negocio**:
- El token debe expirar después de 24 horas (configurable)
- Se deben ocultar detalles específicos del error por seguridad
- Límite de intentos de login fallidos: 5 intentos en 15 minutos (futuro)

---

## 🏗️ Modelo de Dominio

### Entity: User

```python
User
├── id: UserId (Value Object - UUID)
├── email: Email (Value Object)
├── password: Password (Value Object - bcrypt hashed)
├── first_name: str
├── last_name: str
├── created_at: datetime
└── updated_at: datetime
```

**Comportamientos**:
- `create(email, plain_password, first_name, last_name, hasher)`: Factory method async
- `verify_password(plain_password, hasher)`: Verifica contraseña de forma segura
- `update_profile(first_name, last_name)`: Actualiza perfil (futuro)
- `get_full_name()`: Retorna nombre completo

**Invariantes**:
- `first_name` y `last_name` no pueden estar vacíos
- Máximo 100 caracteres para nombres

### Value Objects

#### UserId
- UUID v4 generado con `uuid.uuid4()`
- Inmutable usando `@dataclass(frozen=True)`
- Métodos:
  - `generate()`: Genera nuevo ID
  - `from_string(user_id: str)`: Crea desde string
  - `to_string()`: Convierte a string

**Ejemplo**:
```python
user_id = UserId.generate()  # UserId(UUID('...'))
user_id_str = user_id.to_string()  # 'a1b2c3d4-...'
```

#### Email
- Formato validado con regex RFC 5322 simplificado
- Normalizado a lowercase automáticamente
- Inmutable usando `@dataclass(frozen=True)`
- Métodos:
  - `create(email: str)`: Factory method con validación
  - `get_domain()`: Extrae dominio
  - `get_local_part()`: Extrae parte local

**Reglas**:
- Debe cumplir expresión regular: `^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$`
- Máximo 254 caracteres (estándar RFC)
- Se normaliza a lowercase en `__post_init__`

**Ejemplo**:
```python
email = Email.create("User@EXAMPLE.com")
print(email)  # user@example.com
print(email.get_domain())  # example.com
```

#### Password
- Hasheada con bcrypt (12 rounds por defecto)
- Nunca se expone el valor hasheado fuera del dominio
- Inmutable usando `@dataclass(frozen=True)`
- Métodos:
  - `create(plain_password, hasher)`: Factory async con validación y hash
  - `from_hash(hashed_password)`: Crea desde hash existente
  - `verify(plain_password, hasher)`: Verifica contraseña async
  - `get_value()`: Obtiene hash (solo para persistencia)

**Reglas de Validación**:
- Mínimo 8 caracteres
- Al menos 1 mayúscula (A-Z)
- Al menos 1 minúscula (a-z)
- Al menos 1 número (0-9)
- Caracteres especiales recomendados (futuro)

**Ejemplo**:
```python
# Crear nueva contraseña
password = await Password.create("ValidPass123", hasher)

# Verificar contraseña
is_valid = await password.verify("ValidPass123", hasher)  # True

# Representación segura
print(password)  # "********"
```

---

## 🔧 Componentes Técnicos

### Repositories

#### UserRepository (ABC - Domain Layer)

```python
class UserRepository(ABC):
    @abstractmethod
    async def save(user: User) -> User
    
    @abstractmethod
    async def find_by_id(user_id: UserId) -> Optional[User]
    
    @abstractmethod
    async def find_by_email(email: Email) -> Optional[User]
    
    @abstractmethod
    async def exists_by_email(email: Email) -> bool
    
    @abstractmethod
    async def update(user: User) -> User
    
    @abstractmethod
    async def delete(user_id: UserId) -> None
```

#### UserRepositoryImpl (Infrastructure Layer)

**Tecnologías**:
- SQLAlchemy 2.0 con async support
- PostgreSQL como base de datos
- asyncpg como driver

**Características**:
- Usa `AsyncSession` de SQLAlchemy
- Mapeo entre `UserModel` (ORM) y `User` (Entity)
- Transacciones manejadas por FastAPI dependency
- Índice en columna `email` para búsquedas rápidas

**Ejemplo de implementación**:
```python
class UserRepositoryImpl(UserRepository):
    def __init__(self, session: AsyncSession):
        self._session = session
    
    async def save(self, user: User) -> User:
        model = UserModel(
            id=user.id.value,
            email=str(user.email),
            hashed_password=user.password.get_value(),
            first_name=user.first_name,
            last_name=user.last_name,
        )
        self._session.add(model)
        await self._session.flush()
        return user
    
    async def find_by_email(self, email: Email) -> Optional[User]:
        result = await self._session.execute(
            select(UserModel).where(UserModel.email == str(email))
        )
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None
```

### Domain Services

#### PasswordHasher (ABC - Domain Layer)

```python
class PasswordHasher(ABC):
    @abstractmethod
    async def hash(plain_password: str) -> str
    
    @abstractmethod
    async def verify(plain_password: str, hashed_password: str) -> bool
```

#### BcryptPasswordHasher (Infrastructure Layer)

**Tecnología**: passlib con bcrypt

**Características**:
- 12 rounds de hashing (configurable)
- Salt generado automáticamente
- Operaciones async para no bloquear event loop

**Ejemplo**:
```python
from passlib.context import CryptContext

class BcryptPasswordHasher(PasswordHasher):
    def __init__(self):
        self._context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    
    async def hash(self, plain_password: str) -> str:
        return self._context.hash(plain_password)
    
    async def verify(self, plain_password: str, hashed_password: str) -> bool:
        return self._context.verify(plain_password, hashed_password)
```

### Application Services

#### TokenService (ABC - Application Layer)

```python
@dataclass(frozen=True)
class TokenPayload:
    user_id: str
    email: str

class TokenService(ABC):
    @abstractmethod
    def generate(user_id: str, email: str) -> str
    
    @abstractmethod
    def verify(token: str) -> TokenPayload
    
    @abstractmethod
    def decode(token: str) -> Optional[TokenPayload]
```

#### JWTTokenService (Infrastructure Layer)

**Tecnología**: python-jose con cryptography

**Características**:
- Algoritmo HS256
- Claims: sub (user_id), email, exp, iat
- Expiración configurable (por defecto 24h)

**Configuración**:
```python
# En .env
SECRET_KEY=your-secret-key-min-32-chars
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440
```

**Ejemplo de token generado**:
```json
{
  "sub": "a1b2c3d4-5678-90ab-cdef-1234567890ab",
  "email": "user@example.com",
  "exp": 1735689600,
  "iat": 1735603200
}
```

---

## 📊 Esquema de Base de Datos (PostgreSQL)

### Tabla: users

```sql
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(254) NOT NULL UNIQUE,
    hashed_password VARCHAR(255) NOT NULL,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_created_at ON users(created_at);
```

**Constraints**:
- PRIMARY KEY en `id`
- UNIQUE en `email`
- NOT NULL en todos los campos excepto timestamps opcionales

**Índices**:
- `idx_users_email`: Para búsquedas rápidas por email en login
- `idx_users_created_at`: Para consultas ordenadas por fecha (futuro)

### SQLAlchemy Model

```python
from sqlalchemy import Column, String, DateTime
from sqlalchemy.dialects.postgresql import UUID
import uuid
from datetime import datetime

class UserModel(Base):
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(254), unique=True, nullable=False, index=True)
    hashed_password = Column(String, nullable=False)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, 
        default=datetime.utcnow, 
        onupdate=datetime.utcnow,
        nullable=False
    )
```

---

## 📡 API Endpoints (FastAPI)

### POST /api/users/register

Registra un nuevo usuario en el sistema.

**Request Body** (Pydantic Schema):
```python
class RegisterRequest(BaseModel):
    email: EmailStr  # Validación automática de email
    password: str = Field(min_length=8)
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
```

**Ejemplo Request**:
```json
{
  "email": "user@example.com",
  "password": "SecurePass123",
  "first_name": "John",
  "last_name": "Doe"
}
```

**Response (201 Created)**:
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "email": "user@example.com",
  "first_name": "John",
  "last_name": "Doe",
  "created_at": "2024-01-15T10:30:00.000Z"
}
```

**Errores**:
- **400 Bad Request**: Validación fallida
  ```json
  {"detail": "Password must be at least 8 characters long"}
  ```
- **409 Conflict**: Email ya registrado
  ```json
  {"detail": "User with email 'user@example.com' already exists"}
  ```
- **422 Unprocessable Entity**: Formato de datos inválido (Pydantic)

---

### POST /api/users/login

Autentica un usuario y devuelve un token JWT.

**Request Body**:
```python
class LoginRequest(BaseModel):
    email: EmailStr
    password: str
```

**Ejemplo Request**:
```json
{
  "email": "user@example.com",
  "password": "SecurePass123"
}
```

**Response (200 OK)**:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI1NTBlODQwMC1lMjliLTQxZDQtYTcxNi00NDY2NTU0NDAwMDAiLCJlbWFpbCI6InVzZXJAZXhhbXBsZS5jb20iLCJleHAiOjE3MzU2ODk2MDAsImlhdCI6MTczNTYwMzIwMH0.xyz123...",
  "token_type": "bearer",
  "user": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "email": "user@example.com",
    "first_name": "John",
    "last_name": "Doe"
  }
}
```

**Errores**:
- **401 Unauthorized**: Credenciales inválidas
  ```json
  {"detail": "Invalid email or password"}
  ```

**Uso del token**:
```bash
curl -H "Authorization: Bearer eyJhbGc..." http://localhost:8000/api/protected
```

---

## 🧪 Testing

### Stack de Testing
- **pytest**: Framework de testing
- **pytest-asyncio**: Soporte para tests async
- **pytest-cov**: Cobertura de código
- **httpx**: Cliente HTTP para tests E2E
- **faker**: Generación de datos de prueba

### Estructura de Tests

```
tests/
├── unit/                           # Tests de dominio
│   └── modules/user/
│       ├── test_email_vo.py       # Value Object Email
│       ├── test_password_vo.py    # Value Object Password
│       ├── test_user_id_vo.py     # Value Object UserId
│       └── test_user_entity.py    # Entity User
├── integration/                    # Tests con BD
│   └── modules/user/
│       ├── test_register_use_case.py
│       ├── test_login_use_case.py
│       └── test_user_repository.py
└── e2e/                           # Tests de endpoints
    └── test_user_endpoints.py
```

### Ejemplos de Tests

#### Unit Test - Email Value Object
```python
import pytest
from src.modules.user.domain.value_objects.email import Email

def test_create_valid_email():
    email = Email.create("user@example.com")
    assert str(email) == "user@example.com"

def test_email_normalized_to_lowercase():
    email = Email.create("User@EXAMPLE.COM")
    assert str(email) == "user@example.com"

def test_invalid_email_raises_error():
    with pytest.raises(ValueError, match="Invalid email format"):
        Email.create("invalid-email")
```

#### Integration Test - Register Use Case
```python
import pytest
from unittest.mock import AsyncMock

@pytest.mark.asyncio
async def test_register_user_successfully():
    # Arrange
    mock_repo = AsyncMock()
    mock_repo.exists_by_email.return_value = False
    mock_hasher = AsyncMock()
    
    use_case = RegisterUserUseCase(mock_repo, mock_hasher)
    command = RegisterUserCommand(
        email="user@example.com",
        password="ValidPass123",
        first_name="John",
        last_name="Doe"
    )
    
    # Act
    response = await use_case.execute(command)
    
    # Assert
    assert response.email == "user@example.com"
    mock_repo.save.assert_called_once()
```

#### E2E Test - Register Endpoint
```python
import pytest
from httpx import AsyncClient
from src.main import app

@pytest.mark.asyncio
async def test_register_endpoint():
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/api/users/register",
            json={
                "email": "test@example.com",
                "password": "ValidPass123",
                "first_name": "Test",
                "last_name": "User"
            }
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["email"] == "test@example.com"
        assert "id" in data
```

### Ejecutar Tests

```bash
# Todos los tests
pytest

# Solo unit tests
pytest tests/unit/ -v

# Solo integration tests
pytest tests/integration/ -v

# Con cobertura
pytest --cov=src --cov-report=html

# Tests específicos
pytest tests/unit/modules/user/test_email_vo.py -v

# Con markers
pytest -m unit
pytest -m integration
pytest -m e2e
```

---

## 🔐 Seguridad

### Hashing de Contraseñas
- **Algoritmo**: bcrypt
- **Library**: passlib[bcrypt]
- **Rounds**: 12 (2^12 = 4096 iteraciones)
- **Salt**: Generado automáticamente por bcrypt
- **Tiempo de hash**: ~200-300ms (balance seguridad/performance)

**Ejemplo de hash generado**:
```
$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5GyYqYVqM8EqS
│ │  │  │                                                │
│ │  │  │                                                └─ Hash (31 chars)
│ │  │  └─ Salt (22 chars)
│ │  └─ Cost factor (12)
│ └─ bcrypt version (2b)
└─ Identificador
```

### Tokens JWT
- **Algoritmo**: HS256 (HMAC with SHA-256)
- **Library**: python-jose[cryptography]
- **Estructura**: Header.Payload.Signature

**Configuración recomendada**:
```python
# .env
SECRET_KEY=min-32-characters-random-string-here-change-in-production
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440  # 24 horas
```

**Claims incluidos**:
- `sub`: User ID (subject)
- `email`: Email del usuario
- `exp`: Timestamp de expiración
- `iat`: Timestamp de emisión

**Generación de SECRET_KEY segura**:
```python
import secrets
print(secrets.token_urlsafe(32))
# Output: 'xV9kp2L4mQ8nR5tY7wZ3aB6cD1eF0gH9iJ8kL7mN6o'
```

### Buenas Prácticas Implementadas

✅ **Contraseñas**:
- Nunca se almacenan en texto plano
- Nunca se loguean (ni siquiera hasheadas)
- Siempre hasheadas antes de persistir
- Validación de fortaleza antes de aceptar

✅ **Autenticación**:
- Mensajes de error genéricos (no revelar si usuario existe)
- Rate limiting en login (futuro)
- Tokens con expiración
- Secret key fuerte y configurable

✅ **Base de Datos**:
- Uso de parámetros en queries (SQLAlchemy ORM previene SQL injection)
- Índices para performance sin sacrificar seguridad
- Constraints a nivel de BD

✅ **API**:
- Validación de entrada con Pydantic
- HTTPS obligatorio en producción
- CORS configurado apropiadamente
- Headers de seguridad (futuro)

### Checklist de Seguridad para Producción

- [ ] Cambiar SECRET_KEY a valor aleatorio fuerte
- [ ] Usar HTTPS (TLS 1.3)
- [ ] Habilitar CORS solo para dominios confiables
- [ ] Implementar rate limiting
- [ ] Añadir headers de seguridad (Helmet)
- [ ] Configurar logging sin exponer datos sensibles
- [ ] Implementar rotación de tokens
- [ ] Añadir 2FA (futuro)
- [ ] Monitoreo de intentos de login fallidos
- [ ] Backup encriptado de base de datos

---

## 🚀 Futuras Mejoras

### Fase 2: Verificación y Recuperación
- [ ] Confirmación de email con token
- [ ] Reset de contraseña vía email
- [ ] Cambio de contraseña para usuarios logueados
- [ ] Verificación de email en 2 pasos

### Fase 3: Autenticación Avanzada
- [ ] OAuth 2.0 (Google, Facebook, Apple)
- [ ] Refresh tokens para sesiones largas
- [ ] 2FA con TOTP (Google Authenticator)
- [ ] Biometría (WebAuthn/FIDO2)

### Fase 4: Gestión Avanzada
- [ ] Roles y permisos (RBAC)
- [ ] Sesiones múltiples
- [ ] Logs de auditoría de accesos
- [ ] Soft delete de usuarios
- [ ] Gestión de dispositivos confiables

### Fase 5: Seguridad y Compliance
- [ ] Rate limiting avanzado por IP y usuario
- [ ] Detección de patrones sospechosos
- [ ] Notificaciones de login desde nuevos dispositivos
- [ ] Exportación de datos (GDPR)
- [ ] Anonimización de datos para analytics

---

## 📚 Referencias

### Documentación
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [SQLAlchemy 2.0 Documentation](https://docs.sqlalchemy.org/en/20/)
- [Pydantic V2 Documentation](https://docs.pydantic.dev/latest/)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)

### Librerías Utilizadas
- **fastapi**: Framework web moderno y rápido
- **sqlalchemy**: ORM con soporte async
- **alembic**: Migraciones de base de datos
- **pydantic**: Validación de datos
- **python-jose**: Manejo de JWT
- **passlib**: Hashing de contraseñas
- **asyncpg**: Driver async para PostgreSQL

### Artículos y Recursos
- Clean Architecture in Python
- Domain-Driven Design patterns
- OAuth 2.0 y JWT best practices
- Password hashing con bcrypt
- Async Python patterns