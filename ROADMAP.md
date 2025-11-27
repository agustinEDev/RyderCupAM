# 🗺️ Roadmap - RyderCupFriends Backend (API)

> **Versión:** 1.7.0
> **Última actualización:** 27 Nov 2025
> **Estado general:** ✅ Producción
> **Framework:** FastAPI + SQLAlchemy (Async)
> **Arquitectura:** Clean Architecture + DDD

---

## 📊 Resumen Ejecutivo

### ✅ Completado (v1.0.0 - v1.7.0)

| Componente | Estado | Descripción |
|-----------|--------|-------------|
| **Clean Architecture** | ✅ 100% | Bounded Contexts, Use Cases, Repositories |
| **SQLAlchemy ORM** | ✅ Implementado | Async, parametrización automática (anti-SQL injection) |
| **Autenticación** | ✅ JWT | Login, Register, Email Verification |
| **Competiciones** | ✅ Completo | CRUD, Estados, Transiciones, Países adyacentes |
| **Enrollments** | ✅ Completo | Solicitudes, Aprobaciones, Equipos, Custom Handicap |
| **Handicaps** | ✅ Completo | Manual + RFEG (solo usuarios españoles) |
| **Países** | ✅ Repository | 250+ países, códigos ISO, adyacencias geográficas |
| **HTTPS** | ✅ Habilitado | Render.com proporciona SSL automático |

### 📈 Métricas Clave

- **Endpoints:** 45+ rutas API
- **Bounded Contexts:** 4 (User, Auth, Competition, Handicap)
- **Database:** PostgreSQL con migraciones Alembic
- **Deployment:** Render.com (contenedor Docker)

---

## 🔐 SEGURIDAD - Mejoras Prioritarias

> **Análisis de seguridad completado:** 27 Nov 2025
>
> **Estado de protecciones:**
> - ✅ **HTTPS:** Habilitado (Render.com)
> - ✅ **SQL Injection:** Protegido (SQLAlchemy ORM)
> - ⚠️ **Headers de Seguridad:** NO implementado
> - ⚠️ **Validación de Input:** Parcial (Pydantic básico)
> - ❌ **Rate Limiting:** NO implementado (CRÍTICO)
> - ❌ **CSRF Protection:** NO implementado (CRÍTICO)
> - ⚠️ **Dependencias:** Revisar actualizaciones

### 🔴 Prioridad CRÍTICA (v1.8.0 - Semana 1)

#### 1. Rate Limiting (SlowAPI)
**Estado:** ❌ **NO IMPLEMENTADO - CRÍTICO**
**Estimación:** 2-3 horas
**Impacto:** Prevención de brute force, DoS, spam

**Problema Actual:**
- Sin protección contra ataques brute force en login
- Sin límites de requests por IP/usuario
- Endpoints de autenticación completamente expuestos
- Recursos costosos (RFEG API) sin throttling

**Solución:**
```bash
# Instalar dependencia
pip install slowapi
```

```python
# src/main.py - Configuración global
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# src/modules/auth/infrastructure/api/auth_routes.py
@router.post("/login")
@limiter.limit("5/minute")  # 5 intentos por minuto
async def login(credentials: LoginRequest, request: Request):
    ...

@router.post("/register")
@limiter.limit("3/hour")  # 3 registros por hora
async def register(user_data: RegisterRequest, request: Request):
    ...
```

**Rate Limits Recomendados:**
| Endpoint | Límite | Motivo |
|----------|--------|--------|
| `POST /api/v1/auth/login` | **5/minute** | Anti brute-force (password guessing) |
| `POST /api/v1/auth/register` | **3/hour** | Anti spam (cuentas falsas) |
| `POST /api/v1/auth/verify-email` | **10/hour** | Anti abuse (reverificación) |
| `POST /api/v1/auth/forgot-password` | **3/hour** | Anti enumeration |
| `POST /api/v1/competitions/` | **10/hour** | Anti spam (torneos falsos) |
| `POST /api/v1/enrollments/` | **20/hour** | Uso normal de usuarios |
| `POST /api/v1/handicaps/update` | **5/hour** | RFEG API (recurso costoso) |
| `GET /api/v1/competitions` | **100/minute** | Lectura intensiva permitida |
| `GET /api/v1/users/{id}` | **60/minute** | Perfiles públicos |

**Archivos a Crear/Modificar:**
- `requirements.txt` - Agregar `slowapi>=0.1.9`
- `src/main.py` - Configurar limiter global
- `src/modules/auth/infrastructure/api/auth_routes.py` - Agregar decoradores
- `src/modules/competition/infrastructure/api/competition_routes.py` - Agregar decoradores
- `src/modules/enrollment/infrastructure/api/enrollment_routes.py` - Agregar decoradores
- `src/modules/handicap/infrastructure/api/handicap_routes.py` - Agregar decoradores

**Testing:**
```python
# tests/test_rate_limiting.py
def test_login_rate_limit():
    """Verificar que login bloquea después de 5 intentos"""
    for i in range(6):
        response = client.post("/api/v1/auth/login", json={
            "email": "test@example.com",
            "password": "wrong"
        })
        if i < 5:
            assert response.status_code in [200, 401]
        else:
            assert response.status_code == 429
            assert "Too Many Requests" in response.json()["detail"]
```

**Impacto:**
- ✅ Previene brute force en login (passwords)
- ✅ Previene spam en registro (bots)
- ✅ Previene DoS (ataques de denegación)
- ✅ Protege recursos costosos (RFEG API calls)

---

#### 2. Security Headers (python-secure)
**Estado:** ❌ **NO IMPLEMENTADO - ALTA PRIORIDAD**
**Estimación:** 1-2 horas
**Impacto:** Defensa en profundidad contra XSS, clickjacking, MIME sniffing

**Problema Actual:**
- No hay headers de seguridad en responses HTTP
- Frontend vulnerable a clickjacking
- Sin HSTS para forzar HTTPS
- Sin protección contra MIME sniffing

**Solución:**
```bash
# Instalar dependencia
pip install secure
```

```python
# src/main.py - Middleware de seguridad
from secure import Secure

secure_headers = Secure()

@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    secure_headers.framework.fastapi(response)
    return response
```

**Headers que se agregarán automáticamente:**
```http
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
Strict-Transport-Security: max-age=31536000; includeSubDomains
Referrer-Policy: strict-origin-when-cross-origin
Permissions-Policy: geolocation=(), microphone=(), camera=()
```

**Configuración personalizada (opcional):**
```python
from secure import Secure

# Configuración custom si se necesita
secure_headers = Secure.with_default_headers()
```

**Archivos a Modificar:**
- `requirements.txt` - Agregar `secure>=0.3.0`
- `src/main.py` - Agregar middleware de headers

**Verificación:**
```bash
# Verificar headers en respuesta
curl -I https://rydercup-api.onrender.com/api/v1/health

# Debe mostrar:
# X-Content-Type-Options: nosniff
# X-Frame-Options: DENY
# Strict-Transport-Security: max-age=31536000; includeSubDomains
```

**Impacto:**
- ✅ Previene clickjacking (X-Frame-Options: DENY)
- ✅ Previene MIME sniffing (X-Content-Type-Options: nosniff)
- ✅ Fuerza HTTPS en cliente (Strict-Transport-Security)
- ✅ Protege privacidad del usuario (Referrer-Policy)

---

#### 3. Migrar a httpOnly Cookies (JWT Tokens)
**Estado:** ❌ **NO IMPLEMENTADO - CRÍTICO**
**Estimación:** 6-8 horas (coordinado con frontend)
**Impacto:** Elimina robo de tokens via XSS

**Problema Actual:**
```python
# ❌ VULNERABLE: Tokens en response body (JSON)
# Frontend almacena en sessionStorage → accesible desde JavaScript
@router.post("/login")
async def login(credentials: LoginRequest):
    token = create_access_token(user.id)
    return {
        "access_token": token,  # ← Enviado al frontend
        "token_type": "bearer",
        "user": user_dto
    }
```

**Solución:**
```python
# ✅ SEGURO: Tokens en httpOnly cookies
from fastapi import Response

@router.post("/login")
async def login(credentials: LoginRequest, response: Response):
    token = create_access_token(user.id)

    # Set httpOnly cookie
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,   # ✅ No accesible desde JavaScript (anti-XSS)
        secure=True,     # ✅ Solo HTTPS en producción
        samesite="lax",  # ✅ Protección CSRF básica (80%)
        max_age=3600,    # 1 hora
        path="/",
        domain=None      # Automático según request
    )

    # NO enviar token en body
    return {"user": user_dto}  # Sin access_token
```

**Archivos a Modificar:**

**Backend:**
- `src/modules/auth/infrastructure/api/auth_routes.py`
  - `login()` - Set cookie en lugar de return token
  - `register()` - Set cookie en lugar de return token
  - `verify_email()` - Set cookie en lugar de return token
  - `logout()` - Delete cookie
- `src/shared/infrastructure/middleware/auth_middleware.py`
  - Leer token desde cookies en lugar de header `Authorization`
  - Mantener compatibilidad temporal con headers (para migración)
- `src/shared/infrastructure/security/jwt_handler.py`
  - Agregar helper `extract_token_from_cookies(request: Request)`

**Middleware de Autenticación:**
```python
# src/shared/infrastructure/middleware/auth_middleware.py
from fastapi import Request, HTTPException

def extract_token_from_cookies(request: Request) -> str:
    """Extrae JWT desde cookie httpOnly"""
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return token

async def get_current_user(request: Request):
    # Prioridad: cookies > header (para migración gradual)
    token = request.cookies.get("access_token")
    if not token:
        # Fallback temporal a header Authorization
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]

    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    return decode_and_validate_token(token)
```

**CORS Configuration:**
```python
# src/main.py
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "https://rydercup.com"
    ],
    allow_credentials=True,  # ✅ REQUERIDO para cookies
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**Testing:**
```python
# tests/test_httponly_cookies.py
def test_login_sets_httponly_cookie():
    response = client.post("/api/v1/auth/login", json={
        "email": "test@example.com",
        "password": "correct"
    })

    assert response.status_code == 200
    assert "access_token" in response.cookies
    assert response.cookies["access_token"]["httponly"] is True
    assert response.cookies["access_token"]["secure"] is True
    assert "access_token" not in response.json()  # NO en body

def test_protected_endpoint_accepts_cookie():
    # Login para obtener cookie
    login_response = client.post("/api/v1/auth/login", json={...})
    cookies = login_response.cookies

    # Request con cookie
    response = client.get("/api/v1/users/me", cookies=cookies)
    assert response.status_code == 200
```

**Impacto:**
- ✅ Elimina robo de tokens via XSS (JavaScript no puede acceder)
- ✅ Simplifica autenticación (navegador maneja cookies)
- ✅ 80% protección CSRF con `samesite=lax`

**Coordinación requerida:**
- ⚠️ **Requiere cambios simultáneos en frontend y backend**
- Ver: Frontend ADR-004 (httpOnly Cookies Migration)
- Plan de migración por fases (3 semanas):
  - Semana 1: Backend implementa (mantiene compatibilidad con headers)
  - Semana 2: Frontend migra a `credentials: 'include'`
  - Semana 3: Backend elimina soporte de headers Authorization

---

### 🟡 Prioridad ALTA (v1.8.0 - Semana 2-3)

#### 4. CSRF Protection (Evaluar después de httpOnly)
**Estado:** ❌ **NO IMPLEMENTADO**
**Estimación:** 4-6 horas (solo si es necesario)
**Impacto:** 100% protección CSRF

**Contexto:**
- httpOnly cookies con `samesite=lax` proveen 80% protección CSRF
- CSRF tokens explícitos proveen 100% protección
- **Decisión:** Implementar httpOnly primero, luego evaluar necesidad

**Estrategia en 2 Fases:**

**Fase 1: SameSite Cookies (YA IMPLEMENTADA en punto 3)**
```python
response.set_cookie(
    key="access_token",
    samesite="lax",  # ✅ 80% protección CSRF
)
```

**Fase 2: CSRF Tokens Explícitos (OPCIONAL - evaluar después)**
```bash
# Solo si análisis de riesgo lo justifica
pip install fastapi-csrf-protect
```

```python
from fastapi_csrf_protect import CsrfProtect
from fastapi_csrf_protect.exceptions import CsrfProtectError

@CsrfProtect.load_config
def get_csrf_config():
    return CsrfSettings(
        secret_key=os.getenv("CSRF_SECRET_KEY"),
        cookie_samesite="lax",
        cookie_secure=True,
        cookie_httponly=True
    )

# Aplicar a endpoints críticos
@router.post("/competitions/")
async def create_competition(
    competition: CompetitionCreate,
    csrf_protect: CsrfProtect = Depends()
):
    await csrf_protect.validate_csrf(request)
    # ... lógica
```

**Endpoints que requerirían CSRF (solo Fase 2):**
- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login`
- `POST /api/v1/competitions/`
- `PATCH /api/v1/competitions/{id}`
- `POST /api/v1/enrollments/`
- `PATCH /api/v1/enrollments/{id}`
- `PATCH /api/v1/users/security`

**Decisión de Implementación:**
- ✅ **Fase 1 (SameSite=lax)**: Implementar en v1.8.0 (con httpOnly cookies)
- ⏳ **Fase 2 (CSRF tokens)**: Evaluar necesidad en v1.9.0 después de análisis

---

#### 5. Validación de Inputs (Pydantic Mejorada)
**Estado:** ⚠️ **PARCIALMENTE IMPLEMENTADO**
**Estimación:** 4-6 horas
**Impacto:** Defensa en profundidad contra inyecciones

**Problema Actual:**
- Pydantic básico implementado
- Faltan validaciones de longitudes máximas
- Faltan validaciones de rangos
- Faltan sanitizaciones anti-XSS

**Mejoras Necesarias:**
```python
# src/modules/competition/application/dto/competition_dto.py
from pydantic import BaseModel, Field, validator

class CompetitionCreate(BaseModel):
    name: str = Field(..., min_length=3, max_length=100)
    location: str = Field(..., min_length=3, max_length=200)
    max_players: int = Field(..., ge=2, le=100)  # Entre 2 y 100
    description: str = Field(None, max_length=1000)

    @validator('name', 'location')
    def sanitize_html(cls, v):
        """Prevenir tags HTML (anti-XSS)"""
        if '<' in v or '>' in v:
            raise ValueError('Field cannot contain HTML tags')
        return v.strip()

    @validator('name')
    def validate_name_format(cls, v):
        """Validar formato de nombre"""
        if not v[0].isalpha():
            raise ValueError('Name must start with a letter')
        return v

class UserUpdate(BaseModel):
    first_name: str = Field(None, min_length=1, max_length=50)
    last_name: str = Field(None, min_length=1, max_length=50)

    @validator('*')
    def strip_whitespace(cls, v):
        if isinstance(v, str):
            return v.strip()
        return v
```

**Validaciones a Implementar por Módulo:**

| Módulo | DTO | Validaciones Requeridas |
|--------|-----|------------------------|
| **Auth** | `RegisterRequest` | Email format, password strength, name lengths |
| **User** | `UserUpdate` | Name lengths (1-50), no HTML tags |
| **Competition** | `CompetitionCreate` | Name (3-100), location (3-200), max_players (2-100) |
| **Enrollment** | `EnrollmentRequest` | Valid user_id/competition_id (UUID format) |
| **Handicap** | `HandicapUpdate` | Handicap range (0.0-54.0), RFEG license format |

**Archivos a Modificar:**
- `src/modules/auth/application/dto/auth_dto.py`
- `src/modules/user/application/dto/user_dto.py`
- `src/modules/competition/application/dto/competition_dto.py`
- `src/modules/enrollment/application/dto/enrollment_dto.py`
- `src/modules/handicap/application/dto/handicap_dto.py`

**Testing:**
```python
# tests/test_validation.py
def test_competition_name_rejects_html():
    response = client.post("/api/v1/competitions/", json={
        "name": "<script>alert('xss')</script>",
        "location": "Madrid",
        "max_players": 20
    })
    assert response.status_code == 422
    assert "cannot contain HTML tags" in response.json()["detail"]
```

**Impacto:**
- ✅ Defensa en profundidad contra XSS
- ✅ Prevención de datos inválidos en DB
- ✅ Mejores mensajes de error para frontend
- ✅ Validación consistente en toda la API

---

#### 6. Security Logging y Auditoría
**Estado:** ⚠️ **BÁSICO**
**Estimación:** 3-4 horas
**Impacto:** Detección de ataques, auditoría, debugging

**Problema Actual:**
- Logging básico sin estructura
- No se registran eventos de seguridad críticos
- Difícil detectar patrones de ataque

**Solución:**
```python
# src/shared/infrastructure/logging/security_logger.py
import logging
from datetime import datetime
from fastapi import Request

security_logger = logging.getLogger("security")
security_logger.setLevel(logging.INFO)

# Handler para archivo
file_handler = logging.FileHandler("logs/security.log")
file_handler.setFormatter(logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
))
security_logger.addHandler(file_handler)

def log_login_attempt(email: str, ip: str, success: bool):
    if success:
        security_logger.info(f"LOGIN_SUCCESS email={email} ip={ip}")
    else:
        security_logger.warning(f"LOGIN_FAILED email={email} ip={ip}")

def log_security_event(event_type: str, user_id: str, details: dict):
    security_logger.info(
        f"{event_type} user_id={user_id} details={details}"
    )
```

**Uso en Endpoints:**
```python
# src/modules/auth/infrastructure/api/auth_routes.py
from shared.infrastructure.logging.security_logger import log_login_attempt

@router.post("/login")
async def login(credentials: LoginRequest, request: Request):
    ip_address = request.client.host

    try:
        user = await authenticate_user(credentials)
        log_login_attempt(credentials.email, ip_address, success=True)
        return {"user": user}
    except AuthenticationError:
        log_login_attempt(credentials.email, ip_address, success=False)
        raise
```

**Eventos Críticos a Loggear:**
| Evento | Nivel | Información a Capturar |
|--------|-------|----------------------|
| Login success | INFO | user_id, email, ip, timestamp |
| Login failure | WARNING | email, ip, timestamp |
| Register | INFO | user_id, email, ip, country_code |
| Password change | INFO | user_id, ip |
| Email verification | INFO | user_id, email, ip |
| Competition created | INFO | user_id, competition_id, name |
| Enrollment approved/rejected | INFO | creator_id, user_id, competition_id, action |
| Rate limit exceeded | WARNING | endpoint, ip, timestamp |
| RFEG API call | INFO | user_id, license, success |

**Archivos a Crear/Modificar:**
- `src/shared/infrastructure/logging/security_logger.py` (crear)
- `src/modules/auth/infrastructure/api/auth_routes.py`
- `src/modules/user/infrastructure/api/user_routes.py`
- `src/modules/competition/infrastructure/api/competition_routes.py`

**Impacto:**
- ✅ Detección temprana de ataques (patrones en logs)
- ✅ Auditoría de acciones críticas
- ✅ Debugging mejorado
- ✅ Cumplimiento legal (trail de acciones)

---

#### 7. SQL Injection - Auditoría de Verificación
**Estado:** ✅ **BIEN PROTEGIDO** (SQLAlchemy ORM)
**Estimación:** 1 hora (auditoría)
**Impacto:** Mantener protección actual

**Estado Actual:**
- ✅ Todos los repositorios usan SQLAlchemy ORM
- ✅ Parametrización automática en queries
- ✅ No se detectó SQL raw en auditoría inicial

**Auditoría Recomendada:**
```bash
# Buscar posibles queries raw SQL
cd /Users/agustinestevezdominguez/Documents/RyderCupAm
grep -r "text(" src/
grep -r "execute(" src/
grep -r "raw_sql" src/
```

**Si se encuentran queries raw:**
1. Reemplazar con ORM cuando sea posible
2. Si es necesario usar raw SQL, usar siempre parametrización:

```python
# ✅ CORRECTO - Parametrización
from sqlalchemy import text

stmt = text("SELECT * FROM users WHERE email = :email")
result = await session.execute(stmt, {"email": email})

# ❌ INCORRECTO - String interpolation
stmt = text(f"SELECT * FROM users WHERE email = '{email}'")
result = await session.execute(stmt)
```

**Verificación:**
- Revisar queries complejas con JOINs
- Verificar filtros dinámicos
- Auditar custom queries en repositorios

**Impacto:**
- ✅ Mantener nivel de protección actual (excelente)
- ✅ Prevenir regresiones en futuro código

---

### 🟢 Prioridad MEDIA (v1.9.0)

#### 8. Implementar Sentry (Backend)
**Estado:** ❌ **NO IMPLEMENTADO**
**Estimación:** 3-4 horas
**Impacto:** Monitoreo de errores y performance

**Solución:**
```bash
# Instalar Sentry SDK
pip install sentry-sdk[fastapi]
```

```python
# src/main.py
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.sqlalchemy import SqlAlchemyIntegration

sentry_sdk.init(
    dsn=os.getenv("SENTRY_DSN"),
    environment=os.getenv("ENVIRONMENT", "production"),
    release=f"rydercup-api@{VERSION}",
    integrations=[
        FastApiIntegration(),
        SqlAlchemyIntegration(),
    ],
    traces_sample_rate=0.1,  # 10% de transacciones
    before_send=filter_sensitive_data,
)

def filter_sensitive_data(event, hint):
    """Filtrar datos sensibles antes de enviar a Sentry"""
    if 'request' in event:
        # Eliminar headers sensibles
        if 'headers' in event['request']:
            event['request']['headers'].pop('Authorization', None)
            event['request']['headers'].pop('Cookie', None)

        # Eliminar body con passwords
        if 'data' in event['request']:
            if 'password' in str(event['request']['data']):
                event['request']['data'] = '[FILTERED]'

    return event
```

**Eventos a Capturar:**
- Errores de API (500, 400, etc.)
- Errores de DB (queries fallidas, constraints)
- Errores de RFEG integration
- Performance de endpoints lentos (>2 segundos)

**Impacto:**
- ✅ Detección proactiva de errores en producción
- ✅ Monitoreo de performance
- ✅ Stack traces para debugging
- ✅ Alertas automáticas

---

#### 9. Auditoría de Dependencias
**Estado:** ⚠️ **REVISAR**
**Estimación:** 2 horas
**Impacto:** Prevención de vulnerabilidades conocidas

**Solución:**
```bash
# Instalar safety
pip install safety

# Verificar vulnerabilidades
safety check

# Actualizar dependencias
pip list --outdated
pip install --upgrade fastapi sqlalchemy alembic pydantic
```

**Proceso recomendado:**
1. Ejecutar `safety check` mensualmente
2. Revisar `pip list --outdated` mensualmente
3. Actualizar dependencias críticas (FastAPI, SQLAlchemy)
4. Testing exhaustivo después de updates

---

## 🛠️ Desarrollo - Tareas Pendientes

### Módulo de Usuario

#### Sistema de Avatares
**Estado:** ⏳ Pendiente
**Prioridad:** 🟡 Media
**Estimación:** 4-6 horas

**Requiere:**
1. Campo `avatar_url` en modelo User
2. Migración Alembic
3. Endpoint `PUT /api/v1/users/avatar` (multipart/form-data)
4. Endpoint `DELETE /api/v1/users/avatar`
5. Storage service (S3, Cloudinary, o local)

---

### Cross-Cutting Concerns

#### Gestión de Errores Unificada
**Estado:** ⏳ Pendiente
**Prioridad:** 🟡 Media
**Estimación:** 3-4 horas

**Objetivo:** Respuestas de error consistentes en toda la API

**Formato propuesto:**
```json
{
    "error": {
        "code": "VALIDATION_ERROR",
        "message": "Competition name is required",
        "details": {
            "field": "name",
            "constraint": "required"
        }
    }
}
```

---

## 🧪 Testing

### Estado Actual
- ⏳ Tests unitarios pendientes (usar pytest)
- ⏳ Tests de integración pendientes
- ⏳ Tests de seguridad pendientes

### Próximos Tests Prioritarios
1. Tests de rate limiting (verificar 429 después de límite)
2. Tests de httpOnly cookies (verificar flags httponly/secure)
3. Tests de validación de inputs (rechazar HTML, límites)
4. Tests de security headers (verificar presence)
5. Tests de autenticación (JWT, cookies, logout)

---

## 📦 Infraestructura

### Completado
- ✅ Deploy en Render.com
- ✅ PostgreSQL database
- ✅ Docker containerization
- ✅ Migraciones Alembic
- ✅ HTTPS habilitado

### Futuras Mejoras
- CI/CD con GitHub Actions
- Staging environment
- Database backups automáticos
- Monitoring (Prometheus + Grafana)

---

## 🚀 Roadmap de Versiones

### v1.8.0 (Próxima - Security Release) - Estimado: 2-3 semanas
**Objetivo:** Securizar la API contra ataques comunes

**Semana 1: Protecciones Inmediatas**
- 🔐 Rate limiting (SlowAPI) - 2-3h
- 🔐 Security headers (python-secure) - 1-2h
- 🧪 Tests de seguridad básicos - 2h

**Semana 2: httpOnly Cookies (Backend)**
- 🔐 Implementar set_cookie en auth routes - 3-4h
- 🔐 Modificar auth middleware - 2-3h
- 🧪 Tests de cookies - 2h

**Semana 3: httpOnly Cookies (Frontend) + Validaciones**
- 🔐 Frontend migración (coordinado) - 4-6h
- 🔐 Validaciones Pydantic mejoradas - 4-6h
- 📝 Security logging - 3-4h
- 🧪 Testing exhaustivo - 4h

**Total estimado:** 27-38 horas de desarrollo

---

### v1.9.0 (Funcionalidad) - 1-2 meses después
- 👤 Sistema de avatares
- 📝 Gestión de errores unificada
- 🔐 Sentry backend integration
- 🧪 Suite de tests completa
- 📊 Auditoría de dependencias

---

### v2.0.0 (Mayor - Futuro) - 4-6 meses
- 🔐 Autenticación de dos factores (2FA)
- 🔐 CSRF tokens explícitos (si análisis lo justifica)
- 📊 Analytics y estadísticas de torneos
- 🌍 Integración con más federaciones (no solo RFEG)
- 📱 Push notifications
- 🎮 Sistema de equipos mejorado

---

## 📝 Notas de Implementación

### Orden Recomendado de Implementación (v1.8.0)

**Día 1-2: Rate Limiting + Security Headers**
1. Instalar `slowapi` y `secure`
2. Configurar en `main.py`
3. Agregar decoradores a endpoints críticos
4. Testing básico
5. Deploy a staging y verificar

**Día 3-5: httpOnly Cookies (Backend)**
1. Modificar auth routes (set_cookie)
2. Actualizar auth middleware (leer cookies)
3. Mantener compatibilidad con headers (migración gradual)
4. Testing exhaustivo
5. Deploy a staging

**Día 6-10: Frontend Migration + Validaciones**
1. Frontend adapta a `credentials: 'include'`
2. Testing conjunto frontend + backend
3. Mejorar validaciones Pydantic en DTOs
4. Implementar security logging
5. Deploy coordinado a producción
6. Monitoreo intensivo con Sentry

**Día 11-15: Refinamiento y Testing**
1. Ajustar rate limits según uso real
2. Suite de tests de seguridad
3. Documentación de cambios
4. Eliminar compatibilidad con headers Authorization
5. Post-mortem y retrospectiva

---

### Coordinación Frontend-Backend

**Para cambios de seguridad (httpOnly cookies):**
1. Backend implementa primero (mantiene compatibilidad)
2. Frontend adapta después (elimina sessionStorage)
3. Testing exhaustivo en staging
4. Deploy coordinado (backend → frontend)
5. Monitoreo post-deploy (Sentry)
6. Cleanup de código legacy

---

## 🔗 Referencias

- [FastAPI Security Docs](https://fastapi.tiangolo.com/tutorial/security/)
- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [SQLAlchemy Security](https://docs.sqlalchemy.org/en/14/faq/security.html)
- [SlowAPI Documentation](https://slowapi.readthedocs.io/)
- [python-secure Documentation](https://secure.readthedocs.io/)
- Frontend ROADMAP: `../RyderCupWeb/ROADMAP.md`
- Frontend ADR-004: httpOnly Cookies Migration

---

**Última revisión:** 27 Nov 2025
**Próxima revisión:** Después de v1.8.0 (Security Release)
**Responsable:** Equipo de desarrollo backend
