"""
El tope diario del formulario de contacto, en memoria (6 nov 2026).

Como mucho MENSAJES_POR_DIA en 24 horas, en toda la app, además de los 10 al día por
red de la ruta: deja el cupo diario del proveedor (100) para la verificación y la
recuperación de contraseña. En memoria, como los demás límites: un reinicio lo pone a
cero. Sin `await`: atómico en el bucle de asyncio.
"""

from collections import deque
from collections.abc import Callable
from datetime import datetime, timedelta

from src.modules.support.application.ports.cupo_de_contacto_port import ICupoDeContacto

MENSAJES_POR_DIA = 20
UN_DIA = timedelta(hours=24)


class CupoDeContactoEnMemoria(ICupoDeContacto):
    """Los mensajes enviados en las últimas 24 horas."""

    def __init__(self, reloj: Callable[[], datetime] = datetime.now):
        """El tope, vacío, con su reloj."""
        self._reloj = reloj
        self._enviados: deque[datetime] = deque()

    def reserva(self) -> bool:
        """Reserva un mensaje; False si el tope de hoy está lleno."""
        ahora = self._reloj()
        while self._enviados and self._enviados[0] <= ahora - UN_DIA:
            self._enviados.popleft()
        if len(self._enviados) >= MENSAJES_POR_DIA:
            return False
        self._enviados.append(ahora)
        return True

    def devuelve(self) -> None:
        """Devuelve el último mensaje reservado, que no salió."""
        if self._enviados:
            self._enviados.pop()

    def reinicia(self) -> None:
        """Todo a cero (para los tests)."""
        self._enviados.clear()


# El de la app: uno para todo el proceso
cupo_de_contacto = CupoDeContactoEnMemoria()
