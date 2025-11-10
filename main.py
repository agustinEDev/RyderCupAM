# -*- coding: utf-8 -*-
"""
Ryder Cup Manager - Main Application

Punto de entrada de la aplicación FastAPI.
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.openapi.docs import get_swagger_ui_html, get_redoc_html
from pydantic import BaseModel
import secrets
import uvicorn

from src.modules.user.infrastructure.api.v1 import auth_routes, handicap_routes, user_routes
from src.modules.user.infrastructure.persistence.sqlalchemy.mappers import start_mappers
from src.config.settings import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Gestor de ciclo de vida de la aplicación.
    - Inicia los mappers de SQLAlchemy al arrancar.
    - (Aquí se podrían añadir otras tareas de inicio/apagado, como conectar a Redis).
    """
    print("INFO:     Iniciando aplicación y configurando mappers...")
    start_mappers()
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
# En desarrollo: permite localhost:5173 (Vite dev server)
# En producción: configurar origins específicos según deployment
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # Vite dev server
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],  # Permite todos los métodos (GET, POST, PUT, DELETE, OPTIONS, etc.)
    allow_headers=["*"],  # Permite todos los headers
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
