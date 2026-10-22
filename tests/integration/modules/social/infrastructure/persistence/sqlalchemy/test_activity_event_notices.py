"""
Tests de integracion de los avisos de BE-2 en Postgres: borrar lo publicado
desde un origen y contar novedades por tarjeta.
"""

from datetime import datetime, timedelta
from uuid import uuid4

import pytest

from src.modules.social.domain.entities.activity_event import ActivityEvent
from src.modules.social.domain.repositories.activity_event_repository_interface import (
    ActivitySlice,
)
from src.modules.social.domain.value_objects.activity_event_type import ActivityEventType
from src.modules.social.infrastructure.persistence.sqlalchemy.activity_event_repository import (
    SQLAlchemyActivityEventRepository,
)
from src.modules.user.domain.entities.user import User
from src.modules.user.infrastructure.persistence.sqlalchemy.user_repository import (
    SQLAlchemyUserRepository,
)

pytestmark = pytest.mark.integration

T = ActivityEventType
CUANDO = datetime(2026, 10, 22, 12, 0)
TODOS = frozenset(ActivityEventType)


async def _user(db_session) -> User:
    user = User.create(
        first_name="Ana",
        last_name="Garcia",
        email_str=f"notice-{uuid4().hex[:8]}@example.com",
        plain_password="ValidPassword123!",
    )
    await SQLAlchemyUserRepository(db_session).save(user)
    await db_session.commit()
    return user


def _evento(user: User, tipo: ActivityEventType, origen: str) -> ActivityEvent:
    return ActivityEvent.create(
        user_id=user.id,
        type=tipo,
        occurred_at=CUANDO,
        source_match_id=origen,
        published_at=CUANDO + timedelta(minutes=1),
        payload={"competition_id": origen},
    )


async def _tipos(repository, user: User) -> list[tuple[ActivityEventType, str]]:
    eventos = await repository.find_in([ActivitySlice(user_ids=(user.id,), types=TODOS)], 50)
    return sorted((e.type, e.source_match_id) for e in eventos)


async def test_los_tipos_nuevos_caben_y_no_se_duplican(db_session):
    """A7. Given cada tipo nuevo guardado dos veces / When se lee / Then uno de cada."""
    user = await _user(db_session)
    repository = SQLAlchemyActivityEventRepository(db_session)
    nuevos = [
        t
        for t in ActivityEventType
        if t
        not in {
            T.HOLE_IN_ONE,
            T.EAGLE_OR_BETTER,
            T.BIRDIE,
            T.NEW_COURSE,
            T.PERSONAL_BEST,
            T.FIRST_TOURNAMENT,
        }
    ]
    for _ in range(2):
        await repository.add_many([_evento(user, t, "origen-1") for t in nuevos])
        await db_session.commit()

    # Los ocho avisos de BE-2 y ENROLLMENT_CONFIRMED (tabla del 22 oct, C)
    assert len(await _tipos(repository, user)) == len(nuevos) == 9


async def test_borrar_desde_un_origen_de_un_jugador(db_session):
    """A4/B11. Given avisos de dos origenes / When se borra uno de un jugador / Then solo ese."""
    ana = await _user(db_session)
    eva = await _user(db_session)
    repository = SQLAlchemyActivityEventRepository(db_session)
    await repository.add_many(
        [
            _evento(ana, T.ENROLLED_IN_TOURNAMENT, "torneo-1"),
            _evento(ana, T.ENROLLMENT_APPROVED, "torneo-1"),
            _evento(ana, T.ENROLLED_IN_TOURNAMENT, "torneo-2"),
            _evento(eva, T.ENROLLED_IN_TOURNAMENT, "torneo-1"),
        ]
    )
    await db_session.commit()

    borrados = await repository.delete_from_source(
        "torneo-1", [T.ENROLLED_IN_TOURNAMENT], user_id=ana.id
    )
    await db_session.commit()

    assert borrados == 1
    assert await _tipos(repository, ana) == sorted(
        [(T.ENROLLMENT_APPROVED, "torneo-1"), (T.ENROLLED_IN_TOURNAMENT, "torneo-2")]
    )
    assert await _tipos(repository, eva) == [(T.ENROLLED_IN_TOURNAMENT, "torneo-1")]


async def test_borrar_desde_un_origen_de_todos(db_session):
    """C15. Given la clasificacion de dos jugadores / When se reabre / Then de ninguno."""
    ana = await _user(db_session)
    eva = await _user(db_session)
    repository = SQLAlchemyActivityEventRepository(db_session)
    await repository.add_many(
        [
            _evento(ana, T.TOURNAMENT_FINAL_STANDING, "torneo-1"),
            _evento(eva, T.TOURNAMENT_FINAL_STANDING, "torneo-1"),
            _evento(eva, T.TOURNAMENT_FINAL_STANDING, "torneo-2"),
        ]
    )
    await db_session.commit()

    borrados = await repository.delete_from_source("torneo-1", [T.TOURNAMENT_FINAL_STANDING])
    await db_session.commit()

    assert borrados == 2
    assert await _tipos(repository, ana) == []
    assert await _tipos(repository, eva) == [(T.TOURNAMENT_FINAL_STANDING, "torneo-2")]


async def test_borrar_sin_tipos_no_borra_nada(db_session):
    user = await _user(db_session)
    repository = SQLAlchemyActivityEventRepository(db_session)
    await repository.add_many([_evento(user, T.ENROLLMENT_APPROVED, "torneo-1")])
    await db_session.commit()

    assert await repository.delete_from_source("torneo-1", []) == 0
    assert len(await _tipos(repository, user)) == 1


async def test_2_borrar_por_competicion_mira_el_payload(db_session):
    """2. Given avisos de dos torneos con origenes distintos / When se borra uno / Then solo los suyos."""
    user = await _user(db_session)
    repository = SQLAlchemyActivityEventRepository(db_session)
    del_torneo = ActivityEvent.create(
        user_id=user.id,
        type=T.INVITED_TO_TOURNAMENT,
        occurred_at=CUANDO,
        source_match_id="inv-1",
        payload={"competition_id": "torneo-1"},
    )
    await repository.add_many(
        [
            del_torneo,
            _evento(user, T.ENROLLED_IN_TOURNAMENT, "torneo-1"),
            _evento(user, T.ENROLLED_IN_TOURNAMENT, "torneo-2"),
            _evento(user, T.BIRDIE, "torneo-1"),
        ]
    )
    await db_session.commit()

    borrados = await repository.delete_for_competition(
        "torneo-1", [T.INVITED_TO_TOURNAMENT, T.ENROLLED_IN_TOURNAMENT]
    )
    await db_session.commit()

    assert borrados == 2
    assert await _tipos(repository, user) == sorted(
        [(T.ENROLLED_IN_TOURNAMENT, "torneo-2"), (T.BIRDIE, "torneo-1")]
    )
