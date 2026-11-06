"""
El tope global de correos de «intentos fallidos», en memoria (BE #732).

Como mucho 20 por hora en toda la app, además del uno por hora y cuenta. En
memoria, como los límites: la API corre en un solo proceso, y un reinicio lo pone a
cero (como mucho otros 20 avisos). Sin `await`: atómico en el bucle de asyncio.
"""

from collections import deque
from collections.abc import Callable
from datetime import datetime, timedelta

from src.modules.user.application.ports.cupo_de_avisos_port import ICupoDeAvisos

AVISOS_POR_HORA = 20
UNA_HORA = timedelta(hours=1)


class CupoDeAvisosEnMemoria(ICupoDeAvisos):
    """Los avisos de la última hora."""

    def __init__(
        self, reloj: Callable[[], datetime] = datetime.now, por_hora: int = AVISOS_POR_HORA
    ):
        self._reloj = reloj
        self._por_hora = por_hora
        self._enviados: deque[datetime] = deque()

    def reserva(self) -> bool:
        ahora = self._reloj()
        while self._enviados and self._enviados[0] <= ahora - UNA_HORA:
            self._enviados.popleft()
        if len(self._enviados) >= self._por_hora:
            return False
        self._enviados.append(ahora)
        return True

    def devuelve(self) -> None:
        if self._enviados:
            self._enviados.pop()

    def reinicia(self) -> None:
        """Todo a cero (para los tests)."""
        self._enviados.clear()


# El de la app: uno para todo el proceso
cupo_de_avisos = CupoDeAvisosEnMemoria()
