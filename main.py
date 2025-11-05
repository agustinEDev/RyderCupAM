# -*- coding: utf-8 -*-
"""
Ryder Cup Manager - Main Application

Punto de entrada de la aplicación FastAPI.
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from pydantic import BaseModel
import uvicorn

from src.modules.user.infrastructure.api.v1 import auth_routes
from src.modules.user.infrastructure.persistence.sqlalchemy.mappers import start_mappers


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


class HealthResponse(BaseModel):
    """Response model para el health check."""
    message: str
    version: str
    status: str
    docs: str
    description: str

# Crear la app, registrando el gestor de ciclo de vida 'lifespan'
app = FastAPI(
    title="Ryder Cup Manager",
    description="API para gestion de torneos tipo Ryder Cup entre amigos",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan  # <-- Forma moderna de manejar eventos de startup/shutdown
)

# Incluir los routers de la API
app.include_router(
    auth_routes.router,
    prefix="/api/v1/auth",
    tags=["Authentication"],
)

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
