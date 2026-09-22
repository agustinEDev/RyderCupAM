"""
DraftRoster - Los jugadores que entran al draft, con su handicap (FE #653).

El handicap que cuenta es el de la inscripcion si tiene uno propio, y si no el
del jugador; sin ninguno, cero. Esa regla ya estaba dentro del reparto
automatico, y el draft necesita exactamente la misma: si divergieran, la
aplicacion elegiria por un capitan con un criterio distinto del que usa al
repartir sola.

Los capitanes no entran: nombrarlos ya los fijo en su equipo (RyderCupAm#320).
"""

from collections.abc import Iterable
from decimal import Decimal

from src.modules.competition.domain.entities.enrollment import Enrollment
from src.modules.competition.domain.services.snake_draft_service import PlayerForDraft
from src.modules.user.domain.repositories.user_repository_interface import (
    UserRepositoryInterface,
)
from src.modules.user.domain.value_objects.user_id import UserId


class DraftRoster:
    """Quien puede ser elegido, y con que handicap."""

    @staticmethod
    async def de_los_inscritos(
        enrollments: Iterable[Enrollment],
        user_repository: UserRepositoryInterface,
        excluidos: Iterable[UserId] = (),
    ) -> list[PlayerForDraft]:
        """
        Args:
            enrollments: Las inscripciones aprobadas
            user_repository: De donde sale el handicap del jugador
            excluidos: Quien no entra al draft, normalmente los dos capitanes

        Returns:
            Los jugadores con su handicap, en el orden de las inscripciones
        """
        fuera = set(excluidos)
        players = []
        for enrollment in enrollments:
            if enrollment.user_id in fuera:
                continue
            if enrollment.custom_handicap is not None:
                handicap = enrollment.custom_handicap
            else:
                user = await user_repository.find_by_id(enrollment.user_id)
                handicap = (
                    Decimal(str(user.handicap.value))
                    if user and user.handicap is not None
                    else Decimal("0")
                )
            players.append(PlayerForDraft(user_id=enrollment.user_id, handicap=handicap))
        return players
