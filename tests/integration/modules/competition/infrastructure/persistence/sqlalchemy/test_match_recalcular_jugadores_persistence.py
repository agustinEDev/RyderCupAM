"""
Recalcular los golpes de un partido queda guardado, y el partido es el mismo (BE #502).
"""

import pytest

from src.modules.competition.domain.value_objects.match_player import MatchPlayer
from src.modules.competition.infrastructure.persistence.sqlalchemy.match_repository import (
    SQLAlchemyMatchRepository,
)
from src.modules.golf_course.domain.value_objects.tee_color import TeeColor
from src.shared.domain.value_objects.gender import Gender
from tests.integration.modules.competition.infrastructure.persistence.sqlalchemy.test_match_repository_for_update import (  # noqa: F401
    creator_id,
    golf_course_id,
    match,
)

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def test_los_golpes_nuevos_quedan_guardados_en_el_mismo_partido(
    db_session,
    match,  # noqa: F811
    creator_id,  # noqa: F811
):
    repo = SQLAlchemyMatchRepository(db_session)

    def jugador(golpes):
        return MatchPlayer.create(
            user_id=creator_id,
            playing_handicap=golpes,
            tee_color=TeeColor.YELLOW,
            strokes_received=list(range(1, golpes + 1)),
            tee_gender=Gender.MALE,
        )

    partido = await repo.find_by_id_for_update(match.id)
    partido.recalcular_jugadores([jugador(7)], [jugador(3)])
    await repo.update(partido)
    await db_session.commit()
    db_session.expunge_all()

    leido = await repo.find_by_id(match.id)

    assert leido.id == match.id
    assert leido.team_a_players[0].playing_handicap == 7
    assert leido.handicap_strokes_given == 4
    assert leido.strokes_given_to_team == "A"
