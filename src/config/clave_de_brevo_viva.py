"""
La clave de Brevo, viva (B1-B3, 7 nov 2026).

Brevo caduca una clave que pasa 90 días sin usarse, y su respaldo solo se usa el día
que Mailgun no puede. Una consulta pequeña al día la mantiene viva y, si Brevo la
rechaza, sale un error propio en Sentry antes de necesitarla. Se arranca en el
`lifespan` solo en producción, enviando por Mailgun y con clave de Brevo.
"""

import asyncio
import logging
import os
from collections.abc import Awaitable, Callable, Mapping

import httpx

from src.shared.infrastructure.email.envio_de_correo import BrevoTransport

logger = logging.getLogger(__name__)

INTERVALO_SEGUNDOS = 24 * 60 * 60
CLAVE_DE_BREVO_RECHAZADA = "Brevo API key rejected"
# Tres días seguidos sin respuesta buena: el vigía podría estar roto (auditoría)
DIAS_SIN_RESPUESTA_BUENA = 3
COMPROBACION_ROTA = f"Brevo key check failing for {DIAS_SIN_RESPUESTA_BUENA} days"


def vigia_activado(entorno: Mapping[str, str]) -> bool:
    """En producción, enviando por mailgun y con clave de Brevo; nunca en los tests."""
    if (entorno.get("TESTING") or "").lower() == "true":
        return False
    produccion = (entorno.get("ENVIRONMENT") or "").strip().lower() == "production"
    transporte = (entorno.get("EMAIL_TRANSPORT") or "").strip().lower() or "mailgun"
    clave = (entorno.get("BREVO_API_KEY") or "").strip()
    return produccion and transporte == "mailgun" and bool(clave)


def brevo_de_la_configuracion(entorno: Mapping[str, str] = os.environ) -> BrevoTransport:
    """El transporte de Brevo con la clave y el remitente de la configuración."""
    return BrevoTransport(
        api_key=(entorno.get("BREVO_API_KEY") or "").strip(),
        api_url=(entorno.get("BREVO_API_URL") or "").strip() or "https://api.brevo.com/v3",
        from_email=(entorno.get("MAILGUN_FROM_EMAIL") or "").strip()
        or "Ryder Cup Friends <noreply@rydercupfriends.com>",
    )


class VigiaDeLaClaveDeBrevo:
    """Una vuelta al día: usa la clave de Brevo y avisa si la rechaza."""

    def __init__(
        self,
        brevo: BrevoTransport,
        esperar: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ):
        self._brevo = brevo
        self._esperar = esperar
        self._dias_sin_respuesta_buena = 0

    async def vigilar(self) -> None:
        """Hasta que la app se apague. Una vuelta que falla no para las siguientes."""
        while True:
            try:
                await self.vuelta()
            except Exception as error:
                logger.warning("Brevo key check failed (%s)", type(error).__name__)
            await self._esperar(INTERVALO_SEGUNDOS)

    async def vuelta(self) -> bool:
        """True si Brevo aceptó la clave."""
        estado = await self._brevo.comprueba_la_clave()
        if estado == httpx.codes.OK:
            logger.info("Brevo key check: ok")
            self._dias_sin_respuesta_buena = 0
            return True
        if estado in (httpx.codes.UNAUTHORIZED, httpx.codes.FORBIDDEN):
            # Su propio error en Sentry: la clave caducó o la revocaron
            logger.error(CLAVE_DE_BREVO_RECHAZADA)
            return False
        if estado is not None:
            logger.warning("Brevo key check: status %s; retrying tomorrow", estado)
        self._dias_sin_respuesta_buena += 1
        if self._dias_sin_respuesta_buena == DIAS_SIN_RESPUESTA_BUENA:
            logger.error(COMPROBACION_ROTA)
        return False
