"""
Las rondas de una competición y un usuario, una vez por petición (27 oct 2026, PR 2).

La ficha pedía las rondas dos veces (para «tus jornadas» y para saber si se
puede borrar), el reparto de equipos hasta tres y, a quien organiza, su
usuario dos veces (la sesión y el creador). La segunda lectura en la misma sesión ya no pregunta; si las rondas
cambian con el propio repositorio (añadir, borrar), se vuelven a leer.
"""

import gc
from datetime import date

import pytest
from sqlalchemy import event

from src.modules.competition.domain.entities.round import Round
from src.modules.competition.domain.entities.team_assignment import TeamAssignment
from src.modules.competition.domain.value_objects.session_type import SessionType
from src.modules.competition.domain.value_objects.team_assignment_mode import (
    TeamAssignmentMode,
)
from src.modules.competition.infrastructure.persistence.sqlalchemy.competition_unit_of_work import (
    SQLAlchemyCompetitionUnitOfWork,
)
from src.modules.user.infrastructure.persistence.sqlalchemy.user_repository import (
    SQLAlchemyUserRepository,
)
from src.shared.domain.value_objects.match_format import MatchFormat
from tests.integration.modules.competition.infrastructure.persistence.sqlalchemy.test_envelope_repository import (  # noqa: F401
    jugadores,
    ronda,
)

pytestmark = [pytest.mark.integration]


class _Cuenta:
    def __init__(self, db_session):
        self._engine = db_session.bind.sync_engine
        self.selects = 0

    def _apunta(self, conn, cursor, statement, *args):
        if statement.lstrip().upper().startswith("SELECT"):
            self.selects += 1

    def __enter__(self):
        event.listen(self._engine, "before_cursor_execute", self._apunta)
        return self

    def __exit__(self, *exc):
        event.remove(self._engine, "before_cursor_execute", self._apunta)


async def test_las_rondas_de_la_competicion_una_vez(db_session, ronda):  # noqa: F811
    uow = SQLAlchemyCompetitionUnitOfWork(db_session)
    primera = await uow.rounds.find_by_competition(ronda.competition_id)
    gc.collect()

    with _Cuenta(db_session) as cuenta:
        segunda = await SQLAlchemyCompetitionUnitOfWork(db_session).rounds.find_by_competition(
            ronda.competition_id
        )

    assert cuenta.selects == 0
    assert [r.id for r in segunda] == [r.id for r in primera]


async def test_al_anadir_una_ronda_se_vuelven_a_leer(db_session, ronda):  # noqa: F811
    uow = SQLAlchemyCompetitionUnitOfWork(db_session)
    await uow.rounds.find_by_competition(ronda.competition_id)
    otra = Round.create(
        competition_id=ronda.competition_id,
        golf_course_id=ronda.golf_course_id,
        round_date=date(2026, 6, 2),
        session_type=SessionType.AFTERNOON,
        match_format=MatchFormat.SINGLES,
    )
    await uow.rounds.add(otra)
    await db_session.flush()

    rondas = await uow.rounds.find_by_competition(ronda.competition_id)

    assert otra.id in {r.id for r in rondas}


async def test_al_borrar_una_ronda_se_vuelven_a_leer(db_session, ronda):  # noqa: F811
    uow = SQLAlchemyCompetitionUnitOfWork(db_session)
    await uow.rounds.find_by_competition(ronda.competition_id)
    await uow.rounds.delete(ronda.id)
    await db_session.flush()

    assert await uow.rounds.find_by_competition(ronda.competition_id) == []


async def test_lo_que_se_devuelve_no_es_la_lista_guardada(db_session, ronda):  # noqa: F811
    """Quien llama puede tocar su lista sin cambiar la de la siguiente lectura."""
    uow = SQLAlchemyCompetitionUnitOfWork(db_session)
    (await uow.rounds.find_by_competition(ronda.competition_id)).clear()

    assert [r.id for r in await uow.rounds.find_by_competition(ronda.competition_id)] == [ronda.id]


async def test_el_usuario_una_vez_aunque_nadie_lo_retenga(db_session, jugadores):  # noqa: F811
    repo = SQLAlchemyUserRepository(db_session)
    db_session.expunge_all()
    await repo.find_by_id(jugadores[0])
    gc.collect()

    with _Cuenta(db_session) as cuenta:
        usuario = await SQLAlchemyUserRepository(db_session).find_by_id(jugadores[0])

    assert cuenta.selects == 0
    assert usuario.id == jugadores[0]


async def test_el_reparto_una_vez_tambien_si_no_lo_hay(db_session, ronda):  # noqa: F811
    """Hasta formar equipos no hay reparto: también eso se recuerda."""
    uow = SQLAlchemyCompetitionUnitOfWork(db_session)
    assert await uow.team_assignments.find_by_competition(ronda.competition_id) is None

    with _Cuenta(db_session) as cuenta:
        otra = await SQLAlchemyCompetitionUnitOfWork(
            db_session
        ).team_assignments.find_by_competition(ronda.competition_id)

    assert otra is None
    assert cuenta.selects == 0


async def test_al_repartir_y_al_deshacerlo_se_vuelve_a_leer(db_session, ronda, jugadores):  # noqa: F811
    uow = SQLAlchemyCompetitionUnitOfWork(db_session)
    await uow.team_assignments.find_by_competition(ronda.competition_id)
    reparto = TeamAssignment.create(
        competition_id=ronda.competition_id,
        mode=TeamAssignmentMode.MANUAL,
        team_a_player_ids=[jugadores[0]],
        team_b_player_ids=[jugadores[1]],
    )
    await uow.team_assignments.add(reparto)
    await db_session.flush()

    leido = await uow.team_assignments.find_by_competition(ronda.competition_id)
    assert leido is not None
    gc.collect()
    with _Cuenta(db_session) as cuenta:
        await uow.team_assignments.find_by_competition(ronda.competition_id)
    assert cuenta.selects == 0

    await uow.team_assignments.delete(reparto.id)
    await db_session.flush()

    assert await uow.team_assignments.find_by_competition(ronda.competition_id) is None
