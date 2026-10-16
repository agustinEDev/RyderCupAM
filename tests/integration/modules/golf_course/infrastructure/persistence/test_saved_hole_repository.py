"""
Integration tests del repositorio de líneas guardadas de los hoyos (BE #575).

Contra PostgreSQL: la línea sale como entró, guardar encima la sustituye, se
lee por campo y en orden de hoyo, reabrir la quita, la tabla frena lo que el
dominio frena y se va con el campo. Y borrar una muestra solo la de ese campo.
"""

from datetime import date, datetime
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from src.modules.golf_course.domain.entities.hole_sample import HoleSample
from src.modules.golf_course.domain.entities.saved_hole import SavedHole
from src.modules.golf_course.domain.value_objects.geo_point import GeoPoint
from src.modules.golf_course.domain.value_objects.tee_color import TeeColor
from src.modules.golf_course.infrastructure.persistence.repositories.hole_sample_repository import (
    HoleSampleRepository,
)
from src.modules.golf_course.infrastructure.persistence.repositories.saved_hole_repository import (
    SavedHoleRepository,
)
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.gender import Gender
from tests.integration.modules.golf_course.infrastructure.persistence.test_hole_map_repository import (
    _insert_user,
    _saved_course,
)

SALIDA = GeoPoint(latitude=36.28, longitude=-5.33)
CODO = GeoPoint(latitude=36.2815, longitude=-5.331)
GREEN = GeoPoint(latitude=36.2827, longitude=-5.33)


async def _course(db_session):
    creator = UserId.generate()
    await _insert_user(db_session, creator)
    return await _saved_course(db_session, creator), creator


def _hole(course_id, admin, hole=1, bends=(CODO,), green=GREEN):
    return SavedHole.reconstruct(
        golf_course_id=course_id,
        hole_number=hole,
        tee=SALIDA,
        bends=bends,
        green_center=green,
        saved_by=admin,
        saved_at=datetime(2026, 10, 17, 9, 0),
    )


@pytest.mark.asyncio
async def test_s1_a_line_comes_back_as_it_went_in_and_saving_again_replaces_it(db_session):
    course_id, admin = await _course(db_session)
    repository = SavedHoleRepository(db_session)
    await repository.save(_hole(course_id, admin))

    otro_admin = UserId.generate()
    await _insert_user(db_session, otro_admin)
    nueva = SavedHole.reconstruct(
        golf_course_id=course_id,
        hole_number=1,
        tee=SALIDA,
        bends=(),
        green_center=GREEN,
        saved_by=otro_admin,
        saved_at=datetime(2026, 10, 18, 7, 30),
    )
    await repository.save(nueva)

    hole = await repository.get(course_id, 1)
    assert (hole.tee, hole.bends, hole.green_center) == (SALIDA, (), GREEN)
    assert (hole.saved_by, hole.saved_at) == (otro_admin, datetime(2026, 10, 18, 7, 30))


@pytest.mark.asyncio
async def test_s2_listed_by_hole_and_only_of_that_course(db_session):
    course_id, admin = await _course(db_session)
    otro, _ = await _course(db_session)
    repository = SavedHoleRepository(db_session)
    for hole in (5, 2):
        await repository.save(_hole(course_id, admin, hole=hole))
    await repository.save(_hole(otro, admin, hole=1))

    assert [h.hole_number for h in await repository.list_by_course(course_id)] == [2, 5]
    assert await repository.get(course_id, 1) is None


@pytest.mark.asyncio
async def test_s3_reopening_deletes_it_and_says_if_there_was_one(db_session):
    course_id, admin = await _course(db_session)
    repository = SavedHoleRepository(db_session)
    await repository.save(_hole(course_id, admin))

    assert await repository.delete(course_id, 1) is True
    assert await repository.delete(course_id, 1) is False
    assert await repository.get(course_id, 1) is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "statement",
    [
        pytest.param("UPDATE golf_course_saved_holes SET hole_number = 19", id="hoyo 19"),
        pytest.param(
            "UPDATE golf_course_saved_holes SET bends = '[[1,2],[1,2],[1,2]]'::jsonb",
            id="tres codos",
        ),
    ],
)
async def test_s4_the_table_rejects_what_the_domain_rejects(db_session, statement):
    course_id, admin = await _course(db_session)
    await SavedHoleRepository(db_session).save(_hole(course_id, admin))

    with pytest.raises(IntegrityError):
        await db_session.execute(text(statement))


@pytest.mark.asyncio
async def test_s5_it_goes_with_the_course(db_session):
    course_id, admin = await _course(db_session)
    await SavedHoleRepository(db_session).save(_hole(course_id, admin))

    await db_session.execute(
        text("DELETE FROM golf_courses WHERE id = :id"), {"id": course_id.value}
    )

    assert await SavedHoleRepository(db_session).get(course_id, 1) is None


@pytest.mark.asyncio
async def test_s6_deleting_a_sample_only_in_its_course(db_session):
    course_id, _ = await _course(db_session)
    otro, _ = await _course(db_session)
    samples = HoleSampleRepository(db_session)
    sample = HoleSample.reconstruct(
        id=uuid4(),
        golf_course_id=course_id,
        hole_number=1,
        tee_color=TeeColor.YELLOW,
        tee_gender=Gender.MALE,
        tee=SALIDA,
        bends=(),
        green_center=GREEN,
        received_on=date(2026, 10, 17),
    )
    await samples.add(sample)

    assert await samples.delete(otro, sample.id) is False
    assert await samples.delete(course_id, sample.id) is True
    assert await samples.list_by_course(course_id) == []
