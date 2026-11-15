"""
Puerto: avisar al organizador de que hay hándicaps sin actualizar (#251).

Si una actualización con la RFEG termina con alguien sin actualizar, se le
avisa por correo para que lo haga con el botón (decidido el 7 oct 2026).
"""

from typing import Protocol


class IHandicapUpdateEmailService(Protocol):
    """Los correos de las actualizaciones de hándicaps: al organizador y al no encontrado."""

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

    async def send_handicap_not_found_email(
        self,
        to_email: str,
        player_name: str,
        competition_name: str,
    ) -> bool:
        """
        Al jugador español al que la RFEG no encontró (H3, 15 nov 2026).

        Args:
            to_email: Su correo
            player_name: Su nombre, el de su perfil
            competition_name: La competición (el enlace va a su perfil, no a ella)

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
