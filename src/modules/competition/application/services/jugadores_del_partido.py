"""
JugadoresDelPartido - Los jugadores de un partido con el reparto de su formato (BE #502).

Estaba dentro de la reasignación de jugadores; salió a su propio sitio para
compartirlo (BE #502), y es la pieza de quien tenga que construir los dos bandos
de un partido ya generado.

Trae a los usuarios en **una sola consulta**. La reasignación los pedía todos a
la vez (`asyncio.gather`) sobre la misma sesión, y SQLAlchemy no admite dos
operaciones a la vez en una sesión: con jugadores que no estaban ya cargados
podía reventar.
"""

from collections.abc import Sequence
from decimal import Decimal

from src.modules.competition.application.services.course_context import course_context_for
from src.modules.competition.application.services.match_players_builder import (
    MatchPlayersBuilder,
)
from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.entities.round import Round
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.value_objects.enrollment_status import EnrollmentStatus
from src.modules.competition.domain.value_objects.match_player import MatchPlayer
from src.modules.golf_course.domain.repositories.golf_course_repository import IGolfCourseRepository
from src.modules.user.domain.repositories.user_repository_interface import UserRepositoryInterface
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.services.playing_handicap_calculator import (
    PlayingHandicapCalculator,
    TeeRating,
)
from src.shared.domain.value_objects.gender import Gender
from src.shared.domain.value_objects.play_mode import PlayMode


class PlayerNotEnrolledError(Exception):
    """El jugador no tiene inscripción aprobada."""

    pass


class JugadoresDelPartido:
    """Construye los dos bandos de un partido, con los golpes que da su formato."""

    def __init__(
        self,
        golf_course_repository: IGolfCourseRepository,
        user_repository: UserRepositoryInterface,
        handicap_calculator: PlayingHandicapCalculator | None = None,
    ):
        self._gc_repo = golf_course_repository
        self._user_repo = user_repository
        self._calculator = handicap_calculator or PlayingHandicapCalculator()
        self._match_players = MatchPlayersBuilder()

    async def construir(
        self,
        uow: CompetitionUnitOfWorkInterface,
        round_entity: Round,
        competition: Competition,
        team_a_ids: Sequence[UserId],
        team_b_ids: Sequence[UserId],
    ) -> tuple[list[MatchPlayer], list[MatchPlayer]]:
        """
        Raises:
            PlayerNotEnrolledError: Si alguno no tiene inscripción aprobada:
                sin ella no se sabe desde qué barra juega ni con qué hándicap
        """
        enrollments = await uow.enrollments.find_by_competition_and_status(
            round_entity.competition_id, EnrollmentStatus.APPROVED
        )
        enrollment_map = {str(e.user_id.value): e for e in enrollments}
        for uid in [*team_a_ids, *team_b_ids]:
            if str(uid.value) not in enrollment_map:
                raise PlayerNotEnrolledError(f"El jugador {uid} no tiene inscripción aprobada")

        is_scratch = competition.play_mode == PlayMode.SCRATCH
        (
            tee_ratings,
            holes_by_stroke_index,
            user_handicap_map,
            user_gender_map,
            holes_by_tee,
        ) = await self._datos_de_handicap(round_entity, is_scratch, [*team_a_ids, *team_b_ids])

        return self._match_players.build(
            round_entity.match_format,
            list(team_a_ids),
            list(team_b_ids),
            enrollment_map,
            tee_ratings,
            self._calculator,
            round_entity.get_effective_allowance(),
            is_scratch,
            user_handicap_map,
            holes_by_stroke_index,
            user_gender_map,
            competition.max_playing_handicap,
            holes_by_tee,
        )

    async def _datos_de_handicap(self, round_entity: Round, is_scratch: bool, player_ids):
        """Barras y hoyos del campo, y hándicap y género de cada jugador."""
        tee_ratings: dict[tuple[str, str | None], TeeRating] = {}
        holes_by_stroke_index: list[int] = []
        holes_by_tee: dict[tuple[str, str | None], list[int]] = {}
        user_handicap_map: dict[str, Decimal] = {}
        user_gender_map: dict[str, Gender | None] = {}

        if not is_scratch:
            golf_course = await self._gc_repo.find_by_id(round_entity.golf_course_id)
            if not golf_course:
                raise ValueError(
                    "Se requiere un campo de golf para el modo HANDICAP. "
                    "Asocie un campo de golf aprobado a la competición."
                )
            context = course_context_for(golf_course)
            tee_ratings = context.tee_ratings
            holes_by_stroke_index = context.holes_by_stroke_index
            holes_by_tee = context.holes_by_tee

            for user in await self._user_repo.find_by_ids(list(player_ids)):
                if user.id is None:
                    continue
                if user.handicap is not None:
                    user_handicap_map[str(user.id.value)] = Decimal(str(user.handicap.value))
                user_gender_map[str(user.id.value)] = user.gender

        return (
            tee_ratings,
            holes_by_stroke_index,
            user_handicap_map,
            user_gender_map,
            holes_by_tee,
        )
