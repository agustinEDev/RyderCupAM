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
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel

from src.config.settings import settings
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Gestor de ciclo de vida de la aplicación.
    - Inicia los mappers de SQLAlchemy al arrancar.
    - (Aquí se podrían añadir otras tareas de inicio/apagado, como conectar a Redis).
    """
    print("INFO:     Iniciando aplicación y configurando mappers...")
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

# Configurar CORS para permitir peticiones desde el frontend
# Leemos orígenes desde la variable de entorno FRONTEND_ORIGINS
FRONTEND_ORIGINS = os.getenv("FRONTEND_ORIGINS", "")
allowed_origins = [origin.strip() for origin in FRONTEND_ORIGINS.split(",") if origin.strip()]

# Incluir localhost en desarrollo (no en producción)
ENV = os.getenv("ENVIRONMENT", "development").lower()
if ENV != "production":
    allowed_origins.extend([
        "http://localhost:3000",   # React/Next.js
        "http://127.0.0.1:3000",   # React/Next.js
        "http://localhost:5173",   # Vite
        "http://127.0.0.1:5173",   # Vite
        "http://localhost:5174",   # Vite (fallback)
        "http://127.0.0.1:5174",   # Vite (fallback)
        "http://localhost:8080",   # Kubernetes port-forward (frontend)
        "http://127.0.0.1:8080",   # Kubernetes port-forward (frontend)
    ])

# Eliminar duplicados conservando orden
allowed_origins = list(dict.fromkeys(allowed_origins))

# Si no hay orígenes configurados, dejar solo localhost (modo seguro por defecto)
if not allowed_origins:
    allowed_origins = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173"
    ]

# Debug: imprimir allowed_origins al iniciar
print(f"🔒 CORS allowed_origins: {allowed_origins}")

# Debug middleware para ver requests OPTIONS (solo en desarrollo)
if ENV != "production":
    @app.middleware("http")
    async def debug_options_requests(request, call_next):
        if request.method == "OPTIONS":
            print(f"🔍 OPTIONS request to: {request.url.path}")
            print(f"   Origin: {request.headers.get('origin', 'N/A')}")
            print(f"   Access-Control-Request-Method: {request.headers.get('access-control-request-method', 'N/A')}")
            print(f"   Access-Control-Request-Headers: {request.headers.get('access-control-request-headers', 'N/A')}")
            print(f"   All headers: {dict(request.headers)}")
        response = await call_next(request)
        if request.method == "OPTIONS":
            print(f"   Response status: {response.status_code}")
        return response

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    max_age=3600,
)

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
    tags=["Competitions"],
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
