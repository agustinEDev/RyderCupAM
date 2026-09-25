"""
Middleware que convierte un error no controlado en un 500 con cabeceras CORS.

Starlette atiende las excepciones no controladas en su `ServerErrorMiddleware`,
que va POR FUERA de todos los middlewares de la aplicación, CORS incluido. Su
500 salía sin `Access-Control-Allow-Origin`, el navegador lo bloqueaba como
«Failed to fetch» y el frontend lo contaba como falta de conexión (FE #710).
Registrar `add_exception_handler(Exception, ...)` no lo arregla: Starlette
engancha ese manejador al mismo middleware exterior.

Este middleware se registra DENTRO del CORS, así que su respuesta pasa por él.
La excepción se registra con su traza a nivel ERROR, que es lo que la
integración de logging de Sentry envía como evento: tragarla aquí no la
esconde. Y la respuesta no cuenta nada del error (OWASP A05).
"""

import logging
from collections.abc import Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class UnhandledErrorMiddleware(BaseHTTPMiddleware):
    """Responde 500 en JSON a cualquier excepción que llegue sin manejar."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        try:
            return await call_next(request)
        except Exception:
            logger.exception("Error no controlado en %s %s", request.method, request.url.path)
            return JSONResponse(
                status_code=500,
                content={"detail": "Error interno del servidor", "error_code": "INTERNAL_ERROR"},
            )
