"""
EnvelopeDesk - Lo que las tres acciones de los sobres comparten (FE #655).

Entregar, mirar y abrir necesitan lo mismo: la ronda, la competicion a la que
pertenece, y quien es capitan de que equipo.
"""

from decimal import Decimal

from src.modules.competition.application.exceptions import (
    CompetitionNotFoundError,
    RoundNotFoundError,
)
from src.modules.competition.application.services.team_roster import TeamRoster
from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.entities.envelope import Envelope
from src.modules.competition.domain.entities.round import Round
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.value_objects.enrollment_status import EnrollmentStatus
from src.modules.competition.domain.value_objects.round_id import RoundId
from src.modules.user.domain.value_objects.user_id import UserId


class EnvelopeDesk:
    """La mesa donde se reciben y se abren los sobres."""

    def __init__(self, uow: CompetitionUnitOfWorkInterface):
        self._uow = uow

    async def ronda_y_competicion(self, round_id: RoundId) -> tuple[Round, Competition]:
        """La sesion y su competicion.

        Raises:
            RoundNotFoundError: Si la ronda no existe
            CompetitionNotFoundError: Si su competicion no existe
        """
        ronda = await self._uow.rounds.find_by_id(round_id)
        if ronda is None:
            raise RoundNotFoundError(f"No existe la ronda {round_id.value}")
        competition = await self._uow.competitions.find_by_id(ronda.competition_id)
        if competition is None:
            raise CompetitionNotFoundError(f"No existe competición con ID {ronda.competition_id}")
        return ronda, competition

    @staticmethod
    def equipo_de(competition: Competition, user_id: UserId) -> str | None:
        """De que equipo es capitan, o None si no capitanea ninguno.

        El equipo sale de aqui y NO de lo que pida el cliente: aceptarlo en el
        cuerpo dejaria entregar el sobre del rival.
        """
        if competition.team_a_captain_id == user_id:
            return "A"
        if competition.team_b_captain_id == user_id:
            return "B"
        return None

    async def jugadores_de(self, competition: Competition, team: str) -> list[UserId]:
        """Los del equipo que siguen inscritos."""
        jugadores, _ = await TeamRoster.de_un_equipo(self._uow, competition.id, team)
        return jugadores

    async def handicaps_de(
        self, competition: Competition, jugadores: list[UserId]
    ) -> list[tuple[UserId, Decimal]]:
        """Cada jugador con el handicap que cuenta en esta competicion.

        El de la inscripcion si tiene uno propio; si no, cero, que es lo que la
        aplicacion sabe sin salir del modulo. Solo se usa para ordenar el sobre
        que nadie entrego.
        """
        inscripciones = {
            e.user_id: e
            for e in await self._uow.enrollments.find_by_competition_and_status(
                competition.id, EnrollmentStatus.APPROVED
            )
        }
        return [
            (uid, inscripciones[uid].custom_handicap or Decimal("0"))
            for uid in jugadores
            if uid in inscripciones
        ]

    async def sobre_de(self, ronda: Round, team: str, crear: bool = False) -> Envelope | None:
        """El sobre de ese equipo para esa sesion, creandolo si hace falta."""
        sobre = await self._uow.envelopes.find_by_round_and_team_for_update(ronda.id, team)
        if sobre is None and crear:
            sobre = Envelope.create(
                competition_id=ronda.competition_id,
                round_id=ronda.id,
                team=team,
                match_format=ronda.match_format,
            )
            await self._uow.envelopes.add(sobre)
        return sobre
