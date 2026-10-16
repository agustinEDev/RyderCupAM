"""
Tests del repositorio de mapas en memoria (BE #532).

Tiene que comportarse como el de PostgreSQL, donde el campo es la clave del
mapa: guardar un mapa NUEVO para un campo que ya tiene uno es un error (se lee y
se reimporta), y guardar el mismo mapa otra vez es actualizarlo.
"""

from datetime import datetime

import pytest

from src.modules.golf_course.domain.entities.course_hole_map import CourseHoleMap
from src.modules.golf_course.domain.value_objects.geo_point import GeoPoint
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.golf_course.domain.value_objects.mapped_hole import MappedHole
from src.modules.golf_course.domain.value_objects.position_source import PositionSource
from src.modules.golf_course.infrastructure.persistence.in_memory.in_memory_hole_map_repository import (
    InMemoryHoleMapRepository,
)
from src.modules.user.domain.value_objects.user_id import UserId

HOYO = MappedHole(
    number=1,
    play_line=(
        GeoPoint(latitude=36.28, longitude=-5.33),
        GeoPoint(latitude=36.29, longitude=-5.32),
    ),
    line_source=PositionSource.OSM,
)


def _map(course_id: GolfCourseId) -> CourseHoleMap:
    return CourseHoleMap.create(
        golf_course_id=course_id,
        holes=[HOYO],
        osm_reference="way/1",
        imported_at=datetime(2026, 10, 15, 9, 0),
    )


@pytest.mark.asyncio
async def test_saving_the_same_map_again_updates_it():
    """
    GIVEN: Un mapa guardado
    WHEN: Se aprueba y se guarda la misma instancia
    THEN: Se actualiza
    """
    repository = InMemoryHoleMapRepository()
    course_id = GolfCourseId.generate()
    hole_map = _map(course_id)
    await repository.save(hole_map)

    hole_map.approve(reviewer_id=UserId.generate())
    await repository.save(hole_map)

    assert await repository.find_by_golf_course_id(course_id) is hole_map


@pytest.mark.asyncio
async def test_saving_a_second_new_map_for_the_same_course_fails():
    """
    GIVEN: Un campo que ya tiene mapa
    WHEN: Se guarda otro mapa recién creado para ese campo
    THEN: Falla, como en PostgreSQL, y el primero sigue intacto
    """
    repository = InMemoryHoleMapRepository()
    course_id = GolfCourseId.generate()
    first = _map(course_id)
    await repository.save(first)

    with pytest.raises(ValueError, match="already has a hole map"):
        await repository.save(_map(course_id))

    assert await repository.find_by_golf_course_id(course_id) is first
