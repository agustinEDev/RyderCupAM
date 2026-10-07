"""
HandicapsAlCerrar - El hándicap de cada jugador se fija al cerrar inscripciones (#251).

Decidido con Agustín el 7 oct 2026, como hace la RFEG («el hándicap de la base
de datos tras el cierre de inscripción»). En un Stableford o un Medal, al cerrar
se guarda en cada inscripción el hándicap que cuenta (el personalizado, si no el
del perfil). Es el de todo el torneo: de él sale su categoría, y ya no cambia.

Para inscribirse ya hace falta hándicap, así que aquí no debería llegar nadie
sin él. Si aun así falta alguno, no se cierra y se dice quién: la misma lista que
«jugadores sin barras».

Una Ryder Cup no pasa por aquí: no tiene categorías.
"""

from src.modules.competition.application.services.handicaps_de_la_competicion import (
    HandicapsDeLaCompeticion,
)
from src.modules.competition.application.services.player_names import PlayerNames
from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.value_objects.enrollment_status import EnrollmentStatus
from src.modules.competition.domain.value_objects.match_generation_block import (
    MISSING_HANDICAP,
    BlockedPlayer,
)
from src.modules.user.domain.repositories.user_repository_interface import (
    UserRepositoryInterface,
)


class PlayersWithoutHandicapError(Exception):
    """Hay inscritos sin hándicap en un stroke play, y aquí van TODOS."""

    def __init__(self, players: list[BlockedPlayer]):
        self.players = players
        super().__init__(
            "Para cerrar las inscripciones de un Stableford o un Medal todos necesitan "
            "hándicap. Falta el de " + ", ".join(p.name or str(p.user_id) for p in players)
        )


class HandicapsAlCerrar:
    """Comprueba y fija el hándicap de cada jugador al cerrar un stroke play."""

    def __init__(
        self, uow: CompetitionUnitOfWorkInterface, user_repository: UserRepositoryInterface
    ):
        self._uow = uow
        self._users = user_repository

    async def fijar(self, competition: Competition) -> None:
        """
        Comprueba que todos tienen hándicap y fija el de cada uno, con UNA lectura:
        lo que se comprueba es lo que se guarda, aunque alguien cambie su perfil
        entre medias.

        Raises:
            PlayersWithoutHandicapError: Si a alguien le falta, con todos ellos
        """
        if competition.stroke_play is None:
            return
        inscripciones, handicaps = await self._de_los_inscritos(competition)
        sin = [e.user_id for e in inscripciones if handicaps[e.user_id] is None]
        if sin:
            nombres = await PlayerNames.de_la_competicion(
                sin, competition.id, self._users, self._uow
            )
            raise PlayersWithoutHandicapError(
                [
                    BlockedPlayer(user_id=u, name=nombres.get(u, ""), missing=MISSING_HANDICAP)
                    for u in sin
                ]
            )
        for inscripcion in inscripciones:
            inscripcion.congelar_handicap(handicaps[inscripcion.user_id])
            await self._uow.enrollments.update(inscripcion)

    async def _de_los_inscritos(self, competition: Competition):
        inscripciones = await self._uow.enrollments.find_by_competition_and_status(
            competition.id, EnrollmentStatus.APPROVED
        )
        return inscripciones, await HandicapsDeLaCompeticion.de(inscripciones, self._users)
