"""
Casos de uso del mapa de hoyos: verlo y revisarlo (BE #532).

El jugador solo ve un mapa aprobado. El admin ve cualquiera y aprueba o rechaza
la VERSIÓN que tiene delante (su fecha de importación): si mientras la miraba se
reimportó, la revisión no vale y tiene que volver a mirarlo.
"""

from datetime import UTC, datetime

from src.modules.golf_course.application.dtos.hole_map_dtos import (
    HoleMapDTO,
    HoleMapReviewDTO,
    PendingHoleMapDTO,
    ReviewHoleMapRequestDTO,
)
from src.modules.golf_course.application.exceptions import (
    HoleMapChangedError,
    HoleMapNotFoundError,
    HoleMapNotPendingError,
)
from src.modules.golf_course.application.mappers.hole_map_geojson import (
    to_hole_map_dto,
    to_hole_map_review_dto,
)
from src.modules.golf_course.domain.entities.course_hole_map import CourseHoleMap
from src.modules.golf_course.domain.repositories.golf_course_unit_of_work_interface import (
    GolfCourseUnitOfWorkInterface,
)
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.golf_course.domain.value_objects.hole_map_status import HoleMapStatus
from src.modules.user.domain.value_objects.user_id import UserId


def _naive_utc(moment: datetime) -> datetime:
    """La versión que llega puede traer zona; las del mapa van en UTC sin zona."""
    return moment if moment.tzinfo is None else moment.astimezone(UTC).replace(tzinfo=None)


class GetApprovedHoleMapUseCase:
    """El mapa aprobado de un campo, para el jugador."""

    def __init__(self, uow: GolfCourseUnitOfWorkInterface) -> None:
        self._uow = uow

    async def execute(self, golf_course_id: str) -> HoleMapDTO:
        """
        Raises:
            HoleMapNotFoundError: si el campo no tiene mapa aprobado
        """
        async with self._uow:
            hole_map = await self._uow.hole_maps.find_by_golf_course_id(
                GolfCourseId(golf_course_id)
            )
            if hole_map is None or hole_map.status is not HoleMapStatus.APPROVED:
                raise HoleMapNotFoundError(golf_course_id)
            return to_hole_map_dto(hole_map)


class ListPendingHoleMapsUseCase:
    """Los mapas pendientes de revisión, del más antiguo al más reciente."""

    def __init__(self, uow: GolfCourseUnitOfWorkInterface) -> None:
        self._uow = uow

    async def execute(self) -> list[PendingHoleMapDTO]:
        async with self._uow:
            pending = await self._uow.hole_maps.find_pending()
            items = []
            for hole_map in pending:
                course = await self._uow.golf_courses.find_by_id(hole_map.golf_course_id)
                items.append(
                    PendingHoleMapDTO(
                        golf_course_id=str(hole_map.golf_course_id),
                        golf_course_name=course.name if course is not None else "",
                        holes=len(hole_map.holes),
                        holes_needing_green=sum(1 for h in hole_map.holes if h.needs_green),
                        imported_at=hole_map.imported_at,
                        osm_reference=hole_map.osm_reference,
                    )
                )
            return items


class GetHoleMapForReviewUseCase:
    """El mapa de un campo en cualquier estado, para el admin."""

    def __init__(self, uow: GolfCourseUnitOfWorkInterface) -> None:
        self._uow = uow

    async def execute(self, golf_course_id: str) -> HoleMapReviewDTO:
        """
        Raises:
            HoleMapNotFoundError: si el campo no tiene mapa
        """
        async with self._uow:
            hole_map = await self._uow.hole_maps.find_by_golf_course_id(
                GolfCourseId(golf_course_id)
            )
            if hole_map is None:
                raise HoleMapNotFoundError(golf_course_id)
            return to_hole_map_review_dto(hole_map)


class _ReviewHoleMapUseCase:
    """Lo común de aprobar y rechazar: el mapa, bloqueado, en la versión vista."""

    def __init__(self, uow: GolfCourseUnitOfWorkInterface) -> None:
        self._uow = uow

    def _apply(self, hole_map: CourseHoleMap, reviewer_id: UserId, reason: str | None) -> None:
        raise NotImplementedError

    async def execute(
        self, golf_course_id: str, reviewer_id: UserId, request: ReviewHoleMapRequestDTO
    ) -> HoleMapReviewDTO:
        """
        Raises:
            HoleMapNotFoundError: si el campo no tiene mapa
            HoleMapChangedError: si la versión no es la actual
            HoleMapNotPendingError: si ya está aprobado o rechazado
            ValueError: si el motivo de rechazo pasa de 500 caracteres
        """
        async with self._uow:
            # Bloqueado: una reimportación a la vez no se cuela entre comprobar y escribir
            hole_map = await self._uow.hole_maps.find_by_golf_course_id_for_update(
                GolfCourseId(golf_course_id)
            )
            if hole_map is None:
                raise HoleMapNotFoundError(golf_course_id)
            if hole_map.status is not HoleMapStatus.PENDING_REVIEW:
                raise HoleMapNotPendingError(golf_course_id)
            if _naive_utc(request.version) != hole_map.imported_at:
                raise HoleMapChangedError(golf_course_id)
            self._apply(hole_map, reviewer_id, request.reason)
            await self._uow.hole_maps.save(hole_map)
            return to_hole_map_review_dto(hole_map)


class ApproveHoleMapUseCase(_ReviewHoleMapUseCase):
    """Un admin aprueba el mapa: a partir de aquí lo ven los jugadores."""

    def _apply(self, hole_map: CourseHoleMap, reviewer_id: UserId, reason: str | None) -> None:
        hole_map.approve(reviewer_id=reviewer_id)


class RejectHoleMapUseCase(_ReviewHoleMapUseCase):
    """Un admin rechaza el mapa, con un motivo opcional."""

    def _apply(self, hole_map: CourseHoleMap, reviewer_id: UserId, reason: str | None) -> None:
        hole_map.reject(reviewer_id=reviewer_id, reason=reason)
