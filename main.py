"""
Ryder Cup Manager - Main Application

Punto de entrada de la aplicación FastAPI.
"""

import os

from dotenv import load_dotenv

load_dotenv()  # Cargar variables de entorno desde .env

# All imports below must be after load_dotenv() to access environment variables
# ruff: noqa: I001 - Import sorting disabled after load_dotenv()
import secrets  # noqa: E402
from contextlib import asynccontextmanager  # noqa: E402

import uvicorn  # noqa: E402
from fastapi import Depends, FastAPI, HTTPException, Request, status  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html  # noqa: E402
from fastapi.security import HTTPBasic, HTTPBasicCredentials  # noqa: E402
from pydantic import BaseModel  # noqa: E402
from secure import Secure  # noqa: E402
from slowapi import _rate_limit_exceeded_handler  # noqa: E402
from slowapi.errors import RateLimitExceeded  # noqa: E402

from src.config.cors_config import get_cors_config  # noqa: E402
from src.config.rate_limit import limiter  # noqa: E402
from src.config.sentry_config import init_sentry  # noqa: E402
from src.config.settings import settings  # noqa: E402
from src.modules.competition.infrastructure.api.v1 import (
    competition_routes,
    enrollment_routes,
)  # noqa: E402
from src.modules.competition.infrastructure.persistence.sqlalchemy.mappers import (  # noqa: E402
    start_mappers as start_competition_mappers,
)
from src.modules.user.infrastructure.api.v1 import (
    auth_routes,
    device_routes,
    handicap_routes,
    user_routes,
)  # noqa: E402
from src.modules.user.infrastructure.persistence.sqlalchemy.mappers import (
    start_mappers,
)  # noqa: E402
from src.shared.infrastructure.api.v1 import country_routes  # noqa: E402
from src.shared.infrastructure.http.correlation_middleware import (
    CorrelationMiddleware,
)  # noqa: E402
from src.shared.infrastructure.http.sentry_middleware import (
    SentryUserContextMiddleware,
)  # noqa: E402
from src.shared.infrastructure.middleware.csrf_middleware import (
    CSRFMiddleware,
)  # noqa: E402
from src.shared.infrastructure.persistence.sqlalchemy.country_mappers import (  # noqa: E402
    start_mappers as start_country_mappers,
)


@asynccontextmanager
async def lifespan(app: FastAPI):  # noqa: ARG001 - FastAPI requires this signature
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
        credentials.username.encode("utf8"), settings.DOCS_USERNAME.encode("utf8")
    )

    # Verificar password
    correct_password = secrets.compare_digest(
        credentials.password.encode("utf8"), settings.DOCS_PASSWORD.encode("utf8")
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
    lifespan=lifespan,
)

# Registrar el limiter en la app para que esté disponible en todos los endpoints
app.state.limiter = limiter

# Registrar el exception handler para RateLimitExceeded
# Cuando se excede el límite, se responde automáticamente con HTTP 429
# slowapi's handler is sync but FastAPI accepts both sync and async
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]

# ================================
# MIDDLEWARE STACK
# ================================
# Los middlewares se ejecutan en el orden INVERSO al que se registran:
# El último en añadirse es el primero en ejecutarse

# ================================
# SECURITY HEADERS MIDDLEWARE
# ================================
# Instanciar configuración de security headers
secure_headers = Secure()


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """
    Middleware para añadir Security Headers HTTP a todas las respuestas.

    OWASP Top 10 2021 Coverage:
    - A02: Cryptographic Failures (HSTS fuerza cifrado HTTPS)
    - A05: Security Misconfiguration
    """
    response = await call_next(request)
    secure_headers.framework.fastapi(response)
    return response


# ================================
# CORS MIDDLEWARE (v1.8.0)
# ================================
# Aplicar middleware CORS con configuración centralizada
# IMPORTANTE: Debe ir DESPUÉS de security headers para que CORS
# se aplique ANTES (orden inverso de ejecución)
app.add_middleware(CORSMiddleware, **get_cors_config())

# ================================
# CSRF PROTECTION MIDDLEWARE (v1.13.0)
# ================================
# Valida CSRF tokens en requests no seguros (POST, PUT, PATCH, DELETE)
# Exime GET, HEAD, OPTIONS, rutas públicas (/health, /docs)
# IMPORTANTE: Debe ir ANTES de que los endpoints procesen los requests
app.add_middleware(CSRFMiddleware)

# Sentry User Context Middleware (captura usuario de JWT para eventos)
app.add_middleware(SentryUserContextMiddleware)

# Correlation ID Middleware (debe capturar todos los requests)
app.add_middleware(CorrelationMiddleware)

# Debug middleware para ver requests CORS (solo en desarrollo)
# Este debe ir AL FINAL para que se ejecute PRIMERO y vea todo
ENV = os.getenv("ENVIRONMENT", "development").lower()
if ENV != "production":

    @app.middleware("http")
    async def debug_cors_requests(request, call_next):
        origin = request.headers.get("origin", "N/A")
        method = request.method

        # Log de peticiones con origen
        if origin != "N/A":
            print(f"🌍 {method} request to: {request.url.path}")
            print(f"   Origin: {origin}")

            if method == "OPTIONS":
                print(
                    f"   Access-Control-Request-Method: {request.headers.get('access-control-request-method', 'N/A')}"
                )
                print(
                    f"   Access-Control-Request-Headers: {request.headers.get('access-control-request-headers', 'N/A')}"
                )

        response = await call_next(request)

        # Log de respuesta CORS
        if origin != "N/A":
            print(f"   Response status: {response.status_code}")
            cors_headers = {
                k: v
                for k, v in response.headers.items()
                if "access-control" in k.lower() or "vary" in k.lower()
            }
            if cors_headers:
                print(f"   CORS headers: {cors_headers}")
            else:
                print("   ⚠️  NO CORS headers in response!")

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
    device_routes.router,
    prefix="/api/v1",
    tags=["Devices"],
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
async def get_documentation(
    username: str = Depends(verify_docs_credentials),
):  # noqa: ARG001
    """Swagger UI protegido con HTTP Basic Auth."""
    return get_swagger_ui_html(openapi_url="/openapi.json", title="API Docs")


@app.get("/redoc", include_in_schema=False)
async def get_redoc_documentation(
    username: str = Depends(verify_docs_credentials),
):  # noqa: ARG001
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
        description="API para gestion de torneos tipo Ryder Cup entre amigos",
    )


if __name__ == "__main__":
    # Para reload=True necesitamos pasar la app como string
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
