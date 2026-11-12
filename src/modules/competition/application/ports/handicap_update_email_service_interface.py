"""
Puerto: avisar al organizador de que hay hándicaps sin actualizar (#251).

Si una actualización con la RFEG termina con alguien sin actualizar, se le
avisa por correo para que lo haga con el botón (decidido el 7 oct 2026).
"""

from typing import Protocol


class IHandicapUpdateEmailService(Protocol):
    """Correo al organizador cuando una actualización de hándicaps queda incompleta."""

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

    async def send_scheduled_handicaps_update_skipped_email(
        self,
        to_email: str,
        organizer_name: str,
        competition_name: str,
        competition_id: str,
        reason: str,
    ) -> bool:
        """
        La actualización programada no se lanzó: a esa hora la ventana estaba cerrada.

        Args:
            reason: Por qué (el motivo de la ventana)
        """
