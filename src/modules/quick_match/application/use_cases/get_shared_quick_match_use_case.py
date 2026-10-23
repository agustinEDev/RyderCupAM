"""Caso de Uso: ver en solo lectura la partida rapida de un amigo (bloque K)."""

from src.modules.golf_course.domain.repositories.golf_course_unit_of_work_interface import (
    GolfCourseUnitOfWorkInterface,
)
from src.modules.quick_match.application.dto.quick_match_dto import (
    SharedQuickMatchDetailResponseDTO,
)
from src.modules.quick_match.application.exceptions import (
    QuickMatchNotFoundError,
    QuickMatchNotSharedError,
)
from src.modules.quick_match.application.use_cases.get_quick_match_use_case import (
    GetQuickMatchUseCase,
)
from src.modules.quick_match.domain.repositories.quick_match_unit_of_work_interface import (
    QuickMatchUnitOfWorkInterface,
)
from src.modules.quick_match.domain.services.scoring_coverage_service import (
    ScoringCoverageService,
)
from src.modules.quick_match.domain.value_objects.participant_id import ParticipantId
from src.modules.quick_match.domain.value_objects.quick_match_id import QuickMatchId
from src.modules.quick_match.domain.value_objects.quick_match_status import QuickMatchStatus
from src.modules.social.domain.repositories.social_unit_of_work_interface import (
    SocialUnitOfWorkInterface,
)
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.services.match_play_scoring import MatchPlayScoring

# A quien no participa: un unico 403, termine o no la partida (22 oct 2026)
_NOT_SHARED = "You cannot view this quick match."


class GetSharedQuickMatchUseCase:
    """
    La partida rapida de un amigo, en solo lectura (tabla K, 22 oct 2026).

    **Quien entra**: quien la juega, en cualquier estado (el cliente lo lleva a
    su anotacion con `viewer_is_participant`); o, si esta terminada, el amigo de
    al menos uno de sus jugadores con cuenta que cumpla todo esto a la vez: la
    cuenta de ese jugador esta activa y publica su actividad, no hay bloqueo
    entre los dos —una amistad aceptada ya lo excluye— y el no la tiene en su
    papelera. La papelera es de cada uno: si la oculto otro jugador, ese no es
    el camino, pero otro puede serlo. Lo demas, 403, sin decir por que.

    **Los nombres**, como en Actividad (`feed_references.autores_de`): a quien
    no la jugo no le llega el nombre de nadie con quien tenga un bloqueo, lo
    pusiera quien lo pusiera, ni el de una cuenta desactivada; tampoco el de
    los invitados, que lo escribio otro en su partida. El cliente pinta «un
    jugador» o «un invitado».

    El detalle sale del mismo calculo que el de quien anota
    (`GetQuickMatchUseCase.build_detail`): la tarjeta y la clasificacion que ve
    el amigo son las de la partida, no una copia. Todo se lee por lotes: una
    consulta de usuarios, una de amigos y una de bloqueos, juegue quien juegue.
    """

    def __init__(
        self,
        uow: QuickMatchUnitOfWorkInterface,
        user_uow: UserUnitOfWorkInterface,
        social_uow: SocialUnitOfWorkInterface,
        scoring_service: MatchPlayScoring,
        coverage_service: ScoringCoverageService,
        golf_course_uow: GolfCourseUnitOfWorkInterface,
    ):
        self._uow = uow
        self._user_uow = user_uow
        self._social_uow = social_uow
        self._detail = GetQuickMatchUseCase(
            uow, user_uow, scoring_service, coverage_service, golf_course_uow
        )

    async def execute(
        self, quick_match_id_raw: str, viewer_id_raw: str
    ) -> SharedQuickMatchDetailResponseDTO:
        viewer_id = UserId(viewer_id_raw)

        # Las unidades de trabajo, en serie: comparten sesion por debajo
        async with self._uow:
            quick_match = await self._uow.quick_matches.find_by_id(QuickMatchId(quick_match_id_raw))
            if not quick_match:
                raise QuickMatchNotFoundError(f"Quick match not found: {quick_match_id_raw}")
            is_participant = quick_match.is_participant(ParticipantId(viewer_id.value))
            # Al participante se le responde en cualquier estado: el cliente lo
            # lleva a su anotacion con `viewer_is_participant` (22 oct)
            if not is_participant and quick_match.status != QuickMatchStatus.COMPLETED:
                # El mismo mensaje que sin permiso: no le deja deducir el estado
                raise QuickMatchNotSharedError(_NOT_SHARED)
            hole_scores = await self._uow.quick_match_hole_scores.find_by_match(quick_match.id)

        registered = [p.user_id for p in quick_match.participants if p.user_id is not None]
        async with self._user_uow:
            users = {u.id: u for u in await self._user_uow.users.find_by_ids(registered)}

        hidden_names: set[UserId] = set()
        if not is_participant:
            async with self._social_uow:
                friends = set(await self._social_uow.friendships.find_friend_ids(viewer_id))
                blocked = set(await self._social_uow.friendships.find_blocked_ids(viewer_id))
            if not self._shared_by_a_friend(quick_match, users, friends):
                raise QuickMatchNotSharedError(_NOT_SHARED)
            hidden_names = blocked | {
                uid for uid in registered if uid not in users or not users[uid].is_active
            }

        detail = await self._detail.build_detail(quick_match, hole_scores, users, viewer_id)
        shared = SharedQuickMatchDetailResponseDTO(
            **detail.model_dump(), read_only=True, viewer_is_participant=is_participant
        )
        if not is_participant:
            self._hide_names(shared, quick_match, hidden_names)
        return shared

    @staticmethod
    def _shared_by_a_friend(quick_match, users: dict, friends: set) -> bool:
        """Si algun jugador con cuenta es el amigo que la comparte con quien mira."""
        for participant in quick_match.participants:
            user_id = participant.user_id
            if user_id is None or user_id not in friends:
                continue
            user = users.get(user_id)
            if user is None or not user.is_active or not user.share_activity:
                continue
            if quick_match.is_hidden_for(participant.participant_id):
                continue
            return True
        return False

    @staticmethod
    def _hide_names(
        shared: SharedQuickMatchDetailResponseDTO, quick_match, hidden: set[UserId]
    ) -> None:
        """Sin nombre los invitados y los jugadores que quien mira no puede ver."""
        nameless = {
            p.participant_id.value
            for p in quick_match.participants
            if p.user_id is None or p.user_id in hidden
        }
        for participant in shared.participants:
            if participant.participant_id in nameless:
                participant.name = None
        for assignment in shared.scoring_assignments:
            if assignment.scorer_participant_id in nameless:
                assignment.scorer_name = None
