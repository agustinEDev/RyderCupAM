"""
El repositorio en memoria hace lo mismo que Postgres con lo que se retiro
oculto (`test_activity_event_hidden_kept.py` en integracion): los tests de los
casos de uso se apoyan en el.
"""

from datetime import datetime, timedelta

import pytest

from src.modules.social.domain.entities.activity_event import ActivityEvent
from src.modules.social.domain.repositories.activity_event_repository_interface import (
    ActivitySlice,
)
from src.modules.social.domain.value_objects.activity_event_type import ActivityEventType
from src.modules.social.infrastructure.persistence.in_memory.in_memory_activity_event_repository import (
    InMemoryActivityEventRepository,
)
from src.modules.user.domain.value_objects.user_id import UserId

pytestmark = pytest.mark.asyncio

T = ActivityEventType
CUANDO = datetime(2026, 10, 23, 12, 0)
DIEGO = UserId.generate()
EVA = UserId.generate()


def _logro(
    tipo: ActivityEventType,
    origen: str,
    *,
    user: UserId = DIEGO,
    visible: bool = True,
    **extra,
) -> ActivityEvent:
    return ActivityEvent.create(
        user_id=user,
        type=tipo,
        occurred_at=CUANDO,
        source_match_id=origen,
        published_at=CUANDO + timedelta(minutes=1),
        payload={"competition_id": "torneo-1", **extra},
        visible_to_friends=visible,
    )


async def _visibles(repo, user: UserId = DIEGO) -> dict[tuple, bool]:
    eventos = await repo.find_in(
        [ActivitySlice(user_ids=(user,), types=frozenset(ActivityEventType))], 50
    )
    return {(e.type, e.source_match_id): e.visible_to_friends for e in eventos}


@pytest.fixture
def repo():
    return InMemoryActivityEventRepository()


@pytest.mark.parametrize(
    "retirar",
    [
        lambda r: r.delete_for_competition("torneo-1", [T.BIRDIE]),
        lambda r: r.delete_pairs(T.BIRDIE, [(DIEGO, "grupo-1")]),
        lambda r: r.delete_from_source("grupo-1", [T.BIRDIE]),
        lambda r: r.delete_from_source_for_users("grupo-1", [T.BIRDIE], [DIEGO]),
    ],
    ids=["competition", "pairs", "source", "source_for_users"],
)
async def test_retired_hidden_comes_back_hidden(repo, retirar):
    await repo.add_many([_logro(T.BIRDIE, "grupo-1", visible=False)])
    await retirar(repo)

    await repo.add_many([_logro(T.BIRDIE, "grupo-1")])

    assert await _visibles(repo) == {(T.BIRDIE, "grupo-1"): False}


async def test_a_retired_visible_one_comes_back_visible(repo):
    await repo.add_many([_logro(T.BIRDIE, "grupo-1")])
    await repo.delete_for_competition("torneo-1", [T.BIRDIE])

    await repo.add_many([_logro(T.BIRDIE, "grupo-1")])

    assert await _visibles(repo) == {(T.BIRDIE, "grupo-1"): True}


async def test_only_the_same_identity_is_kept_hidden(repo):
    await repo.add_many([_logro(T.BIRDIE, "grupo-1", visible=False)])
    await repo.delete_for_competition("torneo-1", [T.BIRDIE])

    await repo.add_many(
        [
            _logro(T.BIRDIE, "grupo-2"),
            _logro(T.EAGLE_OR_BETTER, "grupo-1"),
            _logro(T.BIRDIE, "grupo-1", user=EVA),
        ]
    )

    assert await _visibles(repo) == {
        (T.BIRDIE, "grupo-2"): True,
        (T.EAGLE_OR_BETTER, "grupo-1"): True,
    }
    assert await _visibles(repo, EVA) == {(T.BIRDIE, "grupo-1"): True}


async def test_a_notice_is_not_remembered(repo):
    await repo.add_many([_logro(T.ENROLLED_IN_TOURNAMENT, "torneo-1", visible=False)])
    await repo.delete_from_source("torneo-1", [T.ENROLLED_IN_TOURNAMENT])

    await repo.add_many([_logro(T.ENROLLED_IN_TOURNAMENT, "torneo-1")])

    assert await _visibles(repo) == {(T.ENROLLED_IN_TOURNAMENT, "torneo-1"): True}


async def test_the_note_is_used_once_and_retiring_again_writes_it_again(repo):
    await repo.add_many([_logro(T.BIRDIE, "grupo-1", visible=False)])
    await repo.delete_for_competition("torneo-1", [T.BIRDIE])
    await repo.add_many([_logro(T.BIRDIE, "grupo-1")])
    # Ya gastado: lo oculto lo guarda el propio logro
    await repo.delete_for_user(DIEGO)
    await repo.add_many([_logro(T.BIRDIE, "grupo-1")])
    assert await _visibles(repo) == {(T.BIRDIE, "grupo-1"): True}

    await repo.delete_for_competition("torneo-1", [T.BIRDIE])
    await repo.add_many([_logro(T.BIRDIE, "grupo-1", visible=False)])
    await repo.delete_for_competition("torneo-1", [T.BIRDIE])
    await repo.add_many([_logro(T.BIRDIE, "grupo-1")])
    assert await _visibles(repo) == {(T.BIRDIE, "grupo-1"): False}


async def test_replacing_over_a_hidden_one_keeps_it_hidden_and_untouched(repo):
    oculto = _logro(T.BIRDIE, "grupo-1", visible=False)
    await repo.add_many([oculto])

    await repo.replace_for_competition("torneo-1", [T.BIRDIE], [_logro(T.BIRDIE, "grupo-1")])

    eventos = await repo.find_in(
        [ActivitySlice(user_ids=(DIEGO,), types=frozenset(ActivityEventType))], 50
    )
    assert [(e.id, e.visible_to_friends) for e in eventos] == [(oculto.id, False)]


async def test_replacing_a_hidden_one_whose_payload_changed_keeps_it_hidden(repo):
    await repo.add_many([_logro(T.BIRDIE, "grupo-1", visible=False, holes=[4])])

    await repo.replace_for_competition(
        "torneo-1", [T.BIRDIE], [_logro(T.BIRDIE, "grupo-1", holes=[4, 7])]
    )

    assert await _visibles(repo) == {(T.BIRDIE, "grupo-1"): False}


async def test_replacing_a_visible_one_with_a_hidden_one_hides_it(repo):
    await repo.add_many([_logro(T.BIRDIE, "grupo-1")])

    await repo.replace_for_competition(
        "torneo-1", [T.BIRDIE], [_logro(T.BIRDIE, "grupo-1", visible=False)]
    )

    assert await _visibles(repo) == {(T.BIRDIE, "grupo-1"): False}
