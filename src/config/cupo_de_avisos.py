"""
El tope global de correos de «intentos fallidos», en memoria (BE #732).

Además del uno por hora y cuenta, en toda la app:
- los avisos de una red bloqueada: 20 por hora y 30 al día;
- los graves (el aviso a los 25 fallos, el respaldo y el contador diario): su propio
  hueco de 10 al día, que los de red no gastan. Así un atacante bloqueando redes no
  tapa los avisos de un ataque repartido.
Deja más de la mitad del cupo diario del proveedor (100) para la verificación y la
recuperación de contraseña. En memoria, como los límites: un reinicio lo pone a cero.
Sin `await`: atómico en el bucle de asyncio.
"""

from collections import deque
from collections.abc import Callable
from datetime import datetime, timedelta

from src.modules.user.application.ports.cupo_de_avisos_port import (
    MOTIVO_SESION_CERRADA,
    ICupoDeAvisos,
)

AVISOS_DE_RED_POR_HORA = 20
AVISOS_DE_RED_POR_DIA = 30
AVISOS_GRAVES_POR_DIA = 10
# Los de «sesión cerrada por seguridad» (F-02): los provoca quien tenga cookies robadas;
# su propio hueco, para no gastar ni que les gasten los de los fallos
AVISOS_DE_SESION_CERRADA_POR_DIA = 10
UNA_HORA = timedelta(hours=1)
UN_DIA = timedelta(hours=24)


class CupoDeAvisosEnMemoria(ICupoDeAvisos):
    """Los avisos enviados en el último día, por tipo."""

    def __init__(self, reloj: Callable[[], datetime] = datetime.now):
        """El tope, vacío, con su reloj."""
        self._reloj = reloj
        self._de_red: deque[datetime] = deque()
        self._graves: deque[datetime] = deque()
        self._sesiones_cerradas: deque[datetime] = deque()

    def _de(self, motivo: str) -> deque[datetime]:
        """La cola de este motivo: la de red, la de sesiones cerradas o la de los graves."""
        if motivo == "red":
            return self._de_red
        if motivo == MOTIVO_SESION_CERRADA:
            return self._sesiones_cerradas
        return self._graves

    def reserva(self, motivo: str) -> bool:
        """Reserva un aviso de este motivo; False si su tope está lleno."""
        ahora = self._reloj()
        enviados = self._de(motivo)
        while enviados and enviados[0] <= ahora - UN_DIA:
            enviados.popleft()
        if motivo == "red":
            en_la_hora = sum(1 for t in enviados if t > ahora - UNA_HORA)
            if len(enviados) >= AVISOS_DE_RED_POR_DIA or en_la_hora >= AVISOS_DE_RED_POR_HORA:
                return False
        elif motivo == MOTIVO_SESION_CERRADA:
            if len(enviados) >= AVISOS_DE_SESION_CERRADA_POR_DIA:
                return False
        elif len(enviados) >= AVISOS_GRAVES_POR_DIA:
            return False
        enviados.append(ahora)
        return True

    def devuelve(self, motivo: str) -> None:
        """Devuelve el último aviso reservado de este motivo, que no salió."""
        enviados = self._de(motivo)
        if enviados:
            enviados.pop()

    def reinicia(self) -> None:
        """Todo a cero (para los tests)."""
        self._de_red.clear()
        self._graves.clear()
        self._sesiones_cerradas.clear()


# El de la app: uno para todo el proceso
cupo_de_avisos = CupoDeAvisosEnMemoria()
