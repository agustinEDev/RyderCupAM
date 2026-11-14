"""
La respuesta a un límite superado (429), que además queda en el log de seguridad.

Auditoría de la fase 6, B-06: `log_rate_limit_exceeded` existía y no lo llamaba
nadie, así que un abuso que chocaba con los límites (registro, recuperar la
contraseña, búsquedas) no dejaba rastro de auditoría. La respuesta es la misma de
siempre, la de slowapi; el evento es de gravedad media, así que se queda en el log
y no va a Sentry (allí solo llega lo alto y lo crítico).
"""

import logging

from fastapi import Request
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from starlette.responses import Response

from src.config.settings import settings
from src.shared.infrastructure.http.http_context_validator import (
    get_trusted_client_ip,
    get_user_agent,
)
from src.shared.infrastructure.logging.security_logger import get_security_logger

logger = logging.getLogger(__name__)


def responde_al_limite_superado(request: Request, exc: RateLimitExceeded) -> Response:
    """Apunta el 429 en el log de seguridad y responde como slowapi."""
    try:
        get_security_logger().log_rate_limit_exceeded(
            user_id=None,
            ip_address=get_trusted_client_ip(
                request, settings.TRUSTED_PROXIES, settings.TRUST_CLOUDFLARE_HEADERS
            )
            or "unknown",
            user_agent=get_user_agent(request) or "unknown",
            endpoint=request.url.path,
            limit_type="rate_limit",
            limit_value=str(exc.detail),
            request_count=0,
        )
    except Exception:
        # Que no se pueda apuntar no puede cambiar la respuesta
        logger.warning("No se pudo apuntar el 429 en el log de seguridad", exc_info=True)
    return _rate_limit_exceeded_handler(request, exc)
