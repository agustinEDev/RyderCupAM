"""
Vigilante del refresco de hándicaps de las 3:00 (BE #502).

Hasta ahora el backend no tenía ninguna tarea programada: todo lo automático
se hace al llegar una petición. Esto es la primera, y corre **dentro de la
propia API**: cada 15 minutos da una vuelta y el caso de uso decide si toca
algo. Así no hace falta ningún servicio aparte, y si el servidor se reinicia a
las 3:00, lo hace en cuanto vuelve. La vuelta real, que cruza módulos, se monta
en `src/config/vigilantes.py`.

**Solo en producción**: apagado por defecto y encendido con
`HANDICAP_REFRESH_ENABLED=true`, que solo se pone en Render. Así el Kind y el
entorno local no preguntan a la RFEG real por los usuarios de prueba. En los
tests (`TESTING=true`) nunca, aunque se encienda.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable, Mapping

logger = logging.getLogger(__name__)

INTERVALO_SEGUNDOS = 15 * 60
_ENCENDIDO = {"true", "1", "yes", "on"}


def debe_vigilar(entorno: Mapping[str, str]) -> bool:
    """Solo con `HANDICAP_REFRESH_ENABLED` encendido, y nunca en los tests."""
    if entorno.get("TESTING", "").lower() == "true":
        return False
    return entorno.get("HANDICAP_REFRESH_ENABLED", "").strip().lower() in _ENCENDIDO


class VigilanteDeHandicaps:
    """Da una vuelta cada 15 minutos; una vuelta que falla no para las siguientes."""

    def __init__(
        self,
        vuelta: Callable[[], Awaitable[int | None]],
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
