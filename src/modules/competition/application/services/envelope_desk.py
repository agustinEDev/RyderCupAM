"""
EnvelopeDesk - Lo que las tres acciones de los sobres comparten (FE #655).

Entregar, mirar y abrir necesitan lo mismo: la ronda, la competicion a la que
pertenece, y quien es capitan de que equipo.
"""

from decimal import Decimal

from src.modules.competition.application.exceptions import (
    CompetitionNotFoundError,
    NotCompetitionParticipantError,
    RoundNotFoundError,
)
from src.modules.competition.application.services.team_roster import TeamRoster
from src.modules.competition.domain.entities.competition import (
    Competition,
    TeamsNotAssignedError,
)
from src.modules.competition.domain.entities.envelope import Envelope
from src.modules.competition.domain.entities.round import Round
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.value_objects.enrollment_status import EnrollmentStatus
from src.modules.competition.domain.value_objects.round_id import RoundId
from src.modules.user.domain.repositories.user_repository_interface import (
    UserRepositoryInterface,
)
from src.modules.user.domain.value_objects.user_id import UserId


class EnvelopeDesk:
    """La mesa donde se reciben y se abren los sobres."""

    def __init__(
        self, uow: CompetitionUnitOfWorkInterface, user_repository: UserRepositoryInterface
    ):
        """
        Args:
            uow: Unit of Work del modulo
            user_repository: De donde sale el handicap de quien no tiene uno
                propio en esta competicion, que es casi todo el mundo
        """
        self._uow = uow
        self._user_repo = user_repository

    async def ronda_y_competicion(
        self, round_id: RoundId, bloquear: bool = False
    ) -> tuple[Round, Competition]:
        """La sesion y su competicion, bloqueada cuando se va a escribir.

        Bloquear la competicion serializa las entregas de esa competicion, que
        es justo lo que hace falta: el sobre se crea la primera vez que el
        capitan entrega, y dos peticiones a la vez leerian que no existe, las
        dos lo crearian, y una reventaria contra la clave unica con un 500.

        Raises:
            RoundNotFoundError: Si la ronda no existe
            CompetitionNotFoundError: Si su competicion no existe
        """
        ronda = await self._uow.rounds.find_by_id(round_id)
        if ronda is None:
            raise RoundNotFoundError(f"No existe la ronda {round_id.value}")
        competition = (
            await self._uow.competitions.find_by_id_for_update(ronda.competition_id)
            if bloquear
            else await self._uow.competitions.find_by_id(ronda.competition_id)
        )
        if competition is None:
            raise CompetitionNotFoundError(f"No existe competición con ID {ronda.competition_id}")
        return ronda, competition

    @staticmethod
    def equipo_de(competition: Competition, user_id: UserId) -> str | None:
        """De que equipo es capitan, o None si no capitanea ninguno.

        El equipo sale de aqui y NO de lo que pida el cliente: aceptarlo en el
        cuerpo dejaria entregar el sobre del rival. Quien capitanea que lo
        decide la entidad, que es donde vive esa regla.
        """
        for team in ("A", "B"):
            if competition.is_captain_of(team, user_id):
                return team
        return None

    async def comprobar_que_es_de_la_competicion(
        self, competition: Competition, user_id: UserId
    ) -> None:
        """Quien pregunta tiene que ser de esta competicion.

        Sin esto, probando identificadores se leia la sesion de cualquiera,
        incluida la de una privada.

        Raises:
            NotCompetitionParticipantError: Si no esta inscrito ni la organiza
        """
        if competition.is_creator(user_id):
            return
        inscripcion = await self._uow.enrollments.find_by_user_and_competition(
            user_id, competition.id
        )
        if inscripcion is None:
            raise NotCompetitionParticipantError(
                "Esta sesión es de una competición en la que no participas"
            )

    async def jugadores_de(self, competition: Competition, team: str) -> list[UserId]:
        """Los del equipo que siguen inscritos.

        Raises:
            TeamsNotAssignedError: Si todavia no hay equipos repartidos. Sin
                esto el error acababa siendo «hay jugadores que no son de este
                equipo», que manda a buscar el fallo donde no esta
        """
        jugadores, hay_equipos = await TeamRoster.de_un_equipo(self._uow, competition.id, team)
        if not hay_equipos:
            raise TeamsNotAssignedError(
                "Todavía no hay equipos repartidos: primero se reparten y después van los sobres"
            )
        return jugadores

    async def handicaps_de(
        self, competition: Competition, jugadores: list[UserId]
    ) -> list[tuple[UserId, Decimal]]:
        """Cada jugador con el handicap que cuenta en esta competicion.

        El de la inscripcion si tiene uno propio, y si no el del jugador: la
        MISMA regla que usa la generacion de partidos. Mirar solo el propio
        dejaba a casi todo el mundo en cero —`custom_handicap` suele ser
        None—, y entonces el sobre automatico salia en el orden de la lista y
        no por handicap, que es lo que dice hacer.
        """
        inscripciones = {
            e.user_id: e
            for e in await self._uow.enrollments.find_by_competition_and_status(
                competition.id, EnrollmentStatus.APPROVED
            )
        }
        con_handicap = []
        for uid in jugadores:
            inscripcion = inscripciones.get(uid)
            if inscripcion is None:
                continue
            if inscripcion.custom_handicap is not None:
                con_handicap.append((uid, inscripcion.custom_handicap))
                continue
            user = await self._user_repo.find_by_id(uid)
            con_handicap.append(
                (
                    uid,
                    Decimal(str(user.handicap.value))
                    if user and user.handicap is not None
                    else Decimal("0"),
                )
            )
        return con_handicap

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
