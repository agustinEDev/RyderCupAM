"""La papelera de partidas rapidas, leida del modulo de partidas rapidas (22 oct 2026)."""

from uuid import uuid4

import pytest

from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.quick_match.domain.entities.quick_match import QuickMatch
from src.modules.quick_match.domain.value_objects.participant_id import ParticipantId
from src.modules.quick_match.domain.value_objects.quick_match_id import QuickMatchId
from src.modules.quick_match.domain.value_objects.quick_match_participant import (
    QuickMatchParticipant,
)
from src.modules.quick_match.infrastructure.persistence.in_memory.in_memory_quick_match_unit_of_work import (
    InMemoryQuickMatchUnitOfWork,
)
from src.modules.social.infrastructure.adapters.quick_match_trash_adapter import (
    QuickMatchTrashAdapter,
)
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.scoring_format import ScoringFormat

pytestmark = pytest.mark.asyncio


async def _partida(qm_uow, ana: UserId, bea: UserId, *, ocultan=()) -> QuickMatch:
    match = QuickMatch.create(
        id=QuickMatchId.generate(),
        creator_id=ana,
        golf_course_id=GolfCourseId(uuid4()),
        scoring_format=ScoringFormat.STABLEFORD,
    )
    match.add_participant(QuickMatchParticipant.for_user(bea))
    for quien in ocultan:
        match.hide_for(ParticipantId(quien.value))
    async with qm_uow:
        await qm_uow.quick_matches.add(match)
    return match


@pytest.fixture
def qm_uow():
    return InMemoryQuickMatchUnitOfWork()


async def test_only_the_pairs_whose_author_has_it_in_the_trash(qm_uow):
    ana, bea = UserId(uuid4()), UserId(uuid4())
    oculta = await _partida(qm_uow, ana, bea, ocultan=[ana])
    visible = await _partida(qm_uow, ana, bea)
    crudo, otro = str(oculta.id.value), str(visible.id.value)

    resultado = await QuickMatchTrashAdapter(qm_uow).trashed_by_author(
        [(crudo, ana), (crudo, bea), (otro, ana)]
    )

    assert resultado == {(crudo, ana)}


async def test_unknown_or_unreadable_ids_do_not_count(qm_uow):
    ana = UserId(uuid4())

    resultado = await QuickMatchTrashAdapter(qm_uow).trashed_by_author(
        [(str(uuid4()), ana), ("no-es-un-id", ana)]
    )

    assert resultado == set()


async def test_someone_who_did_not_play_it_has_nothing_in_the_trash(qm_uow):
    ana, bea, otro = UserId(uuid4()), UserId(uuid4()), UserId(uuid4())
    partida = await _partida(qm_uow, ana, bea, ocultan=[ana])

    resultado = await QuickMatchTrashAdapter(qm_uow).trashed_by_author(
        [(str(partida.id.value), otro)]
    )

    assert resultado == set()


async def test_the_whole_page_is_read_at_once(qm_uow, monkeypatch):
    ana, bea = UserId(uuid4()), UserId(uuid4())
    partidas = [await _partida(qm_uow, ana, bea, ocultan=[ana]) for _ in range(3)]
    lecturas = []
    leer = qm_uow.quick_matches.find_by_ids

    async def _lee(ids):
        lecturas.append(ids)
        return await leer(ids)

    monkeypatch.setattr(qm_uow.quick_matches, "find_by_ids", _lee)

    resultado = await QuickMatchTrashAdapter(qm_uow).trashed_by_author(
        [(str(p.id.value), autor) for p in partidas for autor in (ana, bea)]
    )

    assert len(lecturas) == 1
    assert len(resultado) == 3


async def test_nothing_to_ask_reads_nothing(qm_uow, monkeypatch):
    async def _no_lee(ids):
        raise AssertionError("no deberia leer")

    monkeypatch.setattr(qm_uow.quick_matches, "find_by_ids", _no_lee)

    assert await QuickMatchTrashAdapter(qm_uow).trashed_by_author([]) == set()
