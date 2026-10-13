"""Caso de Uso: Añadir un amigo directamente a una partida rapida."""

from src.modules.golf_course.domain.repositories.golf_course_unit_of_work_interface import (
    GolfCourseUnitOfWorkInterface,
)
from src.modules.golf_course.domain.value_objects.tee_color import TeeColor
from src.modules.quick_match.application.dto.quick_match_dto import (
    AddParticipantRequestDTO,
    QuickMatchResponseDTO,
)
from src.modules.quick_match.application.exceptions import (
    NotQuickMatchCreatorError,
    QuickMatchNotFoundError,
)
from src.modules.quick_match.application.mappers.quick_match_mapper import QuickMatchDTOMapper
from src.modules.quick_match.application.services.roster_checks import (
    check_friends,
    check_tee_of_match,
)
from src.modules.quick_match.domain.repositories.quick_match_unit_of_work_interface import (
    QuickMatchUnitOfWorkInterface,
)
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


class AddFriendToQuickMatchUseCase:
    """
    Añade a un amigo como participante, sin invitacion intermedia.

    Solo el creador puede añadir participantes, y solo si existe una amistad
    ACCEPTED entre el creador y el usuario a añadir.
    """

    def __init__(
        self,
        uow: QuickMatchUnitOfWorkInterface,
        social_uow: SocialUnitOfWorkInterface,
        user_uow: UserUnitOfWorkInterface,
        golf_course_uow: GolfCourseUnitOfWorkInterface,
    ):
        self._uow = uow
        self._social_uow = social_uow
        self._user_uow = user_uow
        self._golf_course_uow = golf_course_uow

    async def execute(self, request: AddParticipantRequestDTO) -> QuickMatchResponseDTO:
        requester_id = UserId(request.requester_id)
        friend_id = UserId(request.friend_user_id)
        tee_color = TeeColor(request.tee_color) if request.tee_color else None
        tee_gender = Gender(request.tee_gender) if request.tee_gender else None

        await check_friends(self._user_uow, self._social_uow, requester_id, [friend_id])

        await check_tee_of_match(
            self._uow,
            self._golf_course_uow,
            QuickMatchId(request.quick_match_id),
            requester_id,
            (tee_color, tee_gender),
        )

        async with self._uow:
            quick_match = await self._uow.quick_matches.find_by_id_for_update(
                QuickMatchId(request.quick_match_id)
            )
            if not quick_match:
                raise QuickMatchNotFoundError(f"Quick match not found: {request.quick_match_id}")

            if quick_match.creator_id != requester_id:
                raise NotQuickMatchCreatorError(
                    "Only the quick match creator can add participants."
                )

            participant = QuickMatchParticipant.for_user(
                friend_id,
                team=request.team,
                tee_color=tee_color,
                tee_gender=tee_gender,
            )
            quick_match.add_participant(participant)
            await self._uow.quick_matches.update(quick_match)

        return await QuickMatchDTOMapper.to_response_dto(
            quick_match, self._user_uow, requester_id=requester_id
        )
