"""
Tests de integracion: un logro que se publico oculto y se retira vuelve oculto
si se publica otra vez con la misma identidad (jugador, tipo y origen). Fallo
del probador del 23 oct 2026: reabrir y cerrar el mismo torneo lo destapaba.
"""

from datetime import datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import text

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
CUANDO = datetime(2026, 10, 23, 12, 0)
TODOS = frozenset(ActivityEventType)


async def _user(db_session) -> User:
    user = User.create(
        first_name="Diego",
        last_name="Garcia",
        email_str=f"hidden-{uuid4().hex[:8]}@example.com",
        plain_password="ValidPassword123!",
    )
    await SQLAlchemyUserRepository(db_session).save(user)
    await db_session.commit()
    return user


def _logro(
    user: User,
    tipo: ActivityEventType,
    origen: str,
    torneo: str = "torneo-1",
    *,
    visible: bool = True,
    **extra,
) -> ActivityEvent:
    return ActivityEvent.create(
        user_id=user.id,
        type=tipo,
        occurred_at=CUANDO,
        source_match_id=origen,
        published_at=CUANDO + timedelta(minutes=1),
        payload={"competition_id": torneo, "from_tournament": True, **extra},
        visible_to_friends=visible,
    )


async def _visibles(repository, user: User) -> dict[tuple, bool]:
    eventos = await repository.find_in([ActivitySlice(user_ids=(user.id,), types=TODOS)], 50)
    return {(e.type, e.source_match_id): e.visible_to_friends for e in eventos}


async def _apuntes(db_session) -> int:
    resultado = await db_session.execute(text("SELECT count(*) FROM withdrawn_hidden_achievements"))
    return resultado.scalar_one()


async def test_retired_hidden_by_reopening_comes_back_hidden(db_session):
    diego = await _user(db_session)
    repository = SQLAlchemyActivityEventRepository(db_session)
    await repository.add_many(
        [
            _logro(diego, T.BIRDIE, "grupo-1", visible=False),
            _logro(diego, T.PERSONAL_BEST, "grupo-1", visible=True),
        ]
    )
    await db_session.commit()

    await repository.delete_for_competition("torneo-1", [T.BIRDIE, T.PERSONAL_BEST])
    await db_session.commit()
    await repository.replace_for_competition(
        "torneo-1",
        [T.BIRDIE, T.PERSONAL_BEST, T.EAGLE_OR_BETTER],
        [
            _logro(diego, T.BIRDIE, "grupo-1"),
            _logro(diego, T.PERSONAL_BEST, "grupo-1"),
            _logro(diego, T.EAGLE_OR_BETTER, "grupo-1"),
        ],
    )
    await db_session.commit()

    assert await _visibles(repository, diego) == {
        (T.BIRDIE, "grupo-1"): False,
        (T.PERSONAL_BEST, "grupo-1"): True,
        (T.EAGLE_OR_BETTER, "grupo-1"): True,
    }


async def test_replacing_over_a_hidden_one_keeps_it_hidden_and_untouched(db_session):
    """La reapertura no llego a borrar: lo oculto se queda como estaba, con su id."""
    diego = await _user(db_session)
    repository = SQLAlchemyActivityEventRepository(db_session)
    oculto = _logro(diego, T.BIRDIE, "grupo-1", visible=False)
    await repository.add_many([oculto])
    await db_session.commit()

    await repository.replace_for_competition(
        "torneo-1", [T.BIRDIE], [_logro(diego, T.BIRDIE, "grupo-1")]
    )
    await db_session.commit()

    eventos = await repository.find_in([ActivitySlice(user_ids=(diego.id,), types=TODOS)], 50)
    assert [(e.id, e.visible_to_friends) for e in eventos] == [(oculto.id, False)]


async def test_replacing_a_hidden_one_whose_payload_changed_keeps_it_hidden(db_session):
    diego = await _user(db_session)
    repository = SQLAlchemyActivityEventRepository(db_session)
    await repository.add_many([_logro(diego, T.BIRDIE, "grupo-1", visible=False, holes=[4])])
    await db_session.commit()

    await repository.replace_for_competition(
        "torneo-1", [T.BIRDIE], [_logro(diego, T.BIRDIE, "grupo-1", holes=[4, 7])]
    )
    await db_session.commit()

    assert await _visibles(repository, diego) == {(T.BIRDIE, "grupo-1"): False}


async def test_replacing_a_visible_one_with_a_hidden_one_hides_it(db_session):
    diego = await _user(db_session)
    repository = SQLAlchemyActivityEventRepository(db_session)
    await repository.add_many([_logro(diego, T.BIRDIE, "grupo-1")])
    await db_session.commit()

    await repository.replace_for_competition(
        "torneo-1", [T.BIRDIE], [_logro(diego, T.BIRDIE, "grupo-1", visible=False)]
    )
    await db_session.commit()

    assert await _visibles(repository, diego) == {(T.BIRDIE, "grupo-1"): False}


async def test_an_exclusive_retired_hidden_comes_back_hidden(db_session):
    """Lo que retira `keep_only_the_oldest` y luego hereda otra vez."""
    diego = await _user(db_session)
    repository = SQLAlchemyActivityEventRepository(db_session)
    await repository.add_many([_logro(diego, T.NEW_COURSE, "grupo-2", "torneo-2", visible=False)])
    await db_session.commit()

    await repository.delete_pairs(T.NEW_COURSE, [(diego.id, "grupo-2")])
    await db_session.commit()
    await repository.add_many([_logro(diego, T.NEW_COURSE, "grupo-2", "torneo-2")])
    await db_session.commit()

    assert await _visibles(repository, diego) == {(T.NEW_COURSE, "grupo-2"): False}


async def test_retired_from_its_source_comes_back_hidden(db_session):
    diego = await _user(db_session)
    repository = SQLAlchemyActivityEventRepository(db_session)
    await repository.add_many([_logro(diego, T.NEW_COURSE, "partida-1", visible=False)])
    await db_session.commit()

    await repository.delete_from_source("partida-1", [T.NEW_COURSE])
    await db_session.commit()
    await repository.add_many([_logro(diego, T.NEW_COURSE, "partida-1")])
    await db_session.commit()

    assert await _visibles(repository, diego) == {(T.NEW_COURSE, "partida-1"): False}


async def test_a_retired_visible_one_comes_back_visible(db_session):
    diego = await _user(db_session)
    repository = SQLAlchemyActivityEventRepository(db_session)
    await repository.add_many([_logro(diego, T.BIRDIE, "grupo-1")])
    await db_session.commit()

    await repository.delete_for_competition("torneo-1", [T.BIRDIE])
    await repository.add_many([_logro(diego, T.BIRDIE, "grupo-1")])
    await db_session.commit()

    assert await _visibles(repository, diego) == {(T.BIRDIE, "grupo-1"): True}


async def test_only_the_same_identity_is_kept_hidden(db_session):
    """Otro origen, otro tipo u otro jugador toman el interruptor de ahora."""
    diego, eva = await _user(db_session), await _user(db_session)
    repository = SQLAlchemyActivityEventRepository(db_session)
    await repository.add_many([_logro(diego, T.BIRDIE, "grupo-1", visible=False)])
    await repository.delete_for_competition("torneo-1", [T.BIRDIE])
    await db_session.commit()

    await repository.add_many(
        [
            _logro(diego, T.BIRDIE, "grupo-2"),
            _logro(diego, T.EAGLE_OR_BETTER, "grupo-1"),
            _logro(eva, T.BIRDIE, "grupo-1"),
        ]
    )
    await db_session.commit()

    assert await _visibles(repository, diego) == {
        (T.BIRDIE, "grupo-2"): True,
        (T.EAGLE_OR_BETTER, "grupo-1"): True,
    }
    assert await _visibles(repository, eva) == {(T.BIRDIE, "grupo-1"): True}


async def test_a_notice_is_not_remembered(db_session):
    """Solo los logros: apuntarse otra vez es un aviso nuevo, con el interruptor de ahora."""
    diego = await _user(db_session)
    repository = SQLAlchemyActivityEventRepository(db_session)
    await repository.add_many([_logro(diego, T.ENROLLED_IN_TOURNAMENT, "torneo-1", visible=False)])
    await repository.delete_from_source("torneo-1", [T.ENROLLED_IN_TOURNAMENT])
    await db_session.commit()

    await repository.add_many([_logro(diego, T.ENROLLED_IN_TOURNAMENT, "torneo-1")])
    await db_session.commit()

    assert await _visibles(repository, diego) == {(T.ENROLLED_IN_TOURNAMENT, "torneo-1"): True}
    assert await _apuntes(db_session) == 0


async def test_the_note_is_kept_and_retiring_again_keeps_it_hidden(db_session):
    """
    El apunte no se gasta (23 oct 2026): lo que estuvo oculto se queda oculto
    aunque se vuelva a publicar muchas veces.
    """
    diego = await _user(db_session)
    repository = SQLAlchemyActivityEventRepository(db_session)
    await repository.add_many([_logro(diego, T.BIRDIE, "grupo-1", visible=False)])
    await repository.delete_for_competition("torneo-1", [T.BIRDIE])
    await db_session.commit()
    assert await _apuntes(db_session) == 1

    await repository.add_many([_logro(diego, T.BIRDIE, "grupo-1")])
    await db_session.commit()
    assert await _apuntes(db_session) == 1

    await repository.delete_for_competition("torneo-1", [T.BIRDIE])
    await repository.add_many([_logro(diego, T.BIRDIE, "grupo-1")])
    await db_session.commit()
    assert await _visibles(repository, diego) == {(T.BIRDIE, "grupo-1"): False}


async def test_deleting_the_account_deletes_its_notes(db_session):
    diego = await _user(db_session)
    repository = SQLAlchemyActivityEventRepository(db_session)
    await repository.add_many([_logro(diego, T.BIRDIE, "grupo-1", visible=False)])
    await repository.delete_for_competition("torneo-1", [T.BIRDIE])
    await db_session.commit()
    assert await _apuntes(db_session) == 1

    await db_session.execute(text("DELETE FROM users WHERE id = :id"), {"id": str(diego.id.value)})
    await db_session.commit()

    assert await _apuntes(db_session) == 0
