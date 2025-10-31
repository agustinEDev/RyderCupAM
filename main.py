# -*- coding: utf-8 -*-
"""
Ryder Cup Manager - Main Application

Punto de entrada de la aplicación FastAPI.
"""

from fastapi import FastAPI
from pydantic import BaseModel
import uvicorn


class HealthResponse(BaseModel):
    """Response model para el health check."""
    message: str
    version: str
    status: str
    docs: str
    description: str

# Crear la app
app = FastAPI(
    title="Ryder Cup Manager",
    description="API para gestion de torneos tipo Ryder Cup entre amigos",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
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