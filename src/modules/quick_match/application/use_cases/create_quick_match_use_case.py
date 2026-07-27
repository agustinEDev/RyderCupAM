"""Caso de Uso: Crear una Partida Rapida."""

from src.modules.competition.domain.value_objects.match_format import MatchFormat
from src.modules.golf_course.domain.repositories.golf_course_unit_of_work_interface import (
    GolfCourseUnitOfWorkInterface,
)
from src.modules.golf_course.domain.value_objects.approval_status import ApprovalStatus
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.quick_match.application.dto.quick_match_dto import (
    CreateQuickMatchRequestDTO,
    QuickMatchResponseDTO,
)
from src.modules.quick_match.application.exceptions import (
    GolfCourseNotApprovedError,
    GolfCourseNotFoundError,
)
from src.modules.quick_match.application.mappers.quick_match_mapper import QuickMatchDTOMapper
from src.modules.quick_match.domain.entities.quick_match import QuickMatch
from src.modules.quick_match.domain.repositories.quick_match_unit_of_work_interface import (
    QuickMatchUnitOfWorkInterface,
)
from src.modules.quick_match.domain.value_objects.quick_match_id import QuickMatchId
from src.modules.quick_match.domain.value_objects.scoring_format import ScoringFormat
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.modules.user.domain.value_objects.user_id import UserId


class CreateQuickMatchUseCase:
    """Crea una partida rapida con el usuario actual como creador y primer participante."""

    def __init__(
        self,
        uow: QuickMatchUnitOfWorkInterface,
        golf_course_uow: GolfCourseUnitOfWorkInterface,
        user_uow: UserUnitOfWorkInterface,
    ):
        self._uow = uow
        self._golf_course_uow = golf_course_uow
        self._user_uow = user_uow

    async def execute(self, request: CreateQuickMatchRequestDTO) -> QuickMatchResponseDTO:
        golf_course_id = GolfCourseId(request.golf_course_id)

        async with self._golf_course_uow:
            golf_course = await self._golf_course_uow.golf_courses.find_by_id(golf_course_id)
            if not golf_course:
                raise GolfCourseNotFoundError(f"Golf course not found: {request.golf_course_id}")
            if golf_course.approval_status != ApprovalStatus.APPROVED:
                raise GolfCourseNotApprovedError(
                    f"Golf course '{golf_course.name}' is not approved."
                )

        quick_match = QuickMatch.create(
            id=QuickMatchId.generate(),
            creator_id=UserId(request.creator_id),
            golf_course_id=golf_course_id,
            match_format=MatchFormat(request.match_format) if request.match_format else None,
            scoring_format=(
                ScoringFormat(request.scoring_format) if request.scoring_format else None
            ),
            name=request.name,
        )

        async with self._uow:
            await self._uow.quick_matches.add(quick_match)

        return await QuickMatchDTOMapper.to_response_dto(quick_match, self._user_uow)
