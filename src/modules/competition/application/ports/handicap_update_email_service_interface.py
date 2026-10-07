"""
Puerto: avisar al organizador de que hay hándicaps sin actualizar (#251).

Si una actualización con la RFEG termina con alguien sin actualizar, se le
avisa por correo para que lo haga con el botón (decidido el 7 oct 2026).
"""

from abc import ABC, abstractmethod


class IHandicapUpdateEmailService(ABC):
    """Correo al organizador cuando una actualización de hándicaps queda incompleta."""

    @abstractmethod
    async def send_handicaps_pending_email(
        self,
        to_email: str,
        organizer_name: str,
        competition_name: str,
        competition_id: str,
        pending_names: list[str],
    ) -> bool:
        """
        Args:
            to_email: El correo del organizador
            organizer_name: Su nombre
            competition_name: La competición
            competition_id: Para el enlace a su ficha
            pending_names: Quién se quedó sin actualizar

        Returns:
            True si se envió
        """
