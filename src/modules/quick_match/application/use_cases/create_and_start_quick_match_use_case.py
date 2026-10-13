"""Caso de Uso: Crear e iniciar una Partida Rapida en una sola peticion (FE #848)."""

from src.modules.golf_course.domain.repositories.golf_course_unit_of_work_interface import (
    GolfCourseUnitOfWorkInterface,
)
from src.modules.golf_course.domain.value_objects.approval_status import ApprovalStatus
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.golf_course.domain.value_objects.tee_color import TeeColor
from src.modules.quick_match.application.dto.quick_match_dto import (
    CreateAndStartQuickMatchRequestDTO,
    QuickMatchResponseDTO,
)
from src.modules.quick_match.application.exceptions import (
    FriendUserNotFoundError,
    GolfCourseNotApprovedError,
    GolfCourseNotFoundError,
    InvalidTeeSelectionError,
    NotFriendsError,
)
from src.modules.quick_match.application.mappers.quick_match_mapper import QuickMatchDTOMapper
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


def _tee(color: str | None, gender: str | None) -> tuple[TeeColor | None, Gender | None]:
    return (TeeColor(color) if color else None, Gender(gender) if gender else None)


class CreateAndStartQuickMatchUseCase:
    """
    Crea la partida con todos sus jugadores, la inicia y fija los hándicaps.

    El asistente ya no crea nada hasta «Confirmar e iniciar» (FE #848): crearla
    en el primer paso dejaba una partida «Pendiente» a quien salía a medias.
    Todo se monta sobre el agregado en memoria —los ids salen de Python, nada
    pide a la BD entre un paso y otro— y se guarda UNA vez al final: si algo
    falla, no queda nada.

    Las lecturas de fuera (campo, usuarios, amistades) van antes de abrir la
    unidad de trabajo de la partida: la sesión es compartida y salir de un
    `async with` anidado hace commit a mitad.
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

    async def execute(self, request: CreateAndStartQuickMatchRequestDTO) -> QuickMatchResponseDTO:
        creator_id = UserId(request.creator_id)
        golf_course_id = GolfCourseId(request.golf_course_id)
        creator_tee = _tee(request.creator_tee_color, request.creator_tee_gender)
        friend_tees = [_tee(f.tee_color, f.tee_gender) for f in request.friends]
        guest_tees = [_tee(g.tee_color, g.tee_gender) for g in request.guests]

        await self._check_course(golf_course_id, [creator_tee, *friend_tees, *guest_tees])

        quick_match = QuickMatch.create(
            id=QuickMatchId.generate(),
            creator_id=creator_id,
            golf_course_id=golf_course_id,
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
        # La plantilla primero: repetidos, el propio creador, cupo y equipos
        # los dice el dominio antes de preguntar a nadie por nada
        friend_ids = [UserId(f.friend_user_id) for f in request.friends]
        for friend, friend_id, (color, gender) in zip(
            request.friends, friend_ids, friend_tees, strict=True
        ):
            quick_match.add_participant(
                QuickMatchParticipant.for_user(
                    friend_id, team=friend.team, tee_color=color, tee_gender=gender
                )
            )
        for guest, (color, gender) in zip(request.guests, guest_tees, strict=True):
            quick_match.add_participant(
                QuickMatchParticipant.for_guest(
                    guest.first_name,
                    guest.last_name,
                    handicap=guest.handicap,
                    team=guest.team,
                    tee_color=color,
                    tee_gender=gender,
                )
            )

        profile_handicaps = await self._profile_handicaps(creator_id, friend_ids)
        await self._check_friendships(creator_id, friend_ids)

        overrides = [(creator_id, request.creator_handicap)] + [
            (friend_id, friend.handicap)
            for friend_id, friend in zip(friend_ids, request.friends, strict=True)
        ]
        for user_id, handicap in overrides:
            if handicap is not None:
                quick_match.set_participant_handicap(ParticipantId(user_id.value), handicap)

        # El `participant_id` de un registrado es su UserId
        quick_match.start([ParticipantId(sid) for sid in request.scorer_user_ids])
        quick_match.freeze_handicaps(profile_handicaps)

        async with self._uow:
            await self._uow.quick_matches.add(quick_match)

        return await QuickMatchDTOMapper.to_response_dto(
            quick_match, self._user_uow, requester_id=creator_id
        )

    async def _check_course(
        self,
        golf_course_id: GolfCourseId,
        tees: list[tuple[TeeColor | None, Gender | None]],
    ) -> None:
        """El campo existe, está aprobado y tiene cada barra elegida."""
        async with self._golf_course_uow:
            golf_course = await self._golf_course_uow.golf_courses.find_by_id(golf_course_id)
        if not golf_course:
            raise GolfCourseNotFoundError(f"Golf course not found: {golf_course_id.value}")
        if golf_course.approval_status != ApprovalStatus.APPROVED:
            raise GolfCourseNotApprovedError(f"Golf course '{golf_course.name}' is not approved.")
        for color, gender in tees:
            if color is not None and not golf_course.has_tee(color, gender):
                raise InvalidTeeSelectionError(
                    f"{color.value} is not a valid tee for this golf course."
                )

    async def _profile_handicaps(
        self, creator_id: UserId, friend_ids: list[UserId]
    ) -> dict[UserId, float | None]:
        """
        El hándicap del perfil del creador y de cada amigo, en una consulta.

        De paso dice si cada amigo existe: el que no está, 404.
        """
        async with self._user_uow:
            users = await self._user_uow.users.find_by_ids([creator_id, *friend_ids])
        found = {user.id: user for user in users if user.id is not None}
        for friend_id in friend_ids:
            if friend_id not in found:
                raise FriendUserNotFoundError(f"User not found: {friend_id.value}")
        return {
            user_id: (user.handicap.value if user.handicap else None)
            for user_id, user in found.items()
        }

    async def _check_friendships(self, creator_id: UserId, friend_ids: list[UserId]) -> None:
        """Solo se añade a quien es amigo ACEPTADO, como al añadirlo uno a uno."""
        async with self._social_uow:
            for friend_id in friend_ids:
                if not await self._social_uow.friendships.are_friends(creator_id, friend_id):
                    raise NotFriendsError(
                        "Only accepted friends can be added directly to a quick match."
                    )
