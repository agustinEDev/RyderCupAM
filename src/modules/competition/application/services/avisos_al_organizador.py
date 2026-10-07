"""
AvisosAlOrganizador - Los correos al organizador sobre las actualizaciones de hándicaps (#251).

Los usan la pasada (al acabar con alguien sin actualizar) y el vigilante (una
cortada por un reinicio, o una programada que no se pudo lanzar). Un correo que
falla se registra y no tumba nada: lo que pasó ya está guardado.
"""

import logging

from src.modules.competition.application.ports.handicap_update_email_service_interface import (
    IHandicapUpdateEmailService,
)
from src.modules.competition.domain.entities.competition import Competition
from src.modules.user.domain.repositories.user_repository_interface import (
    UserRepositoryInterface,
)

logger = logging.getLogger(__name__)


class AvisosAlOrganizador:
    """Escribe al organizador de una competición."""

    def __init__(self, avisos: IHandicapUpdateEmailService | None):
        self._avisos = avisos

    async def quien(self, usuarios: UserRepositoryInterface, competition: Competition):
        """El organizador, si existe y tiene correo (leerlo dentro de la transacción)."""
        organizador = await usuarios.find_by_id(competition.creator_id)
        if organizador is None or organizador.email is None:
            return None
        return organizador

    async def pendientes(self, organizador, competition: Competition, nombres: list[str]) -> None:
        """Hay jugadores sin actualizar: que los termine con el botón."""
        if self._avisos is None or organizador is None:
            return
        try:
            await self._avisos.send_handicaps_pending_email(
                to_email=organizador.email.value,
                organizer_name=organizador.get_full_name(),
                competition_name=str(competition.name),
                competition_id=str(competition.id.value),
                pending_names=nombres,
            )
        except Exception:
            logger.exception("No se pudo avisar al organizador de %s", competition.id.value)

    async def no_lanzada(self, organizador, competition: Competition, motivo: str) -> None:
        """La programada no se lanzó: a su hora la ventana estaba cerrada."""
        if self._avisos is None or organizador is None:
            return
        try:
            await self._avisos.send_scheduled_handicaps_update_skipped_email(
                to_email=organizador.email.value,
                organizer_name=organizador.get_full_name(),
                competition_name=str(competition.name),
                competition_id=str(competition.id.value),
                reason=motivo,
            )
        except Exception:
            logger.exception("No se pudo avisar al organizador de %s", competition.id.value)
