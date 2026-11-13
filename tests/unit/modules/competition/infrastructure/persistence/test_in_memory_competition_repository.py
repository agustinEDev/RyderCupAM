"""El doble en memoria del repositorio de competiciones cumple la interfaz."""

from datetime import date, datetime, timedelta
from uuid import uuid4

import pytest

from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.competition_name import CompetitionName
from src.modules.competition.domain.value_objects.competition_status import CompetitionStatus
from src.modules.competition.domain.value_objects.date_range import DateRange
from src.modules.competition.domain.value_objects.location import Location
from src.modules.competition.infrastructure.persistence.in_memory.in_memory_competition_repository import (
    InMemoryCompetitionRepository,
)
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.country_code import CountryCode
from src.shared.domain.value_objects.play_mode import PlayMode


def _competicion(nombre: str) -> Competition:
    hoy = date.today() + timedelta(days=30)
    return Competition.create(
        id=CompetitionId(uuid4()),
        creator_id=UserId.generate(),
        name=CompetitionName(nombre),
        dates=DateRange(start_date=hoy, end_date=hoy + timedelta(days=2)),
        location=Location(main_country=CountryCode("ES")),
        play_mode=PlayMode.HANDICAP,
        team_1_name="Team A",
        team_2_name="Team B",
    )


async def test_find_by_status_with_limit_and_offset_returns_that_page():
    """
    Given: Three competitions in DRAFT
    When: Asking for DRAFT with limit 1 and offset 1, as the interface allows
    Then: One competition comes back (the double did not accept limit/offset)
    """
    repo = InMemoryCompetitionRepository()
    for nombre in ("Uno", "Dos", "Tres"):
        await repo.save(_competicion(nombre))

    pagina = await repo.find_by_status(CompetitionStatus.DRAFT, limit=1, offset=1)

    assert len(pagina) == 1


def _dos_de_un_creador_la_antigua_guardada_antes():
    """Two competitions of the same creator: the older one is saved first, as in real life."""
    antigua, nueva = _competicion("Antigua"), _competicion("Nueva")
    nueva._creator_id = antigua.creator_id
    antigua._created_at = datetime(2026, 1, 1, 10, 0)
    nueva._created_at = datetime(2026, 6, 1, 10, 0)
    return antigua, nueva


@pytest.mark.parametrize(
    "pide",
    [
        pytest.param(
            lambda repo, c: repo.find_by_status(CompetitionStatus.DRAFT, limit=1), id="status"
        ),
        pytest.param(lambda repo, c: repo.find_by_creator(c.creator_id, limit=1), id="creator"),
        pytest.param(lambda repo, c: repo.find_all(limit=1), id="all"),
    ],
)
async def test_the_first_page_holds_the_newest_competition_as_in_sql(pide):
    """
    Given: An older competition saved before a newer one
    When: Asking for the first page of one
    Then: The newer one comes back, as the SQL repository orders by created_at descending
    """
    repo = InMemoryCompetitionRepository()
    antigua, nueva = _dos_de_un_creador_la_antigua_guardada_antes()
    await repo.save(antigua)
    await repo.save(nueva)

    pagina = await pide(repo, antigua)

    assert [c.id for c in pagina] == [nueva.id]


async def test_delete_existing_competition_returns_true():
    """
    Given: A saved competition
    When: Deleting it
    Then: True, as the interface promises, and it is gone
    """
    repo = InMemoryCompetitionRepository()
    competicion = _competicion("Uno")
    await repo.save(competicion)

    borrada = await repo.delete(competicion.id)

    assert borrada is True
    assert await repo.find_by_id(competicion.id) is None


async def test_delete_missing_competition_returns_false():
    """
    Given: An empty repository
    When: Deleting a competition that does not exist
    Then: False, as the interface promises
    """
    repo = InMemoryCompetitionRepository()

    assert await repo.delete(CompetitionId(uuid4())) is False
