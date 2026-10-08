"""Caso de Uso: Reasignar jugadores de un partido."""

from src.modules.competition.application.dto.round_match_dto import (
    ReassignMatchPlayersRequestDTO,
    ReassignMatchPlayersResponseDTO,
)
from src.modules.competition.application.exceptions import (
    MatchNotFoundError,
    NotCompetitionCreatorError,
)
from src.modules.competition.application.services.jugadores_del_partido import (
    JugadoresDelPartido,
)
from src.modules.competition.domain.entities.match import Match
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.services.scoring_service import ScoringService
from src.modules.competition.domain.value_objects.match_id import MatchId
from src.modules.competition.domain.value_objects.match_status import MatchStatus
from src.modules.golf_course.domain.repositories.golf_course_repository import IGolfCourseRepository
from src.modules.user.domain.repositories.user_repository_interface import UserRepositoryInterface
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.services.playing_handicap_calculator import (
    PlayingHandicapCalculator,
)


class MatchNotScheduledError(Exception):
    """El partido no esta en estado SCHEDULED."""

    pass


class PlayerNotInTeamError(Exception):
    """Un jugador no pertenece al equipo correcto."""

    pass


class NoTeamAssignmentError(Exception):
    """No hay asignación de equipos."""

    pass


class WrongNumberOfPlayersError(Exception):
    """Un lado no trae los jugadores que pide el formato del partido."""

    pass


class ReassignMatchPlayersUseCase:
    """
    Caso de uso para reasignar jugadores de un partido.

    Solo permitido cuando el partido esta en estado SCHEDULED.
    Recalcula los playing handicaps con los nuevos jugadores.
    Crea un nuevo Match con los nuevos jugadores (elimina el anterior).
    """

    def __init__(
        self,
        uow: CompetitionUnitOfWorkInterface,
        golf_course_repository: IGolfCourseRepository,
        user_repository: UserRepositoryInterface,
        handicap_calculator: PlayingHandicapCalculator | None = None,
        scoring_service: ScoringService | None = None,
    ):
        self._uow = uow
        self._scoring_service = scoring_service or ScoringService()
        self._jugadores = JugadoresDelPartido(
            golf_course_repository, user_repository, handicap_calculator
        )

    async def execute(
        self, request: ReassignMatchPlayersRequestDTO, user_id: UserId, is_admin: bool = False
    ) -> ReassignMatchPlayersResponseDTO:
        async with self._uow:
            # 1-4. Validaciones
            match, round_entity, competition = await self._validate(request, user_id, is_admin)

            # 5. Verificar que los jugadores pertenecen al equipo correcto
            team_assignment = await self._uow.team_assignments.find_by_competition(
                round_entity.competition_id
            )
            self._validate_team_membership(team_assignment, request)

            # 5b. Cada lado, exactamente los jugadores de su formato. El reparto
            #     individual lee el primero de cada lado: sin esto, un 2 contra 2
            #     en individual se guardaba en silencio como 1 contra 1.
            per_side = round_entity.match_format.players_per_team()
            if (
                len(request.team_a_player_ids) != per_side
                or len(request.team_b_player_ids) != per_side
            ):
                raise WrongNumberOfPlayersError(
                    f"Un partido {round_entity.match_format.value} lleva {per_side} "
                    f"jugador(es) por equipo; llegaron {len(request.team_a_player_ids)} "
                    f"y {len(request.team_b_player_ids)}"
                )
            # Y distintos: dos plazas con el mismo jugador lo guardaban repetido
            # en su equipo (en foursomes, la media salía solo de su hándicap)
            for side in (request.team_a_player_ids, request.team_b_player_ids):
                if len(set(side)) != len(side):
                    raise WrongNumberOfPlayersError("Hay un jugador repetido en el mismo equipo")

            # 6-7. Los jugadores nuevos, con el reparto de su formato: el mismo
            #      que al generar (BE #477)
            team_a_players, team_b_players = await self._jugadores.construir(
                self._uow,
                round_entity,
                competition,
                [UserId(uid) for uid in request.team_a_player_ids],
                [UserId(uid) for uid in request.team_b_player_ids],
            )

            # 8. Eliminar partido viejo y crear nuevo
            await self._uow.matches.delete(match.id)
            await self._uow.flush()  # Flush DELETE before INSERT (unique constraint)

            new_match = Match.create(
                round_id=match.round_id,
                match_number=match.match_number,
                team_a_players=team_a_players,
                team_b_players=team_b_players,
            )
            # Con sus marcadores sorteados, como al generar (BE #520): sin ellos
            # la app no lo puede anotar y solo marca el que tiene asignado
            new_match.set_marker_assignments(
                self._scoring_service.generate_marker_assignments(
                    new_match.team_a_players,
                    new_match.team_b_players,
                    round_entity.match_format,
                )
            )
            await self._uow.matches.add(new_match)

            return ReassignMatchPlayersResponseDTO(
                match_id=new_match.id.value,
                new_status=new_match.status.value,
                handicap_strokes_given=new_match.handicap_strokes_given,
                strokes_given_to_team=new_match.strokes_given_to_team or "",
                updated_at=new_match.updated_at,
            )

    async def _validate(self, request, user_id, is_admin: bool = False):
        """Validaciones: buscar match, ronda, competicion, verificar creador y estado."""
        match_id = MatchId(request.match_id)
        match = await self._uow.matches.find_by_id(match_id)
        if not match:
            raise MatchNotFoundError(f"No existe partido con ID {request.match_id}")

        if match.status != MatchStatus.SCHEDULED:
            raise MatchNotScheduledError(
                f"Solo se pueden reasignar jugadores en estado SCHEDULED. "
                f"Estado actual: {match.status.value}"
            )

        round_entity = await self._uow.rounds.find_by_id(match.round_id)
        if not round_entity:
            raise MatchNotFoundError("La ronda asociada no existe")

        competition = await self._uow.competitions.find_by_id(round_entity.competition_id)
        if not competition:
            raise MatchNotFoundError("La competicion asociada no existe")

        if not is_admin and not competition.is_creator(user_id):
            raise NotCompetitionCreatorError("Solo el creador puede reasignar jugadores")

        return match, round_entity, competition

    @staticmethod
    def _validate_team_membership(team_assignment, request):
        """Verifica que los jugadores pertenecen al equipo correcto."""
        if not team_assignment:
            raise NoTeamAssignmentError(
                "No hay asignación de equipos. Use AssignTeamsUseCase primero."
            )

        team_a_set = {str(uid.value) for uid in team_assignment.team_a_player_ids}
        team_b_set = {str(uid.value) for uid in team_assignment.team_b_player_ids}

        for uid in request.team_a_player_ids:
            if str(uid) not in team_a_set:
                raise PlayerNotInTeamError(f"El jugador {uid} no pertenece al equipo A")
        for uid in request.team_b_player_ids:
            if str(uid) not in team_b_set:
                raise PlayerNotInTeamError(f"El jugador {uid} no pertenece al equipo B")
