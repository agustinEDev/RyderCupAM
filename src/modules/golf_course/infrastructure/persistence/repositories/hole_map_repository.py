"""Hole Map Repository - SQLAlchemy Implementation (BE #532)."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.golf_course.domain.entities.course_hole_map import CourseHoleMap
from src.modules.golf_course.domain.repositories.hole_map_repository import IHoleMapRepository
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.golf_course.domain.value_objects.hole_map_status import HoleMapStatus
from src.modules.golf_course.infrastructure.persistence.mappers.golf_course_mapper import (
    golf_courses_table,
)
from src.modules.golf_course.infrastructure.persistence.mappers.hole_map_mapper import (
    golf_course_hole_maps_table,
)

_table = golf_course_hole_maps_table


class HoleMapRepository(IHoleMapRepository):
    """Repositorio de mapas de hoyos con SQLAlchemy."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, hole_map: CourseHoleMap) -> None:
        self._session.add(hole_map)

    async def find_by_golf_course_id(self, golf_course_id: GolfCourseId) -> CourseHoleMap | None:
        result = await self._session.execute(
            select(CourseHoleMap).where(_table.c.golf_course_id == golf_course_id)
        )
        return result.scalars().first()

    async def find_by_golf_course_id_for_update(
        self, golf_course_id: GolfCourseId
    ) -> CourseHoleMap | None:
        # Se bloquea la fila del CAMPO, que siempre existe, y no solo la del mapa:
        # si aún no hay mapa no habría nada que bloquear, y dos importaciones a la
        # vez lo crearían las dos. Así hacen cola y la segunda ve el de la primera
        await self._session.execute(
            select(golf_courses_table.c.id)
            .where(golf_courses_table.c.id == golf_course_id)
            .with_for_update()
        )
        result = await self._session.execute(
            select(CourseHoleMap)
            .where(_table.c.golf_course_id == golf_course_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return result.scalars().first()

    async def find_pending(self) -> list[CourseHoleMap]:
        result = await self._session.execute(
            select(CourseHoleMap)
            .where(_table.c.status == HoleMapStatus.PENDING_REVIEW)
            .order_by(_table.c.imported_at)
        )
        return list(result.scalars().all())
