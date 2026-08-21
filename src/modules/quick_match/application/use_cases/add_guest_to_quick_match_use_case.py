"""Caso de Uso: Añadir a mano un jugador invitado (sin cuenta) a una partida rapida."""

from src.modules.golf_course.domain.repositories.golf_course_unit_of_work_interface import (
    GolfCourseUnitOfWorkInterface,
)
from src.modules.golf_course.domain.value_objects.tee_color import TeeColor
from src.modules.quick_match.application.dto.quick_match_dto import (
    AddGuestParticipantRequestDTO,
    QuickMatchResponseDTO,
)
from src.modules.quick_match.application.exceptions import (
    InvalidTeeSelectionError,
    NotQuickMatchCreatorError,
    QuickMatchNotFoundError,
)
from src.modules.quick_match.application.mappers.quick_match_mapper import QuickMatchDTOMapper
from src.modules.quick_match.domain.repositories.quick_match_unit_of_work_interface import (
    QuickMatchUnitOfWorkInterface,
)
from src.modules.quick_match.domain.value_objects.quick_match_id import QuickMatchId
from src.modules.quick_match.domain.value_objects.quick_match_participant import (
    QuickMatchParticipant,
)
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.gender import Gender


class AddGuestToQuickMatchUseCase:
    """
    Añade a un jugador invitado (sin cuenta en la app) como participante.

    Solo el creador puede añadir participantes. El invitado se identifica con
    nombre/apellidos y un handicap manual opcional; sus resultados tendran que
    ser registrados por uno de los anotadores configurados al iniciar la partida.
    """

    def __init__(
        self,
        uow: QuickMatchUnitOfWorkInterface,
        user_uow: UserUnitOfWorkInterface,
        golf_course_uow: GolfCourseUnitOfWorkInterface,
    ):
        self._uow = uow
        self._user_uow = user_uow
        self._golf_course_uow = golf_course_uow

    async def execute(self, request: AddGuestParticipantRequestDTO) -> QuickMatchResponseDTO:
        requester_id = UserId(request.requester_id)
        tee_color = TeeColor(request.tee_color) if request.tee_color else None
        tee_gender = Gender(request.tee_gender) if request.tee_gender else None

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

            if tee_color is not None:
                async with self._golf_course_uow:
                    golf_course = await self._golf_course_uow.golf_courses.find_by_id(
                        quick_match.golf_course_id
                    )
                    if not golf_course or not golf_course.has_tee(tee_color, tee_gender):
                        raise InvalidTeeSelectionError(
                            f"{tee_color.value} is not a valid tee for this golf course."
                        )

            participant = QuickMatchParticipant.for_guest(
                first_name=request.first_name,
                last_name=request.last_name,
                handicap=request.handicap,
                team=request.team,
                tee_color=tee_color,
                tee_gender=tee_gender,
            )
            quick_match.add_participant(participant)
            await self._uow.quick_matches.update(quick_match)

        return await QuickMatchDTOMapper.to_response_dto(
            quick_match, self._user_uow, requester_id=requester_id
        )
