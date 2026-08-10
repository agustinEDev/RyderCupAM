"""
Ryder Cup Manager - Main Application

Punto de entrada de la aplicación FastAPI.
"""

import os

from dotenv import load_dotenv

load_dotenv()  # Cargar variables de entorno desde .env

# All imports below must be after load_dotenv() to access environment variables

import secrets  # noqa: E402
from contextlib import asynccontextmanager  # noqa: E402

import uvicorn  # noqa: E402
from fastapi import Depends, FastAPI, HTTPException, Request, status  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html  # noqa: E402
from fastapi.responses import JSONResponse  # noqa: E402
from fastapi.security import HTTPBasic, HTTPBasicCredentials  # noqa: E402
from pydantic import BaseModel  # noqa: E402
from secure import Secure  # noqa: E402
from slowapi import _rate_limit_exceeded_handler  # noqa: E402
from slowapi.errors import RateLimitExceeded  # noqa: E402

from src.config.cors_config import get_cors_config  # noqa: E402
from src.config.rate_limit import limiter  # noqa: E402
from src.config.sentry_config import init_sentry  # noqa: E402
from src.config.settings import settings  # noqa: E402
from src.config.version import (  # noqa: E402
    APP_VERSION,
    get_deployed_branch,
    get_deployed_commit,
    get_environment,
)
from src.modules.competition.infrastructure.api.v1 import (  # noqa: E402
    competition_crud_routes,
    competition_golf_course_routes,
    competition_state_routes,
    enrollment_routes,
    invitation_routes,
    round_match_routes,
    scoring_routes,
)
from src.modules.competition.infrastructure.persistence.sqlalchemy.mappers import (  # noqa: E402
    start_mappers as start_competition_mappers,
)
from src.modules.golf_course.infrastructure.api.v1 import golf_course_routes  # noqa: E402
from src.modules.golf_course.infrastructure.persistence.mappers.golf_course_mapper import (  # noqa: E402
    start_golf_course_mappers,
)
from src.modules.quick_match.infrastructure.api.v1 import quick_match_routes  # noqa: E402
from src.modules.quick_match.infrastructure.persistence.mappers.quick_match_mapper import (  # noqa: E402
    start_quick_match_mappers,
)
from src.modules.social.infrastructure.api.v1 import friend_routes  # noqa: E402
from src.modules.social.infrastructure.api.v1 import profile_photo_routes  # noqa: E402
from src.modules.social.infrastructure.api.v1 import profile_routes  # noqa: E402
from src.modules.social.infrastructure.persistence.mappers.activity_event_mapper import (  # noqa: E402
    start_activity_event_mappers,
)
from src.modules.social.infrastructure.persistence.mappers.profile_photo_mapper import (  # noqa: E402
    start_profile_photo_mappers,
)
from src.modules.social.infrastructure.persistence.mappers.friendship_mapper import (  # noqa: E402
    start_social_mappers,
)
from src.modules.support.infrastructure.api.v1 import support_routes  # noqa: E402
from src.modules.user.application.use_cases.upload_avatar_use_case import (  # noqa: E402
    MAX_UPLOAD_BYTES,
)
from src.modules.user.infrastructure.api.v1 import (  # noqa: E402
    admin_routes,
    auth_routes,
    avatar_routes,
    device_routes,
    google_auth_routes,
    handicap_routes,
    user_routes,
)
from src.modules.user.infrastructure.persistence.sqlalchemy.mappers import (  # noqa: E402
    start_mappers,
)
from src.shared.infrastructure.api.v1 import country_routes  # noqa: E402
from src.shared.infrastructure.http.correlation_middleware import (  # noqa: E402
    CorrelationMiddleware,
)
from src.shared.infrastructure.http.sentry_middleware import (  # noqa: E402
    SentryUserContextMiddleware,
)
from src.shared.infrastructure.middleware.csrf_middleware import (  # noqa: E402
    CSRFMiddleware,
)
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
    start_golf_course_mappers()  # Golf Course module mappers (before Competition - dependency)
    start_competition_mappers()  # Competition module mappers (depends on GolfCourse)
    start_social_mappers()  # Social module mappers (depends on User)
    start_profile_photo_mappers()  # Profile photo gallery (depends on User)
    start_activity_event_mappers()  # Activity feed (depends on User)
    start_quick_match_mappers()  # QuickMatch module mappers (depends on User, GolfCourse)
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
    """Response model para el endpoint raiz."""

    message: str
    version: str
    status: str
    docs: str
    description: str


class DeploymentHealthResponse(BaseModel):
    """Response model para /health: identifica el despliegue concreto."""

    status: str
    version: str
    commit: str
    branch: str
    environment: str


# Crear la app, registrando el gestor de ciclo de vida 'lifespan'
# Deshabilitamos docs_url y redoc_url para crear endpoints protegidos manualmente
app = FastAPI(
    title="Ryder Cup Manager",
    description="API para gestion de torneos tipo Ryder Cup entre amigos",
    version=APP_VERSION,
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
    # Algunas rutas (p.ej. las imágenes de preset de avatar, assets estáticos
    # inmutables) fijan su propio Cache-Control antes de llegar aquí; sin esto,
    # el Cache-Control: no-store por defecto de `secure` lo pisaría siempre.
    route_cache_control = response.headers.get("cache-control")
    secure_headers.framework.fastapi(response)
    if route_cache_control is not None:
        response.headers["cache-control"] = route_cache_control
    return response


# ================================
# AVATAR UPLOAD SIZE GUARD (Content-Length fast-fail)
# ================================
# Rechaza subidas de avatar por encima del límite ANTES de que FastAPI/Starlette
# parseen el multipart body: sin esto, un archivo enorme se bufferiza igualmente
# durante el parseo del form (UploadFile ya se construye a partir del cuerpo ya
# parseado), y el chequeo de tamaño dentro del endpoint llega demasiado tarde
# para evitar ese coste. Solo inspecciona la cabecera (no toca el body), así
# que su orden relativo a los demás middlewares no importa.
# Nota: Content-Length es lo que el cliente DECLARA, no una garantía absoluta
# (podría mentir, o usar chunked encoding sin esa cabecera) — la lectura por
# trozos con corte temprano en el propio endpoint sigue siendo la protección
# real; esto es un fast-fail adicional para el caso común.
_AVATAR_UPLOAD_PATH = "/api/v1/users/me/avatar/upload"
# Content-Length cubre el multipart body ENTERO (boundaries + cabeceras de cada
# parte), no solo los bytes del fichero — un archivo justo en el límite (o algo
# por debajo) puede declarar un tamaño total ligeramente mayor que
# MAX_UPLOAD_BYTES por ese framing. Se permite un margen para no rechazar
# subidas válidas; el chequeo exacto por bytes reales sigue en el endpoint.
_MAX_AVATAR_MULTIPART_OVERHEAD_BYTES = 16 * 1024


@app.middleware("http")
async def limit_avatar_upload_content_length(request: Request, call_next):
    if request.url.path == _AVATAR_UPLOAD_PATH and request.method == "POST":
        content_length = request.headers.get("content-length")
        if content_length is not None:
            try:
                declared_size = int(content_length)
            except ValueError:
                declared_size = None
            if (
                declared_size is not None
                and declared_size > MAX_UPLOAD_BYTES + _MAX_AVATAR_MULTIPART_OVERHEAD_BYTES
            ):
                return JSONResponse(
                    status_code=413,
                    content={
                        "detail": (
                            "El archivo supera el tamaño máximo permitido "
                            f"({MAX_UPLOAD_BYTES // (1024 * 1024)}MB)"
                        )
                    },
                )
    return await call_next(request)


# ================================
# CSRF PROTECTION MIDDLEWARE (v1.13.0)
# ================================
# Valida CSRF tokens en requests no seguros (POST, PUT, PATCH, DELETE)
# Exime GET, HEAD, OPTIONS, rutas públicas (/health, /docs)
# Se registra ANTES de CORS para que CORS envuelva CSRF en ejecución
app.add_middleware(CSRFMiddleware)

# ================================
# CORS MIDDLEWARE (v1.8.0)
# ================================
# Registrado DESPUÉS de CSRF → se ejecuta PRIMERO (orden inverso)
# Así cualquier respuesta (incluidos 403 de CSRF) lleva headers CORS
app.add_middleware(CORSMiddleware, **get_cors_config())

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
    google_auth_routes.router,
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
    admin_routes.router,
    prefix="/api/v1/admin",
    tags=["Admin"],
)

app.include_router(
    avatar_routes.router,
    prefix="/api/v1",
    tags=["Avatars"],
)

app.include_router(
    device_routes.router,
    prefix="/api/v1",
    tags=["Devices"],
)

app.include_router(
    competition_crud_routes.router,
    prefix="/api/v1/competitions",
)

app.include_router(
    competition_state_routes.router,
    prefix="/api/v1/competitions",
)

app.include_router(
    competition_golf_course_routes.router,
    prefix="/api/v1/competitions",
)

app.include_router(
    round_match_routes.router,
    prefix="/api/v1/competitions",
)

app.include_router(
    scoring_routes.router,
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

app.include_router(
    invitation_routes.router,
    prefix="/api/v1",
    tags=["Invitations"],
)

app.include_router(
    friend_routes.router,
    prefix="/api/v1",
    tags=["Friends"],
)

app.include_router(
    profile_routes.router,
    prefix="/api/v1",
    tags=["Profiles & Feed"],
)

app.include_router(
    profile_photo_routes.router,
    prefix="/api/v1",
    tags=["Profile Photos"],
)

app.include_router(
    quick_match_routes.router,
    prefix="/api/v1",
    tags=["Quick Matches"],
)

app.include_router(
    golf_course_routes.router,
    prefix="/api/v1",
    tags=["Golf Courses"],
)

app.include_router(
    support_routes.router,
    prefix="/api/v1/support",
    tags=["Support"],
)


# Endpoints protegidos de documentación con HTTP Basic Auth
@app.get("/docs", include_in_schema=False)
async def get_documentation(
    username: str = Depends(verify_docs_credentials),  # noqa: ARG001
):
    """Swagger UI protegido con HTTP Basic Auth."""
    return get_swagger_ui_html(openapi_url="/openapi.json", title="API Docs")


@app.get("/redoc", include_in_schema=False)
async def get_redoc_documentation(
    username: str = Depends(verify_docs_credentials),  # noqa: ARG001
):
    """ReDoc UI protegido con HTTP Basic Auth."""
    return get_redoc_html(openapi_url="/openapi.json", title="API Docs - ReDoc")


# Endpoint raíz para health check y metadata básica
@app.get("/", response_model=HealthResponse)
async def root() -> HealthResponse:
    return HealthResponse(
        message="Ryder Cup Manager API",
        version=APP_VERSION,
        status="running",
        docs="Visita /docs para la documentacion interactiva",
        description="API para gestion de torneos tipo Ryder Cup entre amigos",
    )


# Health check de despliegue: responde QUE version y QUE commit estan corriendo,
# que es lo unico que permite verificar si una release ha llegado a produccion.
# `/` no sirve para eso porque no distingue un despliegue de otro.
@app.get("/health", response_model=DeploymentHealthResponse)
async def health() -> DeploymentHealthResponse:
    return DeploymentHealthResponse(
        status="ok",
        version=APP_VERSION,
        commit=get_deployed_commit(),
        branch=get_deployed_branch(),
        environment=get_environment(),
    )


if __name__ == "__main__":
    # Para reload=True necesitamos pasar la app como string
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
