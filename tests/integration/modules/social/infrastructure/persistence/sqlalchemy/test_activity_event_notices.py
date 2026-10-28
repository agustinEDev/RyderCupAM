"""
Tests de integracion de los avisos de BE-2 en Postgres: borrar lo publicado
desde un origen y contar novedades por tarjeta.
"""

from datetime import datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

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

    # Los ocho avisos de BE-2, ENROLLMENT_CONFIRMED (C), TEE_TIME_ASSIGNED (G),
    # ENROLLMENT_REMOVED (release social 2) y los tres de la inscripcion
    # directa (release social 3)
    assert len(await _tipos(repository, user)) == len(nuevos) == 15


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


def _salida(user: User, ronda: str, torneo: str) -> ActivityEvent:
    return ActivityEvent.create(
        user_id=user.id,
        type=T.TEE_TIME_ASSIGNED,
        occurred_at=CUANDO,
        source_match_id=ronda,
        payload={"competition_id": torneo, "round_id": ronda},
    )


async def test_g3_borrar_desde_un_origen_de_varios_jugadores(db_session):
    """G3. Given salidas de tres jugadores en dos rondas / When se retiran dos de una / Then solo esos."""
    ana, eva, luz = [await _user(db_session) for _ in range(3)]
    repository = SQLAlchemyActivityEventRepository(db_session)
    await repository.add_many(
        [
            _salida(ana, "ronda-1", "torneo-1"),
            _salida(eva, "ronda-1", "torneo-1"),
            _salida(luz, "ronda-1", "torneo-1"),
            _salida(ana, "ronda-2", "torneo-1"),
            _evento(eva, T.ENROLLED_IN_TOURNAMENT, "ronda-1"),
        ]
    )
    await db_session.commit()

    borrados = await repository.delete_from_source_for_users(
        "ronda-1", [T.TEE_TIME_ASSIGNED], [ana.id, eva.id]
    )
    await db_session.commit()

    assert borrados == 2
    assert await _tipos(repository, ana) == [(T.TEE_TIME_ASSIGNED, "ronda-2")]
    assert await _tipos(repository, eva) == [(T.ENROLLED_IN_TOURNAMENT, "ronda-1")]
    assert await _tipos(repository, luz) == [(T.TEE_TIME_ASSIGNED, "ronda-1")]


async def test_g3_sin_jugadores_no_borra_nada(db_session):
    user = await _user(db_session)
    repository = SQLAlchemyActivityEventRepository(db_session)
    await repository.add_many([_salida(user, "ronda-1", "torneo-1")])
    await db_session.commit()

    assert await repository.delete_from_source_for_users("ronda-1", [T.TEE_TIME_ASSIGNED], []) == 0
    assert len(await _tipos(repository, user)) == 1


async def test_g9_borrar_por_competicion_de_un_jugador(db_session):
    """G9. Given salidas de dos jugadores en dos torneos / When uno se retira de uno / Then solo las suyas de ese."""
    ana, eva = [await _user(db_session) for _ in range(2)]
    repository = SQLAlchemyActivityEventRepository(db_session)
    await repository.add_many(
        [
            _salida(ana, "ronda-1", "torneo-1"),
            _salida(ana, "ronda-2", "torneo-1"),
            _salida(ana, "ronda-3", "torneo-2"),
            _salida(eva, "ronda-1", "torneo-1"),
        ]
    )
    await db_session.commit()

    borrados = await repository.delete_for_competition(
        "torneo-1", [T.TEE_TIME_ASSIGNED], user_id=ana.id
    )
    await db_session.commit()

    assert borrados == 2
    assert await _tipos(repository, ana) == [(T.TEE_TIME_ASSIGNED, "ronda-3")]
    assert await _tipos(repository, eva) == [(T.TEE_TIME_ASSIGNED, "ronda-1")]


async def test_g3_el_candado_de_un_torneo_dura_lo_que_su_transaccion(db_session):
    """
    G3. Mientras una publicacion tiene el torneo bloqueado, otra no lo coge; la
    de otro torneo, si. Al confirmar se suelta solo.
    """

    async def _la_coge(origen: str) -> bool:
        async with AsyncSession(bind=db_session.bind) as otra:
            cogido = (
                await otra.execute(
                    text("SELECT pg_try_advisory_xact_lock(hashtextextended(:clave, 0))"),
                    {"clave": f"activity-scope:{origen}"},
                )
            ).scalar()
            await otra.rollback()
            return bool(cogido)

    repository = SQLAlchemyActivityEventRepository(db_session)
    await repository.lock_scope("torneo-1")

    assert await _la_coge("torneo-1") is False
    assert await _la_coge("torneo-2") is True
    await db_session.commit()
    assert await _la_coge("torneo-1") is True


async def test_g3_lo_publicado_desde_un_origen(db_session):
    ana, eva = [await _user(db_session) for _ in range(2)]
    repository = SQLAlchemyActivityEventRepository(db_session)
    await repository.add_many(
        [
            _salida(ana, "ronda-1", "torneo-1"),
            _salida(eva, "ronda-1", "torneo-1"),
            _salida(ana, "ronda-2", "torneo-1"),
            _evento(eva, T.ENROLLED_IN_TOURNAMENT, "ronda-1"),
        ]
    )
    await db_session.commit()

    encontrados = await repository.find_from_source("ronda-1", [T.TEE_TIME_ASSIGNED])

    assert sorted((str(e.user_id.value), e.payload["round_id"]) for e in encontrados) == sorted(
        [(str(ana.id.value), "ronda-1"), (str(eva.id.value), "ronda-1")]
    )
    assert await repository.find_from_source("ronda-1", []) == []


async def test_borrar_por_parejas_de_jugador_y_origen_en_un_solo_delete(db_session):
    """Revision: las invitaciones cerradas se retiran en lote, cada una solo de su jugador."""
    ana = await _user(db_session)
    eva = await _user(db_session)
    repository = SQLAlchemyActivityEventRepository(db_session)
    await repository.add_many(
        [
            _evento(ana, T.INVITED_TO_TOURNAMENT, "inv-a"),
            _evento(ana, T.INVITED_TO_TOURNAMENT, "inv-otra"),
            _evento(eva, T.INVITED_TO_TOURNAMENT, "inv-e"),
            _evento(eva, T.INVITED_TO_TOURNAMENT, "inv-a"),
            _evento(ana, T.ENROLLMENT_APPROVED, "inv-a"),
        ]
    )
    await db_session.commit()

    borrados = await repository.delete_pairs(
        T.INVITED_TO_TOURNAMENT, [(ana.id, "inv-a"), (eva.id, "inv-e")]
    )
    await db_session.commit()

    assert borrados == 2
    assert await _tipos(repository, ana) == sorted(
        [(T.ENROLLMENT_APPROVED, "inv-a"), (T.INVITED_TO_TOURNAMENT, "inv-otra")]
    )
    assert await _tipos(repository, eva) == [(T.INVITED_TO_TOURNAMENT, "inv-a")]
    assert await repository.delete_pairs(T.INVITED_TO_TOURNAMENT, []) == 0


def _logro(user: User, tipo: ActivityEventType, origen: str, torneo: str, **extra) -> ActivityEvent:
    return ActivityEvent.create(
        user_id=user.id,
        type=tipo,
        occurred_at=CUANDO,
        source_match_id=origen,
        published_at=CUANDO + timedelta(minutes=1),
        payload={"competition_id": torneo, "from_tournament": True, **extra},
    )


async def _ids(repository, user: User) -> dict[tuple, tuple]:
    eventos = await repository.find_in([ActivitySlice(user_ids=(user.id,), types=TODOS)], 50)
    return {(e.type, e.source_match_id): (e.id, e.payload) for e in eventos}


async def test_replacing_a_tournaments_achievements_keeps_what_did_not_change(db_session):
    """
    Revision final del 22 oct 2026: el ultimo cierre deja exactamente sus
    logros. Lo igual se queda (mismo id), lo cambiado y lo que sobra se van, lo
    nuevo entra; otros torneos y otros tipos, intactos.
    """
    ana = await _user(db_session)
    repository = SQLAlchemyActivityEventRepository(db_session)
    igual = _logro(ana, T.FIRST_TOURNAMENT, "grupo-1", "torneo-1")
    await repository.add_many(
        [
            igual,
            _logro(ana, T.BIRDIE, "grupo-1", "torneo-1", holes=[4]),
            _logro(ana, T.EAGLE_OR_BETTER, "grupo-1", "torneo-1"),
            _logro(ana, T.BIRDIE, "grupo-9", "torneo-2"),
            _evento(ana, T.TOURNAMENT_FINAL_STANDING, "torneo-1"),
        ]
    )
    await db_session.commit()

    await repository.replace_for_competition(
        "torneo-1",
        [T.FIRST_TOURNAMENT, T.BIRDIE, T.EAGLE_OR_BETTER, T.NEW_COURSE],
        [
            _logro(ana, T.FIRST_TOURNAMENT, "grupo-1", "torneo-1"),
            _logro(ana, T.BIRDIE, "grupo-1", "torneo-1", holes=[5]),
            _logro(ana, T.NEW_COURSE, "grupo-1", "torneo-1"),
        ],
    )
    await db_session.commit()

    quedan = await _ids(repository, ana)
    assert set(quedan) == {
        (T.FIRST_TOURNAMENT, "grupo-1"),
        (T.BIRDIE, "grupo-1"),
        (T.NEW_COURSE, "grupo-1"),
        (T.BIRDIE, "grupo-9"),
        (T.TOURNAMENT_FINAL_STANDING, "torneo-1"),
    }
    assert quedan[(T.FIRST_TOURNAMENT, "grupo-1")][0] == igual.id
    assert quedan[(T.BIRDIE, "grupo-1")][1]["holes"] == [5]


# ==================== Avisos de salida retirados por un cambio (22 oct) ====================


async def test_withdrawn_tee_times_are_remembered_per_round_without_duplicates(db_session):
    ana, eva = await _user(db_session), await _user(db_session)
    repository = SQLAlchemyActivityEventRepository(db_session)

    await repository.remember_withdrawn_tee_times("ronda-1", "torneo-1", [ana.id, eva.id])
    await repository.remember_withdrawn_tee_times("ronda-1", "torneo-1", [ana.id])
    await repository.remember_withdrawn_tee_times("ronda-2", "torneo-1", [ana.id])
    await repository.remember_withdrawn_tee_times("ronda-3", "torneo-1", [])
    await db_session.commit()

    assert await repository.withdrawn_tee_times("ronda-1") == {ana.id, eva.id}
    assert await repository.withdrawn_tee_times("ronda-2") == {ana.id}
    assert await repository.withdrawn_tee_times("ronda-3") == set()


async def test_forgetting_withdrawn_tee_times_of_a_round(db_session):
    ana, eva = await _user(db_session), await _user(db_session)
    repository = SQLAlchemyActivityEventRepository(db_session)
    await repository.remember_withdrawn_tee_times("ronda-1", "torneo-1", [ana.id, eva.id])
    await repository.remember_withdrawn_tee_times("ronda-2", "torneo-1", [ana.id])

    await repository.forget_withdrawn_tee_times("ronda-1", [ana.id])
    await repository.forget_withdrawn_tee_times("ronda-1", [])
    await db_session.commit()

    assert await repository.withdrawn_tee_times("ronda-1") == {eva.id}
    assert await repository.withdrawn_tee_times("ronda-2") == {ana.id}


async def test_forgetting_withdrawn_tee_times_of_a_competition(db_session):
    ana, eva = await _user(db_session), await _user(db_session)
    repository = SQLAlchemyActivityEventRepository(db_session)
    await repository.remember_withdrawn_tee_times("ronda-1", "torneo-1", [ana.id, eva.id])
    await repository.remember_withdrawn_tee_times("ronda-2", "torneo-1", [ana.id])
    await repository.remember_withdrawn_tee_times("ronda-9", "torneo-2", [ana.id])

    await repository.forget_withdrawn_tee_times_of_competition("torneo-1", ana.id)
    await db_session.commit()
    assert await repository.withdrawn_tee_times("ronda-1") == {eva.id}
    assert await repository.withdrawn_tee_times("ronda-2") == set()

    await repository.forget_withdrawn_tee_times_of_competition("torneo-1")
    await db_session.commit()
    assert await repository.withdrawn_tee_times("ronda-1") == set()
    assert await repository.withdrawn_tee_times("ronda-9") == {ana.id}


async def test_deleting_the_account_forgets_its_withdrawn_tee_times(db_session):
    ana = await _user(db_session)
    repository = SQLAlchemyActivityEventRepository(db_session)
    await repository.remember_withdrawn_tee_times("ronda-1", "torneo-1", [ana.id])
    await db_session.commit()

    await db_session.execute(text("DELETE FROM users WHERE id = :id"), {"id": str(ana.id.value)})
    await db_session.commit()

    assert await repository.withdrawn_tee_times("ronda-1") == set()
