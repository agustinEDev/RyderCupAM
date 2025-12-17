"""
Middleware de Correlation ID para trazabilidad de requests.

Genera o propaga un Correlation ID único para cada request HTTP,
permitiendo rastrear el flujo completo de una operación a través
de múltiples servicios y logs.
"""

import uuid
from contextvars import ContextVar
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

# Context variable para almacenar correlation_id por request
correlation_id_var: ContextVar[str | None] = ContextVar("correlation_id", default=None)

# Header para Correlation ID
CORRELATION_ID_HEADER = "X-Correlation-ID"


class CorrelationMiddleware(BaseHTTPMiddleware):
    """
    Middleware que gestiona Correlation IDs en requests HTTP.

    Funcionalidad:
    - Extrae correlation_id del header X-Correlation-ID (si existe)
    - Genera nuevo correlation_id si no viene en el request
    - Almacena en ContextVar para acceso global
    - Añade header X-Correlation-ID a la response
    - Loggea inicio y fin de cada request

    Uso:
        app.add_middleware(CorrelationMiddleware)
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Procesa cada request añadiendo correlation ID.

        Args:
            request: Request HTTP entrante
            call_next: Siguiente handler en la cadena

        Returns:
            Response con header X-Correlation-ID
        """
        # Extraer o generar correlation_id
        correlation_id = request.headers.get(CORRELATION_ID_HEADER)

        if not correlation_id:
            # Generar nuevo UUID si no viene en request
            correlation_id = str(uuid.uuid4())

        # Almacenar en ContextVar para acceso global
        correlation_id_var.set(correlation_id)

        # Procesar request
        response = await call_next(request)

        # Añadir header a response
        response.headers[CORRELATION_ID_HEADER] = correlation_id

        return response


def get_correlation_id() -> str | None:
    """
    Obtiene el correlation ID del contexto actual.

    Returns:
        Correlation ID del request actual, o None si no existe

    Ejemplo:
        correlation_id = get_correlation_id()
        logger.info("Processing order", extra={"correlation_id": correlation_id})
    """
    return correlation_id_var.get()
