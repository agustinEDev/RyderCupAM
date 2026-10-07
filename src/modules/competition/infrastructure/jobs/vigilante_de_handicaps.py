"""
Vigilante del refresco de hándicaps de las 3:00 (BE #502).

Hasta ahora el backend no tenía ninguna tarea programada: todo lo automático
se hace al llegar una petición. Esto es la primera, y corre **dentro de la
propia API**: cada 15 minutos da una vuelta y el caso de uso decide si toca
algo. Así no hace falta ningún servicio aparte, y si el servidor se reinicia a
las 3:00, lo hace en cuanto vuelve. La vuelta real, que cruza módulos, se monta
en `src/config/vigilantes.py`.

Encendido por defecto; apagado en los tests (`TESTING=true`) y con
`HANDICAP_REFRESH_ENABLED=false`.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable, Mapping

logger = logging.getLogger(__name__)

INTERVALO_SEGUNDOS = 15 * 60
_APAGADO = {"false", "0", "no", "off"}


def debe_vigilar(entorno: Mapping[str, str]) -> bool:
    """Encendido salvo en los tests o si se apaga con `HANDICAP_REFRESH_ENABLED`."""
    if entorno.get("TESTING", "").lower() == "true":
        return False
    return entorno.get("HANDICAP_REFRESH_ENABLED", "true").strip().lower() not in _APAGADO


class VigilanteDeHandicaps:
    """Da una vuelta cada 15 minutos; una vuelta que falla no para las siguientes."""

    def __init__(
        self,
        vuelta: Callable[[], Awaitable[int]],
        esperar: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ):
        self._vuelta = vuelta
        self._esperar = esperar

    async def vigilar(self) -> None:
        """Hasta que la app se apague (se cancela la tarea)."""
        while True:
            try:
                preguntados = await self._vuelta()
                if preguntados:
                    logger.info("Refresco de hándicaps: %s jugadores consultados", preguntados)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Falló una vuelta del refresco de hándicaps")
            await self._esperar(INTERVALO_SEGUNDOS)
