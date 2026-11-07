"""
La clave de Brevo, viva (B1-B4, 7 nov 2026).

Brevo caduca una clave que pasa 90 días sin usarse, y su respaldo solo se usa el día
que Mailgun y Resend no pueden. Una consulta pequeña al día la mantiene viva. Cada vuelta
avisa a un monitor de Sentry (Crons): si un día falla o no llega, alerta Sentry, que
guarda el historial, así que los despliegues no lo reinician. Además, una clave
rechazada (401/403) deja su propio error. Se arranca en el `lifespan` solo en
producción, enviando por Mailgun y con clave de Brevo.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable, Mapping

import httpx
from sentry_sdk.crons import capture_checkin

from src.shared.infrastructure.email.envio_de_correo import (
    BrevoTransport,
    brevo_desde,
    envia_por_mailgun_en_produccion,
)

logger = logging.getLogger(__name__)

INTERVALO_SEGUNDOS = 24 * 60 * 60
CLAVE_DE_BREVO_RECHAZADA = "Brevo API key rejected"
MONITOR = "brevo-key-check"
# Sentry crea el monitor con el primer aviso: una vez al día, con una hora de margen
CONFIGURACION_DEL_MONITOR = {
    "schedule": {"type": "interval", "value": 1, "unit": "day"},
    "checkin_margin": 60,
    "max_runtime": 5,
}


def vigia_activado(entorno: Mapping[str, str]) -> bool:
    """En producción, enviando por mailgun y con clave de Brevo; nunca en los tests."""
    if (entorno.get("TESTING") or "").lower() == "true":
        return False
    return envia_por_mailgun_en_produccion(entorno) and brevo_desde(entorno) is not None


class VigiaDeLaClaveDeBrevo:
    """Una vuelta al día: usa la clave de Brevo y se lo cuenta al monitor de Sentry."""

    def __init__(
        self,
        brevo: BrevoTransport,
        esperar: Callable[[float], Awaitable[None]] = asyncio.sleep,
        avisa: Callable[..., object] = capture_checkin,
    ):
        self._brevo = brevo
        self._esperar = esperar
        self._avisa = avisa

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
        bien = estado == httpx.codes.OK
        if bien:
            logger.info("Brevo key check: ok")
        elif estado in (httpx.codes.UNAUTHORIZED, httpx.codes.FORBIDDEN):
            # Su propio error en Sentry: la clave caducó o la revocaron
            logger.error(CLAVE_DE_BREVO_RECHAZADA)
        elif estado is not None:
            logger.warning("Brevo key check: status %s; retrying tomorrow", estado)
        self._al_monitor("ok" if bien else "error")
        return bien

    def _al_monitor(self, estado: str) -> None:
        try:
            self._avisa(
                monitor_slug=MONITOR,
                status=estado,
                monitor_config=CONFIGURACION_DEL_MONITOR,
            )
        except Exception as error:
            logger.warning("Brevo key check: Sentry monitor failed (%s)", type(error).__name__)
