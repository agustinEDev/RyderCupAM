"""Caso de Uso: Crear e iniciar una Partida Rapida en una sola peticion (FE #848)."""

from src.modules.golf_course.domain.repositories.golf_course_unit_of_work_interface import (
    GolfCourseUnitOfWorkInterface,
)
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.golf_course.domain.value_objects.tee_color import TeeColor
from src.modules.quick_match.application.dto.quick_match_dto import (
    CreateAndStartQuickMatchRequestDTO,
    CreateAndStartQuickMatchResponseDTO,
    QuickStartFriendDTO,
    QuickStartGuestDTO,
)
from src.modules.quick_match.application.exceptions import (
    InvalidParticipantError,
    QuickMatchIdTakenError,
)
from src.modules.quick_match.application.mappers.quick_match_mapper import QuickMatchDTOMapper
from src.modules.quick_match.application.services.roster_checks import (
    Tee,
    check_course_and_tees,
    check_friends,
    profile_handicaps,
)
from src.modules.quick_match.domain.entities.quick_match import QuickMatch
from src.modules.quick_match.domain.repositories.quick_match_unit_of_work_interface import (
    QuickMatchUnitOfWorkInterface,
)
from src.modules.quick_match.domain.value_objects.participant_id import ParticipantId
from src.modules.quick_match.domain.value_objects.quick_match_id import QuickMatchId
from src.modules.quick_match.domain.value_objects.quick_match_participant import (
    QuickMatchParticipant,
)
from src.modules.social.domain.repositories.social_unit_of_work_interface import (
    SocialUnitOfWorkInterface,
)
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.gender import Gender
from src.shared.domain.value_objects.match_format import MatchFormat
from src.shared.domain.value_objects.play_mode import PlayMode
from src.shared.domain.value_objects.scoring_format import ScoringFormat


def _tee(color: str | None, gender: str | None) -> Tee:
    return (TeeColor(color) if color else None, Gender(gender) if gender else None)


class CreateAndStartQuickMatchUseCase:
    """
    Crea la partida con todos sus jugadores, la inicia y fija los hándicaps.

    El asistente ya no crea nada hasta «Confirmar e iniciar» (FE #848): crearla
    en el primer paso dejaba una partida «Pendiente» a quien salía a medias.
    Todo se monta sobre el agregado en memoria —los ids salen de Python, nada
    pide a la BD entre un paso y otro— y se guarda UNA vez al final: si algo
    falla, no queda nada.

    El id lo manda el cliente: si la respuesta se pierde con mala cobertura y
    se reintenta, se devuelve la partida que ya existe en vez de crear otra.

    Las lecturas de fuera (campo, usuarios, amistades) van antes de guardar: la
    sesión es compartida y salir de un `async with` anidado hace commit a mitad.
    """

    def __init__(
        self,
        uow: QuickMatchUnitOfWorkInterface,
        golf_course_uow: GolfCourseUnitOfWorkInterface,
        social_uow: SocialUnitOfWorkInterface,
        user_uow: UserUnitOfWorkInterface,
    ):
        self._uow = uow
        self._golf_course_uow = golf_course_uow
        self._social_uow = social_uow
        self._user_uow = user_uow

    async def execute(
        self, request: CreateAndStartQuickMatchRequestDTO
    ) -> CreateAndStartQuickMatchResponseDTO:
        creator_id = UserId(request.creator_id)
        quick_match_id = QuickMatchId(request.quick_match_id)

        # Un reintento con el mismo id: la que ya hay, sin volver a validar
        # nada —se validó al crearla— ni crear otra
        existing = await self._already_created(quick_match_id, creator_id)
        if existing is not None:
            return existing

        creator_tee = _tee(request.creator_tee_color, request.creator_tee_gender)
        await check_course_and_tees(
            self._golf_course_uow,
            GolfCourseId(request.golf_course_id),
            [creator_tee, *(_tee(p.tee_color, p.tee_gender) for p in request.participants)],
        )

        quick_match = QuickMatch.create(
            id=quick_match_id,
            creator_id=creator_id,
            golf_course_id=GolfCourseId(request.golf_course_id),
            match_format=MatchFormat(request.match_format) if request.match_format else None,
            scoring_format=(
                ScoringFormat(request.scoring_format) if request.scoring_format else None
            ),
            name=request.name,
            allowance_percentage=request.allowance_percentage,
            play_mode=PlayMode(request.play_mode),
            creator_tee_color=creator_tee[0],
            creator_tee_gender=creator_tee[1],
        )
        # La plantilla primero, en el orden en que se añadieron: repetidos, el
        # propio creador, cupo y equipos los dice el dominio antes de preguntar
        # a nadie por nada
        for player in request.participants:
            participant = self._participant(player)
            quick_match.add_participant(participant)
            # El hándicap cambiado de un amigo, junto a él: el del invitado ya
            # va dentro de su participante
            if isinstance(player, QuickStartFriendDTO) and player.handicap is not None:
                quick_match.set_participant_handicap(participant.participant_id, player.handicap)
        if request.creator_handicap is not None:
            quick_match.set_participant_handicap(
                ParticipantId(creator_id.value), request.creator_handicap
            )

        friend_ids = [
            UserId(p.friend_user_id)
            for p in request.participants
            if isinstance(p, QuickStartFriendDTO)
        ]
        await check_friends(self._user_uow, self._social_uow, creator_id, friend_ids)

        # El `participant_id` de un registrado es su UserId
        quick_match.start([ParticipantId(sid) for sid in request.scorer_user_ids])
        quick_match.freeze_handicaps(
            await profile_handicaps(self._user_uow, [creator_id, *friend_ids])
        )

        try:
            async with self._uow:
                await self._uow.quick_matches.add(quick_match)
        except Exception:
            # Dos reintentos que se cruzan: los dos vieron que no existía y la
            # otra petición la guardó antes. No es un fallo: es la misma
            # partida. Si no está, el error era otro y sigue su camino
            existing = await self._already_created(quick_match_id, creator_id)
            if existing is None:
                raise
            return existing

        return CreateAndStartQuickMatchResponseDTO(
            quick_match=await QuickMatchDTOMapper.to_response_dto(
                quick_match, self._user_uow, requester_id=creator_id
            ),
            created=True,
        )

    async def _already_created(
        self, quick_match_id: QuickMatchId, creator_id: UserId
    ) -> CreateAndStartQuickMatchResponseDTO | None:
        """La partida con ese id si ya la creó este creador; de otro, 409."""
        async with self._uow:
            existing = await self._uow.quick_matches.find_by_id(quick_match_id)
        if existing is None:
            return None
        if existing.creator_id != creator_id:
            raise QuickMatchIdTakenError(f"Quick match id already in use: {quick_match_id}")
        return CreateAndStartQuickMatchResponseDTO(
            quick_match=await QuickMatchDTOMapper.to_response_dto(
                existing, self._user_uow, requester_id=creator_id
            ),
            created=False,
        )

    @staticmethod
    def _participant(player: QuickStartFriendDTO | QuickStartGuestDTO) -> QuickMatchParticipant:
        color, gender = _tee(player.tee_color, player.tee_gender)
        if isinstance(player, QuickStartFriendDTO):
            return QuickMatchParticipant.for_user(
                UserId(player.friend_user_id),
                team=player.team,
                tee_color=color,
                tee_gender=gender,
            )
        try:
            return QuickMatchParticipant.for_guest(
                player.first_name,
                player.last_name,
                handicap=player.handicap,
                team=player.team,
                tee_color=color,
                tee_gender=gender,
            )
        except ValueError as e:
            # Un nombre que solo era espacios: una petición que no vale
            raise InvalidParticipantError(str(e)) from e
