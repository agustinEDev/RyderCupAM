"""
Cada límite superado (429) queda en el log de seguridad.

Auditoría de la fase 6, B-06: `log_rate_limit_exceeded` existía y no lo llamaba
nadie, así que un abuso que chocaba con los límites no dejaba rastro de auditoría.
Hay 429 de slowapi y 429 que las rutas devuelven por su cuenta (búsqueda por
correo, cambios de seguridad, contacto, invitaciones); este middleware los apunta
todos, sin tocar la respuesta. El evento es de gravedad media: se queda en el log y
no va a Sentry (allí solo llega lo alto y lo crítico).

ASGI puro, como el resto de middlewares de la app: solo mira el código de estado.
"""

import logging

from starlette.requests import Request
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from src.config.settings import settings
from src.shared.infrastructure.http.http_context_validator import (
    get_trusted_client_ip,
    get_user_agent,
)
from src.shared.infrastructure.logging.security_logger import get_security_logger

logger = logging.getLogger(__name__)

DEMASIADAS_PETICIONES = 429


def _plantilla_de_la_ruta(scope: Scope) -> str:
    """La ruta tal como se declara (`/users/{user_id}`); sin ella, la que llegó."""
    ruta = scope.get("route")
    return getattr(ruta, "path", None) or scope.get("path", "")


def _apunta(scope: Scope) -> None:
    request = Request(scope)
    get_security_logger().log_rate_limit_exceeded(
        user_id=None,
        ip_address=get_trusted_client_ip(
            request, settings.TRUSTED_PROXIES, settings.TRUST_CLOUDFLARE_HEADERS
        )
        or "unknown",
        user_agent=get_user_agent(request) or "unknown",
        endpoint=_plantilla_de_la_ruta(scope),
        limit_type="rate_limit",
        limit_value="see route limits",
        request_count=0,
    )


class ApuntaLosLimitesSuperados:
    """Apunta en el log de seguridad cada respuesta 429, venga de donde venga."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def envia(mensaje: Message) -> None:
            if (
                mensaje["type"] == "http.response.start"
                and mensaje.get("status") == DEMASIADAS_PETICIONES
            ):
                try:
                    _apunta(scope)
                except Exception:
                    # Que no se pueda apuntar no puede cambiar la respuesta
                    logger.warning(
                        "No se pudo apuntar el 429 en el log de seguridad", exc_info=True
                    )
            await send(mensaje)

        await self.app(scope, receive, envia)
