"""
Ryder Cup Manager - Main Application

Punto de entrada de la aplicación FastAPI.
"""
import os

from dotenv import load_dotenv

load_dotenv()  # Cargar variables de entorno desde .env
import secrets
from contextlib import asynccontextmanager

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from secure import Secure

from src.config.settings import settings
from src.config.sentry_config import init_sentry
from src.modules.competition.infrastructure.api.v1 import competition_routes, enrollment_routes
from src.modules.competition.infrastructure.persistence.sqlalchemy.mappers import (
    start_mappers as start_competition_mappers,
)
from src.modules.user.infrastructure.api.v1 import auth_routes, handicap_routes, user_routes
from src.modules.user.infrastructure.persistence.sqlalchemy.mappers import start_mappers
from src.shared.infrastructure.api.v1 import country_routes
from src.shared.infrastructure.persistence.sqlalchemy.country_mappers import (
    start_mappers as start_country_mappers,
)
from src.config.rate_limit import limiter
from src.config.cors_config import get_cors_config
from src.shared.infrastructure.http.correlation_middleware import CorrelationMiddleware
from src.shared.infrastructure.http.sentry_middleware import SentryUserContextMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Gestor de ciclo de vida de la aplicación.
    - Inicializa Sentry para error tracking y performance monitoring
    - Inicia los mappers de SQLAlchemy al arrancar.
    - (Aquí se podrían añadir otras tareas de inicio/apagado, como conectar a Redis).
    """
    print("INFO:     Iniciando aplicación y configurando mappers...")

    # Inicializar Sentry (v1.8.0 - Task 10)
    init_sentry()

    start_mappers()  # User module mappers
    start_country_mappers()  # Shared domain (Country) mappers
    start_competition_mappers()  # Competition module mappers
    yield
    print("INFO:     Apagando aplicación...")


# HTTP Basic Security para proteger /docs
security = HTTPBasic()

def verify_docs_credentials(credentials: HTTPBasicCredentials = Depends(security)):
    """
    Verifica las credenciales HTTP Basic para acceder a /docs y /redoc.

    Las credenciales se configuran en variables de entorno:
    - DOCS_USERNAME
    - DOCS_PASSWORD

    Raises:
        HTTPException 401: Si las credenciales son incorrectas o no están configuradas
    """
    # Si no están configuradas las credenciales, denegar acceso
    if not settings.DOCS_USERNAME or not settings.DOCS_PASSWORD:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Documentación no disponible - credenciales no configuradas",
            headers={"WWW-Authenticate": "Basic"},
        )

    # Verificar username
    correct_username = secrets.compare_digest(
        credentials.username.encode("utf8"),
        settings.DOCS_USERNAME.encode("utf8")
    )

    # Verificar password
    correct_password = secrets.compare_digest(
        credentials.password.encode("utf8"),
        settings.DOCS_PASSWORD.encode("utf8")
    )

    if not (correct_username and correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales incorrectas",
            headers={"WWW-Authenticate": "Basic"},
        )

    return credentials.username


class HealthResponse(BaseModel):
    """Response model para el health check."""
    message: str
    version: str
    status: str
    docs: str
    description: str

# Crear la app, registrando el gestor de ciclo de vida 'lifespan'
# Deshabilitamos docs_url y redoc_url para crear endpoints protegidos manualmente
app = FastAPI(
    title="Ryder Cup Manager",
    description="API para gestion de torneos tipo Ryder Cup entre amigos",
    version="1.0.0",
    docs_url=None,  # Deshabilitado - usaremos endpoint protegido
    redoc_url=None,  # Deshabilitado - usaremos endpoint protegido
    lifespan=lifespan
)

# Registrar el limiter en la app para que esté disponible en todos los endpoints
app.state.limiter = limiter

# Registrar el exception handler para RateLimitExceeded
# Cuando se excede el límite, se responde automáticamente con HTTP 429
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ================================
# CORS MIDDLEWARE (v1.8.0)
# ================================
# Configurar CORS (Cross-Origin Resource Sharing) para permitir
# peticiones desde frontends autorizados únicamente.
#
# Características:
# - Whitelist estricta de orígenes (no wildcards)
# - Validación automática de esquemas (http/https)
# - Separación clara desarrollo/producción
# - allow_credentials=True para cookies httpOnly
#
# OWASP Coverage:
# - A05: Security Misconfiguration (whitelist estricta)
# - A01: Broken Access Control (control de acceso por origen)
#
# Configuración centralizada en: src/config/cors_config.py

# Debug middleware para ver requests OPTIONS (solo en desarrollo)
ENV = os.getenv("ENVIRONMENT", "development").lower()
if ENV != "production":
    @app.middleware("http")
    async def debug_options_requests(request, call_next):
        if request.method == "OPTIONS":
            print(f"🔍 OPTIONS request to: {request.url.path}")
            print(f"   Origin: {request.headers.get('origin', 'N/A')}")
            print(f"   Access-Control-Request-Method: {request.headers.get('access-control-request-method', 'N/A')}")
            print(f"   Access-Control-Request-Headers: {request.headers.get('access-control-request-headers', 'N/A')}")
        response = await call_next(request)
        if request.method == "OPTIONS":
            print(f"   Response status: {response.status_code}")
        return response

# Correlation ID Middleware (debe ir PRIMERO para capturar todos los requests)
app.add_middleware(CorrelationMiddleware)

# Sentry User Context Middleware (captura usuario de JWT para eventos)
app.add_middleware(SentryUserContextMiddleware)

# Aplicar middleware CORS con configuración centralizada
app.add_middleware(CORSMiddleware, **get_cors_config())

# ================================
# SECURITY HEADERS MIDDLEWARE
# ================================
# Configurar Security Headers HTTP para proteger contra:
# - XSS (Cross-Site Scripting)
# - Clickjacking
# - MIME-sniffing
# - MITM (Man-in-the-Middle) attacks
# - Inyección de recursos maliciosos
#
# IMPORTANTE: Este middleware debe ir DESPUÉS de CORS
# para que los headers de seguridad se añadan correctamente

# Instanciar configuración de security headers con valores por defecto
# La biblioteca 'secure' proporciona headers seguros pre-configurados
secure_headers = Secure()

@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """
    Middleware para añadir Security Headers HTTP a todas las respuestas.

    Headers añadidos por defecto (biblioteca 'secure'):
    - Strict-Transport-Security (HSTS): max-age=63072000; includeSubdomains
      → Fuerza HTTPS durante 2 años, previene MITM downgrade attacks
    - X-Frame-Options: SAMEORIGIN
      → Previene clickjacking, solo permite iframes del mismo origen
    - X-Content-Type-Options: nosniff
      → Previene MIME-sniffing, fuerza respeto al Content-Type declarado
    - Referrer-Policy: no-referrer, strict-origin-when-cross-origin
      → Controla información de referer enviada en requests
    - X-XSS-Protection: 0
      → Desactivado (obsoleto en navegadores modernos, puede causar vulnerabilidades)
    - Cache-Control: no-store
      → Previene cacheo de respuestas sensibles

    OWASP Top 10 2021 Coverage:
    - A02: Cryptographic Failures (HSTS fuerza cifrado HTTPS)
    - A03: Injection (X-XSS-Protection, aunque obsoleto)
    - A04: Insecure Design (X-Frame-Options previene clickjacking)
    - A05: Security Misconfiguration (todos los headers)
    - A07: Authentication Failures (X-Frame-Options en login, Cache-Control en tokens)

    Nota: En desarrollo (HTTP), HSTS será ignorado por el navegador.
          Solo es efectivo en producción con HTTPS.
    """
    response = await call_next(request)

    # Añadir todos los security headers a la respuesta
    headers_dict = secure_headers.headers()
    for header_name, header_value in headers_dict.items():
        response.headers[header_name] = header_value

    return response

# Incluir los routers de la API
app.include_router(
    auth_routes.router,
    prefix="/api/v1/auth",
    tags=["Authentication"],
)

app.include_router(
    handicap_routes.router,
    prefix="/api/v1",
    tags=["Handicaps"],
)

app.include_router(
    user_routes.router,
    prefix="/api/v1/users",
    tags=["Users"],
)

app.include_router(
    competition_routes.router,
    prefix="/api/v1/competitions",
)

app.include_router(
    country_routes.router,
    prefix="/api/v1/countries",
    tags=["Countries"],
)

app.include_router(
    enrollment_routes.router,
    prefix="/api/v1",
    tags=["Enrollments"],
)

# Endpoints protegidos de documentación con HTTP Basic Auth
@app.get("/docs", include_in_schema=False)
async def get_documentation(username: str = Depends(verify_docs_credentials)):
    """Swagger UI protegido con HTTP Basic Auth."""
    return get_swagger_ui_html(openapi_url="/openapi.json", title="API Docs")


@app.get("/redoc", include_in_schema=False)
async def get_redoc_documentation(username: str = Depends(verify_docs_credentials)):
    """ReDoc UI protegido con HTTP Basic Auth."""
    return get_redoc_html(openapi_url="/openapi.json", title="API Docs - ReDoc")


# Endpoint raíz para health check y metadata básica
@app.get("/", response_model=HealthResponse)
async def root() -> HealthResponse:
    return HealthResponse(
        message="Ryder Cup Manager API",
        version="1.0.0",
        status="running",
        docs="Visita /docs para la documentacion interactiva",
        description="API para gestion de torneos tipo Ryder Cup entre amigos"
    )

if __name__ == "__main__":
    # Para reload=True necesitamos pasar la app como string
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
