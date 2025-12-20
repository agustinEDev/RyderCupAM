# 🔐 Guía de Implementación de Seguridad - v1.8.0

> **⚠️ DOCUMENTO TEMPORAL:** Este archivo debe **ELIMINARSE** una vez completadas todas las tareas de seguridad de v1.8.0.
>
> **Estado:** ❌ Pendiente de implementación
>
> **Progreso:** 0/9 tareas completadas

---

## 📋 Checklist de Implementación

- [ ] 1. Rate Limiting (SlowAPI) - 2-3h
- [ ] 2. Security Headers (python-secure) - 1-2h
- [ ] 3. httpOnly Cookies (JWT) - 6-8h
- [ ] 4. CSRF Protection - 4-6h (evaluar necesidad)
- [ ] 5. Validación de Inputs (Pydantic) - 4-6h
- [ ] 6. Security Logging - 3-4h
- [ ] 7. SQL Injection Audit - 1h
- [ ] 8. Sentry Backend - 3-4h
- [ ] 9. Auditoría de Dependencias - 2h

---

## 🔴 1. Rate Limiting (SlowAPI)

### Instalación
```bash
pip install slowapi
```

### Configuración Global
```python
# src/main.py
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
```

### Aplicar en Endpoints
```python
# src/modules/auth/infrastructure/api/auth_routes.py
@router.post("/login")
@limiter.limit("5/minute")
async def login(credentials: LoginRequest, request: Request):
    ...

@router.post("/register")
@limiter.limit("3/hour")
async def register(user_data: RegisterRequest, request: Request):
    ...
```

### Rate Limits Recomendados

| Endpoint | Límite | Motivo |
|----------|--------|--------|
| `POST /api/v1/auth/login` | 5/minute | Anti brute-force |
| `POST /api/v1/auth/register` | 3/hour | Anti spam |
| `POST /api/v1/auth/verify-email` | 10/hour | Anti abuse |
| `POST /api/v1/auth/forgot-password` | 3/hour | Anti enumeration |
| `POST /api/v1/competitions/` | 10/hour | Anti spam |
| `POST /api/v1/enrollments/` | 20/hour | Uso normal |
| `POST /api/v1/handicaps/update` | 5/hour | RFEG API costoso |
| `GET /api/v1/competitions` | 100/minute | Lectura intensiva |
| `GET /api/v1/users/{id}` | 60/minute | Perfiles públicos |

### Testing
```python
# tests/test_rate_limiting.py
def test_login_rate_limit():
    for i in range(6):
        response = client.post("/api/v1/auth/login", json={
            "email": "test@example.com",
            "password": "wrong"
        })
        if i < 5:
            assert response.status_code in [200, 401]
        else:
            assert response.status_code == 429
```

---

## 🔴 2. Security Headers (python-secure)

### Instalación
```bash
pip install secure
```

### Implementación
```python
# src/main.py
from secure import Secure

secure_headers = Secure()

@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    secure_headers.framework.fastapi(response)
    return response
```

### Headers Aplicados
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `Strict-Transport-Security: max-age=31536000; includeSubDomains`
- `Referrer-Policy: strict-origin-when-cross-origin`
- `Permissions-Policy: geolocation=(), microphone=(), camera=()`

### Verificación
```bash
curl -I https://rydercup-api.onrender.com/api/v1/health
```

---

## 🔴 3. httpOnly Cookies (JWT Tokens)

### Problema Actual
```python
# ❌ VULNERABLE: Tokens en response body
@router.post("/login")
async def login(credentials: LoginRequest):
    token = create_access_token(user.id)
    return {"access_token": token, "user": user_dto}
```

### Solución
```python
# ✅ SEGURO: Tokens en httpOnly cookies
from fastapi import Response

@router.post("/login")
async def login(credentials: LoginRequest, response: Response):
    token = create_access_token(user.id)

    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=3600,
        path="/",
    )

    return {"user": user_dto}
```

### Middleware de Autenticación
```python
# src/shared/infrastructure/middleware/auth_middleware.py
async def get_current_user(request: Request):
    # Prioridad: cookies > header (para migración gradual)
    token = request.cookies.get("access_token")
    if not token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]

    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    return decode_and_validate_token(token)
```

### CORS Configuration
```python
# src/main.py
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "https://rydercup.com"],
    allow_credentials=True,  # REQUERIDO para cookies
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### Plan de Migración
1. **Semana 1:** Backend implementa (mantiene compatibilidad headers)
2. **Semana 2:** Frontend migra a `credentials: 'include'`
3. **Semana 3:** Backend elimina soporte headers Authorization

---

## 🟡 4. CSRF Protection

### Fase 1: SameSite Cookies (incluido en punto 3)
```python
response.set_cookie(key="access_token", samesite="lax")  # 80% protección
```

### Fase 2: CSRF Tokens (OPCIONAL - evaluar después)
```bash
pip install fastapi-csrf-protect
```

```python
from fastapi_csrf_protect import CsrfProtect

@router.post("/competitions/")
async def create_competition(
    competition: CompetitionCreate,
    csrf_protect: CsrfProtect = Depends()
):
    await csrf_protect.validate_csrf(request)
    # ... lógica
```

**Decisión:** Implementar solo si análisis de riesgo lo justifica después de v1.8.0

---

## 🟡 5. Validación de Inputs (Pydantic Mejorada)

### Mejoras Necesarias
```python
# src/modules/competition/application/dto/competition_dto.py
from pydantic import BaseModel, Field, validator

class CompetitionCreate(BaseModel):
    name: str = Field(..., min_length=3, max_length=100)
    location: str = Field(..., min_length=3, max_length=200)
    max_players: int = Field(..., ge=2, le=100)

    @validator('name', 'location')
    def sanitize_html(cls, v):
        if '<' in v or '>' in v:
            raise ValueError('Field cannot contain HTML tags')
        return v.strip()
```

### Por Módulo

| Módulo | DTO | Validaciones |
|--------|-----|--------------|
| Auth | RegisterRequest | Email format, password strength, name lengths |
| User | UserUpdate | Name lengths (1-50), no HTML tags |
| Competition | CompetitionCreate | Name (3-100), location (3-200), max_players (2-100) |
| Enrollment | EnrollmentRequest | Valid UUID format |
| Handicap | HandicapUpdate | Range (0.0-54.0), RFEG license format |

---

## 🟡 6. Security Logging y Auditoría

### Implementación
```python
# src/shared/infrastructure/logging/security_logger.py
import logging

security_logger = logging.getLogger("security")
security_logger.setLevel(logging.INFO)

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
```

### Eventos Críticos

| Evento | Nivel | Información |
|--------|-------|-------------|
| Login success | INFO | user_id, email, ip, timestamp |
| Login failure | WARNING | email, ip, timestamp |
| Register | INFO | user_id, email, ip, country_code |
| Password change | INFO | user_id, ip |
| Email verification | INFO | user_id, email, ip |
| Competition created | INFO | user_id, competition_id, name |
| Rate limit exceeded | WARNING | endpoint, ip, timestamp |

---

## 🟡 7. SQL Injection - Auditoría

### Verificación
```bash
grep -r "text(" src/
grep -r "execute(" src/
grep -r "raw_sql" src/
```

### Si se encuentra SQL raw
```python
# ✅ CORRECTO - Parametrización
from sqlalchemy import text
stmt = text("SELECT * FROM users WHERE email = :email")
result = await session.execute(stmt, {"email": email})

# ❌ INCORRECTO - String interpolation
stmt = text(f"SELECT * FROM users WHERE email = '{email}'")
```

---

## 🟢 8. Sentry Backend

### Instalación
```bash
pip install sentry-sdk[fastapi]
```

### Configuración
```python
# src/main.py
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration

sentry_sdk.init(
    dsn=os.getenv("SENTRY_DSN"),
    environment=os.getenv("ENVIRONMENT", "production"),
    release=f"rydercup-api@{VERSION}",
    integrations=[FastApiIntegration()],
    traces_sample_rate=0.1,
    before_send=filter_sensitive_data,
)

def filter_sensitive_data(event, hint):
    if 'request' in event:
        if 'headers' in event['request']:
            event['request']['headers'].pop('Authorization', None)
            event['request']['headers'].pop('Cookie', None)
    return event
```

---

## 🟢 9. Auditoría de Dependencias ✅ COMPLETADO (19 Dic 2025)

### Herramientas Instaladas
```bash
pip install safety==3.7.0 pip-audit==2.10.0
```

### CI/CD Integration (GitHub Actions)
- ✅ **safety** + **pip-audit** ejecutan en cada push/PR
- ✅ Pipeline **falla automáticamente** si encuentra CVEs críticos
- ✅ Reportes JSON guardados como artifacts (30 días)
- ✅ Ubicación: `.github/workflows/ci_cd_pipeline.yml` → Job `security_checks`

### Uso Local
```bash
# Escanear vulnerabilidades
safety scan
pip-audit

# Actualizar dependencias vulnerables
pip install "package>=fixed-version"
pytest tests/ -n auto  # Validar
```

### Resultados Actuales (19 Dic 2025)
- ✅ 6 CVEs detectados, 5 resueltos (83.3%)
- ✅ Actualizaciones: fastapi 0.125.0, starlette 0.50.0, urllib3 2.6.0, filelock 3.20.1
- ⏳ CVE-2024-23342 (ecdsa): Sin fix, bajo impacto (no usamos ECDSA)
- ✅ 819/819 tests pasando

---

## Tarea 12: Security Tests Suite ✅ COMPLETADO

**Fecha:** 19 Dic 2025
**Tiempo:** 4 horas
**Puntuación OWASP:** A01/A03/A04/A07 - Testing Coverage

### Implementación

**Archivos Creados:**
- `tests/security/__init__.py`
- `tests/security/test_rate_limiting_security.py` (293 líneas, 7 tests)
- `tests/security/test_sql_injection_security.py` (181 líneas, 5 tests)
- `tests/security/test_xss_security.py` (235 líneas, 13 tests)
- `tests/security/test_auth_bypass_security.py` (289 líneas, 9 tests)

### Tests Implementados

**1. Rate Limiting Security (7 tests)**
- ✅ Login rate limit (5/minuto) - bloqueo después de 5 intentos
- ✅ Prevención de brute force con múltiples passwords
- ✅ Register rate limit (3/hora) - prevención de spam accounts
- ✅ Competition creation rate limit (10/hora)
- ✅ Bypass prevention (User-Agent, persistencia)
- ✅ Rate limit metadata en headers

**2. SQL Injection Security (5 tests)**
- ✅ SQL injection en campo email (login)
- ✅ SQL injection en campo password
- ✅ SQL injection en campos de registro
- ✅ SQL injection en nombre de competición
- ✅ ORM protection (consultas parametrizadas)

**3. XSS Security (13 tests)**
- ✅ XSS en campos de nombre/apellido
- ✅ XSS reflejado en mensajes de error
- ✅ XSS en nombre de competición
- ✅ XSS en descripción de competición
- ✅ Stored XSS en perfiles de usuario
- ✅ Sanitización HTML (tags, protocolos javascript:)
- ✅ Security headers (X-Content-Type-Options, X-Frame-Options)

**4. Authentication Bypass Security (9 tests)**
- ✅ Endpoints protegidos requieren autenticación
- ✅ Rechazo de tokens JWT inválidos
- ✅ Rechazo de tokens expirados
- ✅ Prevención de modificación de payload
- ✅ Prevención de algoritmo 'none'
- ✅ Logout invalida refresh tokens
- ✅ No reutilización de refresh tokens revocados
- ✅ Prevención de enumeración de usuarios
- ✅ Manejo seguro de race conditions

### Resultados

- ✅ **34 tests de seguridad** (100% pasando)
- ✅ Tiempo de ejecución: ~9 segundos
- ✅ Cobertura OWASP: A01, A03 (SQL+XSS), A04, A07
- ✅ Total de tests: 819 → 853 (+34)

### Integración CI/CD

Los tests de seguridad se ejecutan automáticamente en cada PR:
```bash
pytest tests/security/ -v
```

### Correcciones Aplicadas

Durante la implementación se corrigieron:
- Fixtures incorrectos (`test_user_token` → `authenticated_client`)
- Validación de respuestas 429 de SlowAPI
- Schema de competiciones con campos obligatorios
- Limpieza de cookies/headers para tests de manipulación de tokens
- Formato JSON para LogoutRequestDTO

---

## 📝 Orden de Implementación Recomendado

### Día 1-2: Protecciones Inmediatas
1. Rate limiting (SlowAPI)
2. Security headers (python-secure)
3. Testing básico
4. Deploy a staging

### Día 3-5: httpOnly Cookies (Backend)
1. Modificar auth routes
2. Actualizar auth middleware
3. Mantener compatibilidad headers
4. Testing exhaustivo

### Día 6-10: Frontend + Validaciones
1. Frontend migra a cookies
2. Testing conjunto
3. Mejorar validaciones Pydantic
4. Security logging
5. Deploy a producción

### Día 11-15: Refinamiento
1. Ajustar rate limits
2. Suite de tests de seguridad
3. Eliminar compatibilidad headers
4. **ELIMINAR ESTE DOCUMENTO**

---

## ✅ Criterios de Completitud

Este documento puede **ELIMINARSE** cuando:

- [x] Todas las 9 tareas estén completadas
- [x] Tests de seguridad pasando al 100%
- [x] Deploy en producción realizado
- [x] Monitoreo activo sin incidencias durante 1 semana
- [x] Documentación técnica actualizada en CLAUDE.md

---

**Última actualización:** 6 Dic 2025
**Responsable:** Backend Team
