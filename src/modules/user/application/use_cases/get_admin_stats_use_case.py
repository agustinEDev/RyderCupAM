"""Caso de Uso: Estadísticas globales de la plataforma (panel de administración)."""

from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.golf_course.domain.repositories.golf_course_unit_of_work_interface import (
    GolfCourseUnitOfWorkInterface,
)
from src.modules.golf_course.domain.value_objects.approval_status import ApprovalStatus
from src.modules.quick_match.domain.repositories.quick_match_unit_of_work_interface import (
    QuickMatchUnitOfWorkInterface,
)
from src.modules.user.application.dto.admin_dto import AdminStatsResponseDTO
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)


class GetAdminStatsUseCase:
    """Agrega contadores globales de los distintos módulos para el panel de admin."""

    def __init__(
        self,
        user_uow: UserUnitOfWorkInterface,
        competition_uow: CompetitionUnitOfWorkInterface,
        quick_match_uow: QuickMatchUnitOfWorkInterface,
        golf_course_uow: GolfCourseUnitOfWorkInterface,
    ):
        self._user_uow = user_uow
        self._competition_uow = competition_uow
        self._quick_match_uow = quick_match_uow
        self._golf_course_uow = golf_course_uow

    async def execute(self) -> AdminStatsResponseDTO:
        async with self._user_uow:
            total_users = await self._user_uow.users.count_all()

        async with self._competition_uow:
            total_competitions = await self._competition_uow.competitions.count_all()

        async with self._quick_match_uow:
            total_quick_matches = await self._quick_match_uow.quick_matches.count_all()

        async with self._golf_course_uow:
            approved = await self._golf_course_uow.golf_courses.find_by_approval_status(
                ApprovalStatus.APPROVED
            )
            pending = await self._golf_course_uow.golf_courses.find_by_approval_status(
                ApprovalStatus.PENDING_APPROVAL
            )

        return AdminStatsResponseDTO(
            total_users=total_users,
            total_competitions=total_competitions,
            total_quick_matches=total_quick_matches,
            total_golf_courses_approved=len(approved),
            total_golf_courses_pending=len(pending),
        )
