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
| **SQLAlchemy ORM** | ✅ Implementado | Async, parametrización automática |
| **Autenticación** | ✅ JWT | Login, Register, Email Verification |
| **Competiciones** | ✅ Completo | CRUD, Estados, Transiciones, Países adyacentes |
| **Enrollments** | ✅ Completo | Solicitudes, Aprobaciones, Equipos, Custom Handicap |
| **Handicaps** | ✅ Completo | Manual + RFEG (solo usuarios españoles) |
| **Países** | ✅ Repository | 250+ países, códigos ISO, adyacencias geográficas |

### 📈 Métricas Clave

- **Endpoints:** 45+ rutas API
- **Bounded Contexts:** 4 (User, Auth, Competition, Handicap)
- **Database:** PostgreSQL con migraciones Alembic
- **Deployment:** Render.com (contenedor Docker)

---

## 🔐 SEGURIDAD - Mejoras Prioritarias

### 🔴 Prioridad CRÍTICA

#### 1. Migrar a httpOnly Cookies (JWT Tokens)
**Problema Actual:**
```python
# ❌ VULNERABLE: Tokens en response body (JSON)
return {
    "access_token": token,
    "token_type": "bearer",
    "user": user_dto
}
```

**Solución:**
```python
# ✅ SEGURO: Tokens en httpOnly cookies
from fastapi import Response

@app.post("/api/v1/auth/login")
async def login(credentials: LoginRequest, response: Response):
    token = create_access_token(user.id)

    # Set httpOnly cookie
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,   # ✅ No accesible desde JavaScript (anti-XSS)
        secure=True,     # ✅ Solo HTTPS
        samesite="lax",  # ✅ Protección CSRF básica
        max_age=3600,    # 1 hora
        path="/",
        domain=None      # Automático
    )

    # NO enviar token en body
    return {"user": user_dto}
```

**Archivos a Modificar:**
- `src/modules/auth/infrastructure/api/auth_routes.py`
  - `login()` - Set cookie en lugar de return token
  - `register()` - Set cookie en lugar de return token
  - `verify_email()` - Set cookie en lugar de return token
- `src/shared/infrastructure/middleware/auth_middleware.py`
  - Leer token desde cookies en lugar de header `Authorization`
- `src/shared/infrastructure/security/jwt_handler.py`
  - Agregar helper `extract_token_from_cookies()`

**Testing:**
- Tests de login con validación de cookies
- Tests de endpoints protegidos con cookies
- Tests de logout (cookie deletion)

**Impacto:** Elimina robo de tokens via XSS

---

#### 2. Implementar CSRF Tokens
**Problema Actual:**
- No hay validación CSRF en endpoints mutables
- Solo CORS como protección (insuficiente)

**Solución:**
```python
# Instalar dependencia
pip install fastapi-csrf-protect

# Configurar CSRF
from fastapi_csrf_protect import CsrfProtect
from fastapi_csrf_protect.exceptions import CsrfProtectError

@CsrfProtect.load_config
def get_csrf_config():
    return CsrfSettings(
        secret_key="tu-secret-key-desde-env",
        cookie_samesite="lax",
        cookie_secure=True,
        cookie_httponly=True
    )

# Aplicar a endpoints críticos
@app.post("/api/v1/competitions/")
async def create_competition(
    competition: CompetitionCreate,
    csrf_protect: CsrfProtect = Depends()
):
    await csrf_protect.validate_csrf(request)
    # ... lógica de creación
```

**Endpoints Críticos a Proteger:**
- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login`
- `POST /api/v1/competitions/`
- `PATCH /api/v1/competitions/{id}`
- `POST /api/v1/enrollments/`
- `PATCH /api/v1/enrollments/{id}`
- `PATCH /api/v1/users/security`

**Archivos a Modificar:**
- `src/shared/infrastructure/middleware/csrf_middleware.py` (crear)
- Todos los endpoints con operaciones mutables (POST, PUT, PATCH, DELETE)

**Impacto:** Protección contra ataques CSRF

---

#### 3. Rate Limiting
**Problema Actual:**
- Sin protección contra brute force attacks
- Sin límites de requests por IP/usuario

**Solución:**
```python
# Instalar dependencia
pip install slowapi

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Aplicar rate limits
@app.post("/api/v1/auth/login")
@limiter.limit("5/minute")  # 5 intentos por minuto
async def login(...):
    # ...

@app.post("/api/v1/auth/register")
@limiter.limit("3/hour")  # 3 registros por hora
async def register(...):
    # ...
```

**Rate Limits Recomendados:**
| Endpoint | Límite | Motivo |
|----------|--------|--------|
| `POST /api/v1/auth/login` | 5/minute | Anti brute-force |
| `POST /api/v1/auth/register` | 3/hour | Anti spam |
| `POST /api/v1/auth/verify-email` | 10/hour | Anti abuse |
| `POST /api/v1/competitions/` | 10/hour | Anti spam |
| `POST /api/v1/enrollments/` | 20/hour | Uso normal |
| `GET /api/v1/competitions` | 100/minute | Lectura intensiva |

**Archivos a Crear/Modificar:**
- `src/shared/infrastructure/middleware/rate_limit_middleware.py` (crear)
- Configuración en `main.py`
- Todos los endpoints críticos

**Impacto:** Prevención de brute force, DoS, spam

---

### 🟡 Prioridad ALTA

#### 4. SQL Injection - Auditoría Adicional
**Estado Actual:** ✅ **Bien Protegido** (SQLAlchemy ORM)

**Verificar:**
- ✅ No hay queries con SQL raw strings
- ✅ Todos los repositorios usan ORM con parametrización
- ⚠️ Revisar queries complejas con JOINs

**Auditoría Recomendada:**
```bash
# Buscar SQL raw en el código
grep -r "text(" src/
grep -r "execute(" src/
grep -r "raw_sql" src/
```

**Si se encuentran queries raw:**
1. Reemplazar con ORM cuando sea posible
2. Si es necesario usar raw SQL, usar siempre parametrización:
   ```python
   # ✅ CORRECTO
   stmt = text("SELECT * FROM users WHERE email = :email")
   result = await session.execute(stmt, {"email": email})

   # ❌ INCORRECTO
   stmt = text(f"SELECT * FROM users WHERE email = '{email}'")
   ```

**Impacto:** Mantener protección actual

---

#### 5. Validación de Inputs
**Estado Actual:** ⚠️ **Parcialmente Implementado**

**Mejoras Necesarias:**
```python
# Agregar validaciones estrictas en DTOs
from pydantic import BaseModel, Field, validator

class CompetitionCreate(BaseModel):
    name: str = Field(..., min_length=3, max_length=100)
    location: str = Field(..., min_length=3, max_length=200)
    max_players: int = Field(..., ge=2, le=100)  # Entre 2 y 100

    @validator('name')
    def name_must_not_contain_html(cls, v):
        # Anti-XSS: No permitir tags HTML
        if '<' in v or '>' in v:
            raise ValueError('Name cannot contain HTML tags')
        return v.strip()
```

**Validaciones a Implementar:**
1. **Longitudes máximas** en todos los strings
2. **Rangos válidos** en números (handicaps, max_players)
3. **Formatos válidos** (emails, country_codes, dates)
4. **Sanitización** de inputs (strip whitespace, prevent HTML)

**Archivos a Modificar:**
- Todos los DTOs en `src/modules/*/application/dto/`

**Impacto:** Defensa en profundidad contra inyecciones

---

#### 6. Logging y Auditoría
**Estado Actual:** ⚠️ **Básico**

**Implementar:**
```python
import logging
from datetime import datetime

# Configurar logging estructurado
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Logging de eventos de seguridad
logger = logging.getLogger("security")

# Eventos a loggear:
# - Login attempts (success/failure)
# - Password changes
# - Email verification attempts
# - Competition creation/deletion
# - Enrollment status changes
# - RFEG API calls

@app.post("/api/v1/auth/login")
async def login(credentials: LoginRequest, request: Request):
    logger.info(f"Login attempt: email={credentials.email}, ip={request.client.host}")
    try:
        user = await authenticate_user(credentials)
        logger.info(f"Login success: user_id={user.id}")
        return {"user": user}
    except AuthenticationError:
        logger.warning(f"Login failed: email={credentials.email}, ip={request.client.host}")
        raise
```

**Eventos Críticos:**
| Evento | Nivel | Información |
|--------|-------|-------------|
| Login success | INFO | user_id, ip, timestamp |
| Login failure | WARNING | email, ip, timestamp |
| Register | INFO | user_id, ip, country_code |
| Password change | INFO | user_id, ip |
| Competition created | INFO | user_id, competition_id |
| Enrollment approved/rejected | INFO | creator_id, user_id, competition_id |

**Archivos a Crear/Modificar:**
- `src/shared/infrastructure/logging/security_logger.py` (crear)
- Todos los endpoints críticos

**Impacto:** Detección de ataques, auditoría, debugging

---

### 🟢 Prioridad MEDIA

#### 7. Configurar HSTS en Render
**Acción:**
- Configurar header `Strict-Transport-Security` en configuración de Render
- Valor recomendado: `max-age=31536000; includeSubDomains; preload`

**Pasos:**
1. Render Dashboard → Service Settings
2. Headers → Add Custom Header
3. Key: `Strict-Transport-Security`
4. Value: `max-age=31536000; includeSubDomains`

**Impacto:** Forzar HTTPS en todas las conexiones

---

#### 8. Implementar Sentry
**Estado:** ❌ No implementado

**Acción:**
```bash
# Instalar Sentry SDK
pip install sentry-sdk[fastapi]
```

```python
# Configurar en main.py
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
    traces_sample_rate=0.1,  # 10% en producción
    before_send=filter_sensitive_data,
)
```

**Eventos a Capturar:**
- Errores de API (500, 400, etc.)
- Errores de DB (queries fallidas, constraints)
- Errores de RFEG integration
- Performance de endpoints lentos

**Impacto:** Monitoreo de errores y performance

---

#### 9. Secrets Management
**Problema Actual:** Variables de entorno en Render

**Mejora:**
- Migrar a servicio dedicado (AWS Secrets Manager, HashiCorp Vault)
- Rotación automática de secrets (JWT keys, DB passwords)

**Impacto:** Mejor gestión de secretos, rotación automática

---

## 🛠️ Desarrollo - Tareas Pendientes

### Módulo de Usuario

#### Sistema de Avatares (Bloqueante para Frontend)
**Estado:** ⏳ Pendiente
**Prioridad:** 🟡 Media

**Requiere:**
1. Campo `avatar_url` en modelo User
2. Migración Alembic
3. Endpoint `PUT /api/v1/users/avatar` (multipart/form-data)
4. Endpoint `DELETE /api/v1/users/avatar`
5. Storage service (S3, Cloudinary, o local)

**Estimación:** 4-6 horas

---

### Cross-Cutting Concerns

#### Gestión de Errores Unificada
**Estado:** ⏳ Pendiente

**Objetivo:** Respuestas de error consistentes

**Ejemplo:**
```python
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

### Próximos Tests
- Tests de authentication (JWT, cookies, CSRF)
- Tests de rate limiting
- Tests de SQL injection (intentar bypassear ORM)
- Tests de validación de inputs
- Tests de RFEG integration

---

## 📦 Infraestructura

### Completado
- ✅ Deploy en Render.com
- ✅ PostgreSQL database
- ✅ Docker containerization
- ✅ Migraciones Alembic

### Futuras Mejoras
- CI/CD con GitHub Actions
- Staging environment
- Database backups automáticos
- Monitoring (Prometheus + Grafana)

---

## 🚀 Roadmap de Versiones

### v1.8.0 (Próxima - Seguridad)
- 🔐 httpOnly cookies para JWT
- 🔐 CSRF tokens
- 🔐 Rate limiting global
- 🔐 Sentry integration
- 📝 Security logging
- 🧪 Tests de seguridad

### v1.9.0 (Funcionalidad)
- 👤 Sistema de avatares
- 📝 Gestión de errores unificada
- 🧪 Suite de tests completa

### v2.0.0 (Mayor - Futuro)
- 🔐 Autenticación de dos factores (2FA)
- 📊 Analytics y estadísticas de torneos
- 🌍 Integración con más federaciones (no solo RFEG)
- 📱 Push notifications
- 🎮 Sistema de equipos mejorado

---

## 📝 Notas de Implementación

### Prioridad de Implementación

**Orden recomendado:**
1. **httpOnly cookies** (crítico para seguridad)
2. **CSRF tokens** (crítico para seguridad)
3. **Rate limiting** (crítico para estabilidad)
4. **Sentry** (importante para monitoreo)
5. **Security logging** (importante para auditoría)
6. **Validaciones mejoradas** (buena práctica)
7. **Sistema de avatares** (funcionalidad, no bloqueante)

### Coordinación Frontend-Backend

**Para cambios de seguridad:**
1. Backend implementa primero (httpOnly cookies, CSRF)
2. Frontend adapta después (remove sessionStorage, add CSRF headers)
3. Deploy coordinado (backend → frontend)
4. Testing exhaustivo post-deploy

---

## 🔗 Referencias

- [FastAPI Security Docs](https://fastapi.tiangolo.com/tutorial/security/)
- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [SQLAlchemy Security](https://docs.sqlalchemy.org/en/14/faq/security.html)
- Frontend ROADMAP: `../RyderCupWeb/ROADMAP.md`

---

**Última revisión:** 27 Nov 2025
**Próxima revisión:** Después de v1.8.0 (Security Release)
