"""
El freno del login por correo y origen (BE #732, ADR-043).

El origen es la red desde la que se intenta o, con un dispositivo fiable de la
cuenta, ese dispositivo. Así los fallos de otra red no dejan fuera al dueño: cada
pareja correo + origen lleva sus propios intentos y su propio bloqueo.
"""

from abc import ABC, abstractmethod
from datetime import datetime


def origen_de_red(red: str) -> str:
    """El origen de un intento desde una red (la IP real, o su /64 en IPv6)."""
    return f"red:{red}"


def origen_de_dispositivo(device_id: str) -> str:
    """El origen de un intento desde un dispositivo fiable de la cuenta."""
    return f"dispositivo:{device_id.lower()}"


class IFrenoDelLogin(ABC):
    """Cuenta los intentos y los fallos de cada pareja correo + origen."""

    @abstractmethod
    def admite_intento(self, email: str, origen: str) -> bool:
        """Cuenta un intento. False si este origen ya agotó los de este minuto."""

    @abstractmethod
    def bloqueado_hasta(self, email: str, origen: str) -> datetime | None:
        """Hasta cuándo está bloqueado este origen para este correo, o None."""

    @abstractmethod
    def apunta_fallo(self, email: str, origen: str) -> datetime | None:
        """Apunta un fallo. Si con él se bloquea, hasta cuándo; si no, None."""

    @abstractmethod
    def olvida(self, email: str, origen: str) -> None:
        """Tras acertar: los fallos de este origen vuelven a cero."""

    @abstractmethod
    def techo_de_la_red_agotado(self, red: str) -> bool:
        """Si la red agotó su techo de fallos (30 por minuto, sea cual sea el correo)."""

    @abstractmethod
    def apunta_fallo_en_la_red(self, red: str) -> None:
        """Apunta un login fallido en el techo de su red."""

    @abstractmethod
    def tiene_bloqueos(self, email: str) -> bool:
        """Si algún origen está bloqueado ahora para este correo. No borra nada."""

    @abstractmethod
    def olvida_la_cuenta(self, email: str) -> bool:
        """El desbloqueo del administrador: borra todo lo de este correo.

        Returns:
            True si había algún origen bloqueado.
        """
