"""
Integration tests del repositorio de marcas de hoyo (BE #532, PR C).

Una fila por campo, jugador y hoyo, escrita con un upsert: lo que se comprueba
es que la marca sale de PostgreSQL como entró, que volver a marcar la sustituye
conservando la fecha de la primera, y que se va con la cuenta y con el campo.
"""

from datetime import datetime

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from src.modules.golf_course.domain.entities.hole_mark import HoleMark
from src.modules.golf_course.domain.value_objects.geo_point import GeoPoint
from src.modules.golf_course.infrastructure.persistence.repositories.hole_mark_repository import (
    HoleMarkRepository,
)
from src.modules.user.domain.value_objects.user_id import UserId
from tests.integration.modules.golf_course.infrastructure.persistence.test_hole_map_repository import (
    _insert_user,
    _saved_course,
)

pytestmark = [pytest.mark.integration]

M_PER_DEGREE = 6_371_000.0 * 3.141592653589793 / 180
SALIDA = GeoPoint(latitude=36.28, longitude=-5.33)
CODO = GeoPoint(latitude=36.2815, longitude=-5.331)
CODO_2 = GeoPoint(latitude=36.282, longitude=-5.3312)
GREEN = GeoPoint(latitude=36.28 + 300 / M_PER_DEGREE, longitude=-5.33)
PRIMERA = datetime(2026, 10, 15, 9, 0, 0, 123456)
SEGUNDA = datetime(2026, 10, 15, 10, 30)


def _mark(course_id, user_id, hole=1, tee=SALIDA, bends=(), green=GREEN, at=PRIMERA):
    return HoleMark(
        golf_course_id=course_id,
        hole_number=hole,
        user_id=user_id,
        tee=tee,
        bends=bends,
        green_center=green,
        created_at=at,
        updated_at=at,
    )


async def _player(db_session) -> UserId:
    uid = UserId.generate()
    await _insert_user(db_session, uid)
    return uid


@pytest.mark.asyncio
async def test_k1_round_trip(db_session):
    """
    GIVEN: Una marca con dos codos y otra solo de green
    WHEN: Se guardan y se leen
    THEN: Salen igual (puntos, codos en orden, salida nula y fechas), por orden de hoyo
    """
    player = await _player(db_session)
    course_id = await _saved_course(db_session, player)
    repository = HoleMarkRepository(db_session)
    completa = _mark(course_id, player, hole=4, bends=(CODO, CODO_2))
    solo_green = _mark(course_id, player, hole=2, tee=None)

    await repository.save(completa)
    await repository.save(solo_green)
    # Sin índice, PostgreSQL las daría en el orden en que entraron (4, 2): el
    # orden lo tiene que poner la consulta, no la clave primaria
    await db_session.execute(text("SET LOCAL enable_indexscan = off"))
    await db_session.execute(text("SET LOCAL enable_bitmapscan = off"))
    await db_session.execute(text("SET LOCAL enable_indexonlyscan = off"))
    found = await repository.find_by_course_and_user(course_id, player)

    assert [m.hole_number for m in found] == [2, 4]
    assert found[0].tee is None
    assert found[0].bends == ()
    assert found[1].tee == SALIDA
    assert found[1].bends == (CODO, CODO_2)
    assert found[1].green_center == GREEN
    assert found[1].created_at == found[1].updated_at == PRIMERA


@pytest.mark.asyncio
async def test_k2_marking_again_replaces_and_keeps_the_first_date(db_session):
    """
    GIVEN: Una marca guardada
    WHEN: El mismo jugador vuelve a marcar el hoyo, más tarde y sin codos
    THEN: Queda una sola fila con lo nuevo; creada en la primera fecha, actualizada en la segunda
    """
    player = await _player(db_session)
    course_id = await _saved_course(db_session, player)
    repository = HoleMarkRepository(db_session)
    await repository.save(_mark(course_id, player, bends=(CODO,)))
    otro_green = GeoPoint(latitude=GREEN.latitude + 0.0005, longitude=-5.33)

    await repository.save(_mark(course_id, player, green=otro_green, at=SEGUNDA))

    (mark,) = await repository.find_by_course_and_user(course_id, player)
    assert mark.bends == ()
    assert mark.green_center == otro_green
    assert mark.created_at == PRIMERA
    assert mark.updated_at == SEGUNDA


@pytest.mark.asyncio
async def test_k3_marks_are_per_player_and_per_course(db_session):
    """
    GIVEN: Dos jugadores con marca en el mismo hoyo, y el primero también en otro campo
    WHEN: Se piden las de cada uno en el primer campo
    THEN: Cada uno, la suya
    """
    yo, otro = await _player(db_session), await _player(db_session)
    course_id = await _saved_course(db_session, yo)
    otro_campo = await _saved_course(db_session, yo)
    repository = HoleMarkRepository(db_session)
    await repository.save(_mark(course_id, yo))
    await repository.save(_mark(course_id, otro, bends=(CODO,)))
    await repository.save(_mark(otro_campo, yo, hole=9))

    mias = await repository.find_by_course_and_user(course_id, yo)
    suyas = await repository.find_by_course_and_user(course_id, otro)

    assert [(m.hole_number, m.bends) for m in mias] == [(1, ())]
    assert [(m.hole_number, m.bends) for m in suyas] == [(1, (CODO,))]


@pytest.mark.asyncio
async def test_k4_marks_go_with_the_account_and_with_the_course(db_session):
    """
    GIVEN: Marcas de un jugador en un campo
    WHEN: Se borra su cuenta; y, en otro caso, el campo
    THEN: Sus marcas desaparecen
    """
    creador = await _player(db_session)
    player = await _player(db_session)
    course_id = await _saved_course(db_session, creador)
    otro_campo = await _saved_course(db_session, creador)
    repository = HoleMarkRepository(db_session)
    await repository.save(_mark(course_id, player))
    await repository.save(_mark(otro_campo, creador))

    await db_session.execute(text("DELETE FROM users WHERE id = :id"), {"id": str(player)})
    await db_session.execute(
        text("DELETE FROM golf_courses WHERE id = :id"), {"id": otro_campo.value}
    )

    assert await repository.find_by_course_and_user(course_id, player) == []
    assert await repository.find_by_course_and_user(otro_campo, creador) == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "sql",
    [
        # hoyo 19
        "INSERT INTO golf_course_hole_marks VALUES (:c, :u, 19, 36.28, -5.33, '[]', 36.29, -5.33, now(), now())",
        # salida a medias
        "INSERT INTO golf_course_hole_marks VALUES (:c, :u, 1, 36.28, NULL, '[]', 36.29, -5.33, now(), now())",
        # tres codos
        "INSERT INTO golf_course_hole_marks VALUES (:c, :u, 1, 36.28, -5.33, '[[1,1],[1,1],[1,1]]', 36.29, -5.33, now(), now())",
        # codos sin salida
        "INSERT INTO golf_course_hole_marks VALUES (:c, :u, 1, NULL, NULL, '[[1,1]]', 36.29, -5.33, now(), now())",
        # codos que no son una lista
        "INSERT INTO golf_course_hole_marks VALUES (:c, :u, 1, 36.28, -5.33, '{}', 36.29, -5.33, now(), now())",
    ],
)
async def test_k5_the_database_rejects_impossible_rows(db_session, sql):
    """
    GIVEN: Una fila que no pasa por el dominio
    WHEN: Es de un hoyo 19, con la salida a medias, tres codos, codos sin salida
          o codos que no son una lista
    THEN: La BD la rechaza
    """
    player = await _player(db_session)
    course_id = await _saved_course(db_session, player)

    with pytest.raises(IntegrityError):
        await db_session.execute(text(sql), {"c": course_id.value, "u": str(player)})


@pytest.mark.asyncio
async def test_k6_an_older_mark_does_not_replace_a_newer_one(db_session):
    """
    GIVEN: Una marca guardada de las 10:30
    WHEN: Se guarda otra del mismo jugador y hoyo hecha a las 9:00 (llegó tarde de la cola)
    THEN: Se queda la de las 10:30; y `find` la devuelve
    """
    player = await _player(db_session)
    course_id = await _saved_course(db_session, player)
    repository = HoleMarkRepository(db_session)
    await repository.save(_mark(course_id, player, bends=(CODO,), at=SEGUNDA))

    await repository.save(_mark(course_id, player, at=PRIMERA))

    mark = await repository.find(course_id, 1, player)
    assert mark is not None
    assert mark.bends == (CODO,)
    assert mark.updated_at == SEGUNDA
    assert await repository.find(course_id, 2, player) is None
    assert await repository.find(course_id, 1, UserId.generate()) is None


@pytest.mark.asyncio
async def test_k6_the_same_time_replaces(db_session):
    """
    GIVEN: Una marca guardada
    WHEN: Llega otra con la misma fecha
    THEN: La sustituye (empate: gana la que llega)
    """
    player = await _player(db_session)
    course_id = await _saved_course(db_session, player)
    repository = HoleMarkRepository(db_session)
    await repository.save(_mark(course_id, player))

    await repository.save(_mark(course_id, player, bends=(CODO,)))

    mark = await repository.find(course_id, 1, player)
    assert mark is not None
    assert mark.bends == (CODO,)


@pytest.mark.asyncio
async def test_k7_a_row_outside_todays_limits_still_loads(db_session):
    """
    GIVEN: Una fila con el green a 10 m de la salida (escrita fuera del caso de uso,
           o válida con unos límites anteriores)
    WHEN: Se leen las marcas del jugador
    THEN: Se carga, sin error
    """
    player = await _player(db_session)
    course_id = await _saved_course(db_session, player)
    await db_session.execute(
        text(
            "INSERT INTO golf_course_hole_marks VALUES "
            "(:c, :u, 1, 36.28, -5.33, '[]', 36.28009, -5.33, now(), now())"
        ),
        {"c": course_id.value, "u": str(player)},
    )

    (mark,) = await HoleMarkRepository(db_session).find_by_course_and_user(course_id, player)

    assert mark.green_center == GeoPoint(latitude=36.28009, longitude=-5.33)
