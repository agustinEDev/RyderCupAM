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
1. El usuario proporciona datos a través de la API (email, nombre, apellido, contraseña).
2. El Caso de Uso `RegisterUserUseCase` recibe un `RegisterUserDTO`.
3. **[Dominio]** El Value Object `Email` valida y normaliza el email.
4. **[Dominio]** El Value Object `Password` valida la fortaleza de la contraseña.
5. **[UoW]** El sistema inicia una transacción.
6. El servicio de dominio `UserFinder` verifica que el email no exista.
7. La entidad `User` se crea a través de su factory `User.create()`, que a su vez hashea la contraseña y genera un evento `UserRegisteredEvent`.
8. El repositorio `UserRepository` guarda la nueva entidad `User`.
9. **[UoW]** El sistema confirma la transacción (commit).
10. El sistema devuelve los datos del usuario creado.

**Flujos Alternativos**:
- **6a**: Si el email ya está registrado → `UserAlreadyExistsError` → HTTP 409
- **3a**: Si el email no es válido → `InvalidEmailError` → HTTP 422 (Unprocessable Entity)
- **4a**: Si la contraseña no es válida → `InvalidPasswordError` → HTTP 422 (Unprocessable Entity)
- **8a**: Si falla el guardado → **[UoW]** Rollback automático → HTTP 500 (Error de Servidor)

**Postcondiciones**:
- Usuario creado en la tabla `users` de PostgreSQL
- Contraseña almacenada de forma segura (hasheada con bcrypt)
- Timestamps `created_at` y `updated_at` registrados
- **Transacción confirmada** o **revertida** completamente

**Reglas de Negocio**:
- Email debe ser único en el sistema (constraint UNIQUE en BD)
- La contraseña debe tener mínimo 8 caracteres
- La contraseña debe contener al menos: 1 mayúscula, 1 minúscula, 1 número
- Nombre y apellido son obligatorios y no pueden exceder 100 caracteres
- **Todas las operaciones deben ejecutarse en una transacción atómica**

---

### 2. Login de Usuario (User Login)

**Actor**: Usuario registrado

**Descripción**: Permite a un usuario autenticarse en el sistema.

**Precondiciones**: 
- El usuario debe estar registrado

**Flujo Principal**:
1. El usuario proporciona: email y contraseña
2. **[UoW]** El sistema inicia una transacción de lectura
3. El sistema busca el usuario por email en PostgreSQL
4. El sistema verifica que la contraseña sea correcta usando bcrypt
5. **[UoW]** El sistema cierra la transacción (no requiere commit)
6. El sistema genera un token de acceso JWT
7. El sistema devuelve el token y los datos del usuario

**Flujos Alternativos**:
- **3a**: Si el usuario no existe → Error: "Invalid email or password" (HTTP 401)
- **4a**: Si la contraseña es incorrecta → Error: "Invalid email or password" (HTTP 401)

**Postcondiciones**:
- Token JWT válido generado con claims: user_id, email, exp, iat
- Usuario autenticado en el sistema
- **No se modifican datos en la BD** (solo lectura)

**Reglas de Negocio**:
- El token debe expirar después de 24 horas (configurable)
- Se deben ocultar detalles específicos del error por seguridad
- Límite de intentos de login fallidos: 5 intentos en 15 minutos (futuro)

---

## 🗃️ Modelo de Dominio

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
- `add_domain_event(event)`: Añade evento de dominio
- `domain_events`: Propiedad con eventos pendientes
- `clear_domain_events()`: Limpia eventos después de publicar

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

### Domain Events

Los eventos de dominio permiten desacoplar efectos secundarios de la lógica principal de negocio en el módulo de usuarios.

#### Eventos Definidos

##### UserRegisteredEvent
```python
@dataclass(frozen=True)
class UserRegisteredEvent(DomainEvent):
    """Evento disparado cuando un usuario se registra exitosamente."""
    user_id: str
    email: str
    full_name: str
    registration_source: str = "web"
    registration_time: datetime = field(default_factory=datetime.now)
```

**Handlers que responden:**
- **WelcomeEmailHandler**: Envía email de bienvenida
- **UserMetricsHandler**: Actualiza métricas de registro
- **AuditLogHandler**: Registra evento para auditoría
- **NewUserNotificationHandler**: Notifica a administradores

##### UserLoggedInEvent
```python
@dataclass(frozen=True)
class UserLoggedInEvent(DomainEvent):
    """Evento disparado cuando un usuario hace login exitoso."""
    user_id: str
    login_time: datetime
    ip_address: str | None = None
    user_agent: str | None = None
    session_duration: int | None = None  # minutos de sesión anterior
```

**Handlers que responden:**
- **LastLoginUpdateHandler**: Actualiza timestamp de último login
- **SecurityAnalyticsHandler**: Detecta patrones de login sospechosos
- **SessionMetricsHandler**: Actualiza estadísticas de uso
- **LoginAuditHandler**: Registro detallado para seguridad

#### Event Collection en User Entity

```python
class User:
    def __init__(self, ...):
        # ... existing code ...
        self._domain_events: List[DomainEvent] = []
    
    @classmethod
    def create(cls, first_name: str, last_name: str, email_str: str, plain_password: str) -> 'User':
        """Factory method que genera UserRegisteredEvent automáticamente."""
        user = cls(...)
        
        # Generar evento de registro
        user.add_domain_event(UserRegisteredEvent(
            aggregate_id=str(user.id),
            user_id=str(user.id),
            email=email_str,
            full_name=user.get_full_name(),
            registration_source="web"
        ))
        
        return user
    
    def authenticate(self, plain_password: str, ip_address: str = None, user_agent: str = None) -> bool:
        """Autentica usuario y genera UserLoggedInEvent si es exitoso."""
        if self.verify_password(plain_password):
            self.add_domain_event(UserLoggedInEvent(
                aggregate_id=str(self.id),
                user_id=str(self.id),
                login_time=datetime.now(),
                ip_address=ip_address,
                user_agent=user_agent
            ))
            return True
        return False
    
    def add_domain_event(self, event: DomainEvent) -> None:
        """Añade evento de dominio para publicar después del commit."""
        self._domain_events.append(event)
    
    @property
    def domain_events(self) -> List[DomainEvent]:
        """Eventos pendientes de publicar."""
        return self._domain_events.copy()
    
    def clear_domain_events(self) -> None:
        """Limpia eventos después de publicarlos."""
        self._domain_events.clear()
```

---

## 🔧 Componentes Técnicos

### Repository Pattern

#### UserRepositoryInterface

**Ubicación**: `src/modules/user/domain/repositories/user_repository.py`

```python
from abc import ABC, abstractmethod
from typing import Optional, List
from src.modules.user.domain.entities.user import User
from src.modules.user.domain.value_objects.user_id import UserId
from src.modules.user.domain.value_objects.email import Email

@abstractmethod
class UserRepositoryInterface(ABC):
    """Interfaz para el repositorio de usuarios siguiendo Clean Architecture."""

    async def save(self, user: User) -> None:
        """Persiste un usuario en el almacén de datos."""
        pass

    async def find_by_id(self, user_id: UserId) -> Optional[User]:
        """Busca un usuario por su ID único."""
        pass

    async def find_by_email(self, email: Email) -> Optional[User]:
        """Busca un usuario por su email."""
        pass

    async def delete(self, user: User) -> None:
        """Elimina un usuario del almacén de datos."""
        pass

    async def list_all(self) -> List[User]:
        """Retorna todos los usuarios."""
        pass

    async def exists_by_email(self, email: Email) -> bool:
        """Verifica si existe un usuario con el email dado."""
        pass

    async def count(self) -> int:
        """Cuenta el total de usuarios."""
        pass

    async def update(self, user: User) -> None:
        """Actualiza un usuario existente."""
        pass
```

### Unit of Work Pattern

#### UnitOfWorkInterface (Base)

**Ubicación**: `src/shared/domain/repositories/unit_of_work.py`

```python
from abc import ABC, abstractmethod

@abstractmethod
class UnitOfWorkInterface(ABC):
    """Interfaz base para el patrón Unit of Work con soporte async."""

    async def __aenter__(self) -> 'UnitOfWorkInterface':
        """Inicia el contexto de la unidad de trabajo."""
        pass

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Finaliza el contexto, haciendo rollback si hay errores."""
        pass

    @abstractmethod
    async def commit(self) -> None:
        """Confirma todos los cambios de la transacción."""
        pass

    @abstractmethod
    async def rollback(self) -> None:
        """Revierte todos los cambios de la transacción."""
        pass

    @abstractmethod
    async def flush(self) -> None:
        """Sincroniza los cambios sin confirmar la transacción."""
        pass

    @abstractmethod
    def is_active(self) -> bool:
        """Indica si la unidad de trabajo está activa."""
        pass
```

#### UserUnitOfWorkInterface

**Ubicación**: `src/modules/user/domain/repositories/unit_of_work.py`

```python
from abc import abstractmethod
from src.shared.domain.interfaces.unit_of_work_interface import UnitOfWorkInterface
from src.modules.user.domain.interfaces.user_repository_interface import UserRepositoryInterface

@abstractmethod
class UserUnitOfWorkInterface(UnitOfWorkInterface):
    """Unit of Work específico para el módulo User."""
    
    @property
    @abstractmethod  
    def users(self) -> UserRepositoryInterface:
        """Acceso al repositorio de usuarios dentro de la transacción."""
        pass
```

### Beneficios de las Interfaces

#### Repository Pattern
- **Testabilidad**: Fácil creación de mocks para pruebas unitarias
- **Desacoplamiento**: La lógica de dominio no depende de tecnologías específicas
- **Flexibilidad**: Cambios de base de datos sin afectar la lógica de negocio
- **Principio de Inversión de Dependencias**: Las capas superiores dependen de abstracciones

#### Unit of Work Pattern
- **Atomicidad**: Garantiza que todas las operaciones se completen o fallen juntas
- **Consistencia**: Mantiene la integridad de los datos a través de múltiples repositorios
- **Gestión Automática**: Context manager que maneja commit/rollback automáticamente
- **Claridad**: Delimita claramente los límites transaccionales

#### Implementación (Infrastructure Layer)

**Ubicación**: `src/shared/infrastructure/persistence/sqlalchemy/sqlalchemy_unit_of_work.py`

```python
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from src.modules.user.domain.repositories.user_repository import UserRepository
from src.shared.domain.repositories.unit_of_work import UnitOfWorkInterface

class SQLAlchemyUnitOfWork(UnitOfWorkInterface):
    """
    Implementación del Unit of Work genérico usando SQLAlchemy.
    Gestiona la sesión y proporciona acceso a los repositorios.
    """
    
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        self._session_factory = session_factory
        self._session: AsyncSession | None = None
    
    async def __aenter__(self):
        self._session = self._session_factory()
        self.users = UserRepository(self._session)
        return self
```

**Características**:
- Implementa la `UnitOfWorkInterface`.
- Gestiona el ciclo de vida de la sesión de SQLAlchemy.
- Proporciona una instancia del `UserRepository` dentro del contexto transaccional.
- Utiliza un `async context manager` para garantizar `commit` o `rollback` automáticos.

            await self._session.rollback()
```

---

### Repositories

#### UserRepository (ABC - Domain Layer)

**Ubicación**: `src/modules/user/domain/repositories/user_repository.py`

```python
from abc import ABC, abstractmethod
from typing import Optional
from src.modules.user.domain.entities.user import User
from src.modules.user.domain.value_objects.user_id import UserId
from src.modules.user.domain.value_objects.email import Email

class UserRepository(ABC):
    """Interfaz del repositorio de usuarios."""
    
    @abstractmethod
    async def save(self, user: User) -> User:
        """Guarda un usuario."""
        pass
    
    @abstractmethod
    async def find_by_id(self, user_id: UserId) -> Optional[User]:
        """Busca un usuario por ID."""
        pass
    
    @abstractmethod
    async def find_by_email(self, email: Email) -> Optional[User]:
        """Busca un usuario por email."""
        pass
    
    @abstractmethod
    async def exists_by_email(self, email: Email) -> bool:
        """Verifica si existe un usuario con el email dado."""
        pass
    
    @abstractmethod
    async def update(self, user: User) -> User:
        """Actualiza un usuario."""
        pass
    
    @abstractmethod
    async def delete(self, user_id: UserId) -> None:
        """Elimina un usuario."""
        pass
```

#### UserRepositoryImpl (Infrastructure Layer)

**Ubicación**: `src/modules/user/infrastructure/persistence/user_repository_impl.py`

**Tecnologías**:
- SQLAlchemy 2.0 con async support
- PostgreSQL como base de datos
- asyncpg como driver

**Características**:
- Usa `AsyncSession` proporcionada por el UoW
- Mapeo entre `UserModel` (ORM) y `User` (Entity)
- **NO maneja transacciones** (delegado al UoW)
- Índice en columna `email` para búsquedas rápidas

**Ejemplo de implementación**:
```python
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

class UserRepositoryImpl(UserRepository):
    """Implementación del repositorio de usuarios con SQLAlchemy."""
    
    def __init__(self, session: AsyncSession):
        """
        Constructor.
        
        Args:
            session: Sesión de SQLAlchemy proporcionada por el UoW
        """
        self._session = session
    
    async def save(self, user: User) -> User:
        """Guarda un usuario en la base de datos."""
        model = self._to_model(user)
        self._session.add(model)
        await self._session.flush()  # NO commit, lo hace el UoW
        return user
    
    async def find_by_email(self, email: Email) -> Optional[User]:
        """Busca un usuario por email."""
        result = await self._session.execute(
            select(UserModel).where(UserModel.email == str(email))
        )
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None
    
    async def exists_by_email(self, email: Email) -> bool:
        """Verifica si existe un usuario con el email."""
        result = await self._session.execute(
            select(UserModel.id).where(UserModel.email == str(email))
        )
        return result.scalar_one_or_none() is not None
    
    def _to_model(self, user: User) -> UserModel:
        """Convierte entidad a modelo SQLAlchemy."""
        return UserModel(
            id=user.id.value,
            email=str(user.email),
            hashed_password=user.password.get_value(),
            first_name=user.first_name,
            last_name=user.last_name,
        )
    
    def _to_entity(self, model: UserModel) -> User:
        """Convierte modelo SQLAlchemy a entidad."""
        return User(
            id=UserId.from_string(str(model.id)),
            email=Email.create(model.email),
            password=Password.from_hash(model.hashed_password),
            first_name=model.first_name,
            last_name=model.last_name,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
```

**⚠️ Importante**: El repositorio NO maneja transacciones. Solo hace `flush()` para sincronizar con la BD, pero el `commit()` o `rollback()` lo gestiona el Unit of Work.

---

### Domain Services

#### PasswordHasher (ABC - Domain Layer)

**Ubicación**: `src/modules/user/domain/services/password_hasher.py`

```python
from abc import ABC, abstractmethod

class PasswordHasher(ABC):
    """Servicio de dominio para hashear contraseñas."""
    
    @abstractmethod
    async def hash(self, plain_password: str) -> str:
        """Hashea una contraseña en texto plano."""
        pass
    
    @abstractmethod
    async def verify(self, plain_password: str, hashed_password: str) -> bool:
        """Verifica una contraseña contra su hash."""
        pass
```

#### BcryptPasswordHasher (Infrastructure Layer)

**Ubicación**: `src/modules/user/infrastructure/security/bcrypt_password_hasher.py`

**Tecnología**: passlib con bcrypt

**Características**:
- 12 rounds de hashing (configurable)
- Salt generado automáticamente
- Operaciones async para no bloquear event loop

**Ejemplo**:
```python
from passlib.context import CryptContext
import asyncio
from functools import partial

class BcryptPasswordHasher(PasswordHasher):
    """Implementación de PasswordHasher usando bcrypt."""
    
    def __init__(self, rounds: int = 12):
        self._context = CryptContext(
            schemes=["bcrypt"],
            deprecated="auto",
            bcrypt__rounds=rounds
        )
    
    async def hash(self, plain_password: str) -> str:
        """Hashea una contraseña de forma asíncrona."""
        # Ejecutar en thread pool para no bloquear event loop
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, 
            partial(self._context.hash, plain_password)
        )
    
    async def verify(self, plain_password: str, hashed_password: str) -> bool:
        """Verifica una contraseña de forma asíncrona."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            partial(self._context.verify, plain_password, hashed_password)
        )
```

---

### Application Services

#### TokenService (ABC - Application Layer)

**Ubicación**: `src/modules/user/application/services/token_service.py`

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass(frozen=True)
class TokenPayload:
    """Payload del token JWT."""
    user_id: str
    email: str

class TokenService(ABC):
    """Servicio para gestionar tokens JWT."""
    
    @abstractmethod
    def generate(self, user_id: str, email: str) -> str:
        """Genera un token JWT."""
        pass
    
    @abstractmethod
    def verify(self, token: str) -> TokenPayload:
        """Verifica y decodifica un token JWT."""
        pass
    
    @abstractmethod
    def decode(self, token: str) -> TokenPayload | None:
        """Decodifica un token sin verificar (uso con precaución)."""
        pass
```

#### JWTTokenService (Infrastructure Layer)

**Ubicación**: `src/modules/user/infrastructure/security/jwt_token_service.py`

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

## 🎯 Casos de Uso con Unit of Work

### RegisterUserUseCase

**Ubicación**: `src/modules/user/application/use_cases/register_user/register_user_use_case.py`

```python
from dataclasses import dataclass
from src.modules.user.application.ports.user_unit_of_work import UserUnitOfWork
from src.modules.user.domain.services.password_hasher import PasswordHasher
from src.modules.user.domain.entities.user import User
from src.modules.user.domain.value_objects.email import Email
from src.modules.user.domain.errors.user_errors import EmailAlreadyExistsError

@dataclass(frozen=True)
class RegisterUserCommand:
    """Comando para registrar un usuario."""
    email: str
    password: str
    first_name: str
    last_name: str

@dataclass(frozen=True)
class UserResponse:
    """Respuesta con datos del usuario."""
    id: str
    email: str
    first_name: str
    last_name: str
    created_at: str

class RegisterUserUseCase:
    """Caso de uso: Registrar un nuevo usuario con soporte para Domain Events."""
    
    def __init__(
        self,
        uow: UserUnitOfWork,
        password_hasher: PasswordHasher,
        event_bus: EventBus
    ):
        """
        Constructor.
        
        Args:
            uow: Unit of Work para gestionar transacciones
            password_hasher: Servicio para hashear contraseñas
            event_bus: Bus de eventos para publicar domain events
        """
        self._uow = uow
        self._password_hasher = password_hasher
        self._event_bus = event_bus
    
    async def execute(self, command: RegisterUserCommand) -> UserResponse:
        """
        Ejecuta el caso de uso de registro.
        
        Args:
            command: Comando con los datos del usuario
            
        Returns:
            UserResponse con los datos del usuario creado
            
        Raises:
            EmailAlreadyExistsError: Si el email ya está registrado
            InvalidEmailError: Si el formato del email es inválido
            InvalidPasswordError: Si la contraseña no cumple requisitos
        """
        # Crear value objects (validación temprana)
        email = Email.create(command.email)
        
        # Iniciar transacción con Unit of Work
        async with self._uow:
            # Verificar que el email no existe (dentro de la transacción)
            if await self._uow.users.exists_by_email(email):
                raise EmailAlreadyExistsError(command.email)
            
            # Crear entidad de dominio (genera UserRegisteredEvent automáticamente)
            user = await User.create(
                email=email,
                plain_password=command.password,
                first_name=command.first_name,
                last_name=command.last_name,
                hasher=self._password_hasher
            )
            
            # Guardar usuario
            await self._uow.users.save(user)
            
            # Confirmar transacción
            await self._uow.commit()
            
            # Publicar eventos de dominio después del commit exitoso
            await self._uow.publish_events(self._event_bus)
        
        # Retornar respuesta
        return UserResponse(
            id=user.id.to_string(),
            email=str(user.email),
            first_name=user.first_name,
            last_name=user.last_name,
            created_at=user.created_at.isoformat()
        )
```

**Flujo de la transacción con eventos**:
1. `async with self._uow:` → Inicia sesión SQLAlchemy
2. `exists_by_email()` → Consulta en BD (dentro de transacción)
3. `User.create()` → Crea entidad + genera `UserRegisteredEvent` (solo en memoria)
4. `save()` → `INSERT` + `flush()` (sincroniza con BD, pero NO commit)
5. `commit()` → Confirma cambios en BD
6. `publish_events()` → Publica eventos de dominio después del commit exitoso
7. `__aexit__()` → Cierra sesión automáticamente

**Eventos disparados automáticamente**:
- **UserRegisteredEvent**: Contiene user_id, email, full_name, registration_source
- **Handlers ejecutados**: WelcomeEmailHandler, UserMetricsHandler, AuditLogHandler

**Manejo de errores**:
- Si ocurre cualquier excepción, el `__aexit__()` hace `rollback()` automático
- La sesión se cierra siempre, incluso si hay error

---

### LoginUserUseCase

**Ubicación**: `src/modules/user/application/use_cases/login_user/login_user_use_case.py`

```python
from dataclasses import dataclass
from src.modules.user.application.ports.user_unit_of_work import UserUnitOfWork
from src.modules.user.application.services.token_service import TokenService
from src.modules.user.domain.services.password_hasher import PasswordHasher
from src.modules.user.domain.value_objects.email import Email
from src.modules.user.domain.errors.user_errors import InvalidCredentialsError

@dataclass(frozen=True)
class LoginUserCommand:
    """Comando para hacer login."""
    email: str
    password: str

@dataclass(frozen=True)
class LoginResponse:
    """Respuesta del login."""
    access_token: str
    token_type: str
    user: UserResponse

class LoginUserUseCase:
    """Caso de uso: Autenticar usuario."""
    
    def __init__(
        self,
        uow: UserUnitOfWork,
        password_hasher: PasswordHasher,
        token_service: TokenService
    ):
        """
        Constructor.
        
        Args:
            uow: Unit of Work para gestionar transacciones
            password_hasher: Servicio para verificar contraseñas
            token_service: Servicio para generar tokens JWT
        """
        self._uow = uow
        self._password_hasher = password_hasher
        self._token_service = token_service
    
    async def execute(self, command: LoginUserCommand) -> LoginResponse:
        """
        Ejecuta el caso de uso de login.
        
        Args:
            command: Comando con email y contraseña
            
        Returns:
            LoginResponse con token y datos del usuario
            
        Raises:
            InvalidCredentialsError: Si las credenciales son inválidas
        """
        email = Email.create(command.email)
        
        # Usar UoW solo para lectura (no requiere commit)
        async with self._uow:
            # Buscar usuario
            user = await self._uow.users.find_by_email(email)
            if user is None:
                raise InvalidCredentialsError()
            
            # Verificar contraseña
            is_valid = await user.verify_password(
                command.password,
                self._password_hasher
            )
            if not is_valid:
                raise InvalidCredentialsError()
            
            # No se requiere commit (solo lectura)
        
        # Generar token (fuera de la transacción)
        token = self._token_service.generate(
            user_id=user.id.to_string(),
            email=str(user.email)
        )
        
        return LoginResponse(
            access_token=token,
            token_type="bearer",
            user=UserResponse(
                id=user.id.to_string(),
                email=str(user.email),
                first_name=user.first_name,
                last_name=user.last_name,
                created_at=user.created_at.isoformat()
            )
        )
```

**Nota sobre transacciones de lectura**:
- El login solo lee datos, no los modifica
- Aunque no se llama `commit()`, el UoW gestiona correctamente la sesión
- El `__aexit__()` cierra la sesión automáticamente

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

**Ubicación**: `src/modules/user/infrastructure/persistence/user_model.py`

```python
from sqlalchemy import Column, String, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base
import uuid
from datetime import datetime

Base = declarative_base()

class UserModel(Base):
    """Modelo SQLAlchemy para la tabla users."""
    
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

**Controller con Unit of Work**:
```python
from fastapi import APIRouter, Depends, status
from src.modules.user.presentation.schemas.register_request import RegisterRequest
from src.modules.user.presentation.schemas.user_response import UserResponse
from src.modules.user.application.use_cases.register_user.register_user_use_case import (
    RegisterUserUseCase,
    RegisterUserCommand
)

router = APIRouter(prefix="/api/users", tags=["users"])

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    request: RegisterRequest,
    use_case: RegisterUserUseCase = Depends(get_register_use_case)
):
    """Registra un nuevo usuario."""
    command = RegisterUserCommand(
        email=request.email,
        password=request.password,
        first_name=request.first_name,
        last_name=request.last_name
    )
    return await use_case.execute(command)
```

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
├── integration/                    # Tests con BD y UoW
│   └── modules/user/
│       ├── test_register_use_case.py
│       ├── test_login_use_case.py
│       ├── test_user_repository.py
│       └── test_user_unit_of_work.py  # Tests del UoW
└── e2e/                           # Tests de endpoints
    └── test_user_endpoints.py
```

### Ejemplos de Tests

#### Unit Test - Email Value Object
```python
import pytest
from src.modules.user.domain.value_objects.email import Email
from src.modules.user.domain.errors.user_errors import InvalidEmailError

def test_create_valid_email():
    """Verifica que se puede crear un email válido."""
    email = Email.create("user@example.com")
    assert str(email) == "user@example.com"

def test_email_normalized_to_lowercase():
    """Verifica que el email se normaliza a lowercase."""
    email = Email.create("User@EXAMPLE.COM")
    assert str(email) == "user@example.com"

def test_invalid_email_raises_error():
    """Verifica que un email inválido lanza error."""
    with pytest.raises(InvalidEmailError, match="Invalid email format"):
        Email.create("invalid-email")
```

#### Integration Test - Register Use Case con UoW
```python
import pytest
from src.modules.user.application.use_cases.register_user.register_user_use_case import (
    RegisterUserUseCase,
    RegisterUserCommand
)
from src.modules.user.domain.errors.user_errors import EmailAlreadyExistsError

@pytest.mark.asyncio
async def test_register_user_successfully(
    user_uow,
    password_hasher
):
    """Verifica que se puede registrar un usuario correctamente."""
    # Arrange
    use_case = RegisterUserUseCase(user_uow, password_hasher)
    command = RegisterUserCommand(
        email="test@example.com",
        password="ValidPass123",
        first_name="John",
        last_name="Doe"
    )
    
    # Act
    response = await use_case.execute(command)
    
    # Assert
    assert response.email == "test@example.com"
    assert response.first_name == "John"
    
    # Verificar que fue guardado en BD
    async with user_uow:
        from src.modules.user.domain.value_objects.email import Email
        saved_user = await user_uow.users.find_by_email(Email.create("test@example.com"))
        assert saved_user is not None

@pytest.mark.asyncio
async def test_register_user_duplicate_email_raises_error(
    user_uow,
    password_hasher
):
    """Verifica que no se puede registrar un usuario con email duplicado."""
    # Arrange
    use_case = RegisterUserUseCase(user_uow, password_hasher)
    command = RegisterUserCommand(
        email="duplicate@example.com",
        password="ValidPass123",
        first_name="John",
        last_name="Doe"
    )
    
    # Act - Primer registro
    await use_case.execute(command)
    
    # Assert - Segundo registro debe fallar
    with pytest.raises(EmailAlreadyExistsError):
        await use_case.execute(command)
```

#### Integration Test - Unit of Work
```python
import pytest
from src.modules.user.domain.entities.user import User
from src.modules.user.domain.value_objects.email import Email

@pytest.mark.asyncio
async def test_unit_of_work_commits_changes(user_uow, password_hasher):
    """Verifica que el UoW hace commit de los cambios."""
    # Arrange
    email = Email.create("uow-test@example.com")
    
    # Act
    async with user_uow:
        user = await User.create(
            email=email,
            plain_password="ValidPass123",
            first_name="UoW",
            last_name="Test",
            hasher=password_hasher
        )
        await user_uow.users.save(user)
        await user_uow.commit()
    
    # Assert - Verificar en nueva transacción
    async with user_uow:
        saved_user = await user_uow.users.find_by_email(email)
        assert saved_user is not None
        assert saved_user.first_name == "UoW"

@pytest.mark.asyncio
async def test_unit_of_work_rollbacks_on_error(user_uow, password_hasher):
    """Verifica que el UoW hace rollback automático en caso de error."""
    # Arrange
    email = Email.create("rollback-test@example.com")
    
    # Act - Simular error
    try:
        async with user_uow:
            user = await User.create(
                email=email,
                plain_password="ValidPass123",
                first_name="Rollback",
                last_name="Test",
                hasher=password_hasher
            )
            await user_uow.users.save(user)
            raise Exception("Simulated error")
    except Exception:
        pass
    
    # Assert - Verificar que NO fue guardado
    async with user_uow:
        saved_user = await user_uow.users.find_by_email(email)
        assert saved_user is None

@pytest.mark.asyncio
async def test_unit_of_work_multiple_operations(user_uow, password_hasher):
    """Verifica que el UoW maneja múltiples operaciones en una transacción."""
    # Arrange
    email1 = Email.create("multi1@example.com")
    email2 = Email.create("multi2@example.com")
    
    # Act - Múltiples operaciones
    async with user_uow:
        user1 = await User.create(
            email=email1,
            plain_password="ValidPass123",
            first_name="User",
            last_name="One",
            hasher=password_hasher
        )
        user2 = await User.create(
            email=email2,
            plain_password="ValidPass123",
            first_name="User",
            last_name="Two",
            hasher=password_hasher
        )
        await user_uow.users.save(user1)
        await user_uow.users.save(user2)
        await user_uow.commit()
    
    # Assert - Ambos usuarios deben existir
    async with user_uow:
        saved_user1 = await user_uow.users.find_by_email(email1)
        saved_user2 = await user_uow.users.find_by_email(email2)
        assert saved_user1 is not None
        assert saved_user2 is not None
```

#### E2E Test - Register Endpoint
```python
import pytest
from httpx import AsyncClient
from src.main import app

@pytest.mark.asyncio
async def test_register_endpoint():
    """Test E2E del endpoint de registro."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/api/users/register",
            json={
                "email": "e2e@example.com",
                "password": "ValidPass123",
                "first_name": "E2E",
                "last_name": "Test"
            }
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["email"] == "e2e@example.com"
        assert data["first_name"] == "E2E"
        assert "id" in data
        assert "created_at" in data

@pytest.mark.asyncio
async def test_register_endpoint_duplicate_email():
    """Test E2E verificando que no se puede duplicar email."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Primer registro
        await client.post(
            "/api/users/register",
            json={
                "email": "duplicate@example.com",
                "password": "ValidPass123",
                "first_name": "First",
                "last_name": "User"
            }
        )
        
        # Segundo registro (debe fallar)
        response = await client.post(
            "/api/users/register",
            json={
                "email": "duplicate@example.com",
                "password": "ValidPass123",
                "first_name": "Second",
                "last_name": "User"
            }
        )
        
        assert response.status_code == 409
        assert "already exists" in response.json()["detail"]
```

### Fixtures de Testing

**Ubicación**: `tests/conftest.py`

```python
import pytest
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from src.modules.user.infrastructure.persistence.user_unit_of_work_impl import UserUnitOfWorkImpl
from src.modules.user.infrastructure.security.bcrypt_password_hasher import BcryptPasswordHasher
from src.modules.user.infrastructure.persistence.user_model import Base

# Database para tests
TEST_DATABASE_URL = "postgresql+asyncpg://test:test@localhost:5432/ryder_cup_test"

@pytest.fixture(scope="session")
def event_loop():
    """Crea un event loop para toda la sesión de tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="session")
async def engine():
    """Crea el engine de SQLAlchemy para tests."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    
    # Crear todas las tablas
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    # Limpiar al final
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    await engine.dispose()

@pytest.fixture
async def session_factory(engine):
    """Factory para crear sesiones de SQLAlchemy."""
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

@pytest.fixture
async def user_uow(session_factory):
    """Fixture que proporciona un Unit of Work limpio para cada test."""
    uow = UserUnitOfWorkImpl(session_factory)
    
    # Limpiar datos antes del test
    async with uow:
        await uow._session.execute("TRUNCATE TABLE users RESTART IDENTITY CASCADE")
        await uow.commit()
    
    yield uow

@pytest.fixture
def password_hasher():
    """Fixture que proporciona un PasswordHasher."""
    return BcryptPasswordHasher(rounds=4)  # Menos rounds para tests más rápidos
```

### Ejecutar Tests

```bash
# Todos los tests
pytest

# Solo unit tests
pytest tests/unit/ -v

# Solo integration tests (incluye UoW)
pytest tests/integration/ -v

# Con cobertura
pytest --cov=src --cov-report=html

# Tests específicos del UoW
pytest tests/integration/modules/user/test_user_unit_of_work.py -v

# Tests con markers
pytest -m unit
pytest -m integration
pytest -m e2e

# Tests en paralelo (más rápido)
pytest -n auto
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

✅ **Transacciones**:
- **Unit of Work** garantiza atomicidad
- Rollback automático en caso de error
- Previene estados inconsistentes en BD
- Aislamiento de transacciones

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
- [ ] Auditoría de transacciones con UoW

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

### Mejoras en Unit of Work
- [ ] Soporte para transacciones anidadas
- [ ] Eventos de dominio con UoW
- [ ] Caché de entidades dentro de UoW
- [ ] Métricas de performance de transacciones
- [ ] Retry logic para transacciones fallidas
- [ ] Logging detallado de operaciones

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
- Unit of Work Pattern (Martin Fowler)
- OAuth 2.0 y JWT best practices
- Password hashing con bcrypt
- Async Python patterns
- SQLAlchemy async best practices

### Patrones Implementados
- **Unit of Work**: Gestión de transacciones y consistencia
- **Repository Pattern**: Abstracción de persistencia
- **Domain-Driven Design**: Entidades y Value Objects
- **Dependency Injection**: FastAPI Depends
- **Factory Pattern**: Creación de entidades
- **Command Pattern**: DTOs para casos de uso