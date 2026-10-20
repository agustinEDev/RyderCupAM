"""
FranjasAlCerrar - Al cerrar un stroke play, cada aprobado tiene su franja (#251).

Decidido con Agustín el 8 oct 2026: con aprobados sin ninguna franja no se
cierran las inscripciones, y se dice quiénes, como con el hándicap. El
organizador los coloca (o los quita) y vuelve a cerrar.
"""

from src.modules.competition.application.services.player_names import PlayerNames
from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.value_objects.enrollment_status import EnrollmentStatus
from src.modules.competition.domain.value_objects.match_generation_block import (
    MISSING_TEE_WINDOW,
    BlockedPlayer,
)
from src.modules.user.domain.repositories.user_repository_interface import (
    UserRepositoryInterface,
)


class PlayersWithoutTeeWindowError(Exception):
    """Hay aprobados sin franja en un stroke play, y aquí van TODOS."""

    def __init__(self, players: list[BlockedPlayer]):
        self.players = players
        super().__init__(
            "Para cerrar las inscripciones de un Stableford o un Medal todos necesitan "
            "franja. Falta la de " + ", ".join(p.name or str(p.user_id) for p in players)
        )


class FranjasAlCerrar:
    """Comprueba que cada aprobado de un stroke play tiene franja."""

    def __init__(
        self, uow: CompetitionUnitOfWorkInterface, user_repository: UserRepositoryInterface
    ):
        self._uow = uow
        self._users = user_repository

    async def comprobar(self, competition: Competition) -> None:
        """
        Raises:
            PlayersWithoutTeeWindowError: Si a alguien le falta, con todos ellos
        """
        if competition.stroke_play is None:
            return
        aprobados = await self._uow.enrollments.find_by_competition_and_status(
            competition.id, EnrollmentStatus.APPROVED
        )
        con_franja = {p.user_id for p in await self._uow.plazas.de_la_competicion(competition.id)}
        sin = [i.user_id for i in aprobados if i.user_id not in con_franja]
        if not sin:
            return
        nombres = await PlayerNames.de_la_competicion(sin, competition.id, self._users, self._uow)
        raise PlayersWithoutTeeWindowError(
            [
                BlockedPlayer(user_id=u, name=nombres.get(u, ""), missing=MISSING_TEE_WINDOW)
                for u in sin
            ]
        )
