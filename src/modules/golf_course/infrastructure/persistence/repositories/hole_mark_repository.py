"""Hole Mark Repository - SQLAlchemy Implementation (BE #532, PR C)."""

from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.golf_course.domain.entities.hole_mark import HoleMark
from src.modules.golf_course.domain.repositories.hole_mark_repository import (
    IHoleMarkRepository,
)
from src.modules.golf_course.domain.value_objects.geo_point import GeoPoint
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.golf_course.infrastructure.persistence.mappers.hole_mark_mapper import (
    golf_course_hole_marks_table,
)
from src.modules.user.domain.value_objects.user_id import UserId

_table = golf_course_hole_marks_table


def _from_row(row: Any) -> HoleMark:
    tee = (
        None
        if row.tee_latitude is None
        else GeoPoint(latitude=row.tee_latitude, longitude=row.tee_longitude)
    )
    return HoleMark(
        golf_course_id=row.golf_course_id,
        hole_number=row.hole_number,
        user_id=row.user_id,
        tee=tee,
        bends=[GeoPoint(latitude=lat, longitude=lon) for lat, lon in row.bends],
        green_center=GeoPoint(latitude=row.green_latitude, longitude=row.green_longitude),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class HoleMarkRepository(IHoleMarkRepository):
    """Repositorio de marcas de hoyo con SQLAlchemy."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, mark: HoleMark) -> None:
        values = {
            "tee_latitude": mark.tee.latitude if mark.tee else None,
            "tee_longitude": mark.tee.longitude if mark.tee else None,
            "bends": [[bend.latitude, bend.longitude] for bend in mark.bends],
            "green_latitude": mark.green_center.latitude,
            "green_longitude": mark.green_center.longitude,
            "updated_at": mark.updated_at,
        }
        # Upsert: volver a marcar sustituye la marca y conserva cuándo se hizo la
        # primera; dos envíos a la vez (el de la cola sin cobertura y uno nuevo)
        # no chocan en la clave
        statement = insert(_table).values(
            golf_course_id=mark.golf_course_id,
            user_id=mark.user_id,
            hole_number=mark.hole_number,
            created_at=mark.created_at,
            **values,
        )
        await self._session.execute(
            statement.on_conflict_do_update(index_elements=list(_table.primary_key), set_=values)
        )

    async def find_by_course_and_user(
        self, golf_course_id: GolfCourseId, user_id: UserId
    ) -> list[HoleMark]:
        result = await self._session.execute(
            select(_table)
            .where(_table.c.golf_course_id == golf_course_id, _table.c.user_id == user_id)
            .order_by(_table.c.hole_number)
        )
        return [_from_row(row) for row in result]
