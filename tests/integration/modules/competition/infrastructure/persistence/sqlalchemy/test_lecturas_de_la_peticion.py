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
    # La segunda sale de lo recordado: tocarla tampoco cambia la siguiente
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


# --- Tras deshacer, nada recordado (revisor de la PR 2) ---------------------------


async def test_el_usuario_tras_un_rollback_se_vuelve_a_leer(db_session, jugadores):  # noqa: F811
    """Recordado y caducado: tocarlo era un MissingGreenlet (un 500)."""
    repo = SQLAlchemyUserRepository(db_session)
    await repo.find_by_id(jugadores[0])
    await db_session.rollback()

    usuario = await repo.find_by_id(jugadores[0])

    assert usuario.email is not None


async def test_un_savepoint_deshecho_olvida_lo_recordado(db_session, ronda, jugadores):  # noqa: F811
    """Como la generación de partidos que falla: se deshace solo el SAVEPOINT."""
    uow = SQLAlchemyCompetitionUnitOfWork(db_session)
    usuario = await SQLAlchemyUserRepository(db_session).find_by_id(jugadores[0])
    await uow.rounds.find_by_competition(ronda.competition_id)
    await uow.team_assignments.find_by_competition(ronda.competition_id)
    try:
        async with db_session.begin_nested():
            # Como el refresco de la RFEG al generar: se toca al usuario dentro
            usuario.set_activity_sharing(not usuario.share_activity)
            otra = Round.create(
                competition_id=ronda.competition_id,
                golf_course_id=ronda.golf_course_id,
                round_date=date(2026, 6, 3),
                session_type=SessionType.EVENING,
                match_format=MatchFormat.SINGLES,
            )
            db_session.add(otra)
            await db_session.flush()
            raise RuntimeError("falla la generación")
    except RuntimeError:
        pass

    rondas = await uow.rounds.find_by_competition(ronda.competition_id)
    usuario = await SQLAlchemyUserRepository(db_session).find_by_id(jugadores[0])

    assert [r.id for r in rondas] == [ronda.id]
    assert usuario.email is not None


async def test_cambiar_la_fecha_sin_actualizar_reordena(db_session, ronda):  # noqa: F811
    """La lista recordada sale en el orden de sus fechas de ahora (revisor)."""
    uow = SQLAlchemyCompetitionUnitOfWork(db_session)
    tarde = Round.create(
        competition_id=ronda.competition_id,
        golf_course_id=ronda.golf_course_id,
        round_date=date(2030, 1, 1),
        session_type=SessionType.AFTERNOON,
        match_format=MatchFormat.SINGLES,
    )
    await uow.rounds.add(tarde)
    await db_session.flush()
    assert [r.id for r in await uow.rounds.find_by_competition(ronda.competition_id)] == [
        ronda.id,
        tarde.id,
    ]

    tarde._round_date = date(2000, 1, 1)

    assert [r.id for r in await uow.rounds.find_by_competition(ronda.competition_id)] == [
        tarde.id,
        ronda.id,
    ]


async def test_una_ronda_caducada_hace_leer_la_lista_otra_vez(db_session, ronda):  # noqa: F811
    uow = SQLAlchemyCompetitionUnitOfWork(db_session)
    id_de_la_ronda, competicion = ronda.id, ronda.competition_id
    (leida,) = await uow.rounds.find_by_competition(competicion)
    db_session.expire(leida)

    with _Cuenta(db_session) as cuenta:
        (otra_vez,) = await uow.rounds.find_by_competition(competicion)

    assert cuenta.selects > 0
    # Releída: su fecha se lee sin carga perezosa
    assert otra_vez.id == id_de_la_ronda
    assert otra_vez.round_date is not None


async def test_una_ronda_leida_dentro_de_un_savepoint_deshecho_no_sale(db_session, ronda):  # noqa: F811
    """Insertada, leída en la lista y deshecha: queda transitoria, no caducada."""
    uow = SQLAlchemyCompetitionUnitOfWork(db_session)
    competicion, id_de_la_ronda = ronda.competition_id, ronda.id
    try:
        async with db_session.begin_nested():
            db_session.add(
                Round.create(
                    competition_id=competicion,
                    golf_course_id=ronda.golf_course_id,
                    round_date=date(2026, 6, 4),
                    session_type=SessionType.EVENING,
                    match_format=MatchFormat.SINGLES,
                )
            )
            await db_session.flush()
            assert len(await uow.rounds.find_by_competition(competicion)) == 2
            raise RuntimeError("se deshace")
    except RuntimeError:
        pass

    assert [r.id for r in await uow.rounds.find_by_competition(competicion)] == [id_de_la_ronda]


async def test_el_usuario_sacado_de_la_sesion_se_vuelve_a_leer(db_session, jugadores):  # noqa: F811
    repo = SQLAlchemyUserRepository(db_session)
    fuera = await repo.find_by_id(jugadores[0])
    db_session.expunge(fuera)

    with _Cuenta(db_session) as cuenta:
        usuario = await repo.find_by_id(jugadores[0])

    assert cuenta.selects > 0
    assert usuario is not fuera


async def test_una_competicion_creada_en_un_savepoint_deshecho_ya_no_existe(
    db_session,
    jugadores,  # noqa: F811
):
    """Como la ronda: insertada, leída dentro y deshecha, no se devuelve."""
    from datetime import timedelta
    from uuid import uuid4

    from src.modules.competition.domain.entities.competition import Competition
    from src.modules.competition.domain.value_objects.competition_id import CompetitionId
    from src.modules.competition.domain.value_objects.competition_name import CompetitionName
    from src.modules.competition.domain.value_objects.date_range import DateRange
    from src.modules.competition.domain.value_objects.location import Location
    from src.shared.domain.value_objects.country_code import CountryCode
    from src.shared.domain.value_objects.play_mode import PlayMode

    uow = SQLAlchemyCompetitionUnitOfWork(db_session)
    otra_id = CompetitionId(uuid4())
    try:
        async with db_session.begin_nested():
            await uow.competitions.add(
                Competition.create(
                    id=otra_id,
                    creator_id=jugadores[0],
                    name=CompetitionName(f"Deshecha {uuid4().hex[:6]}"),
                    dates=DateRange(date(2026, 7, 1), date(2026, 7, 1) + timedelta(days=1)),
                    location=Location(main_country=CountryCode("ES")),
                    play_mode=PlayMode.SCRATCH,
                    team_1_name="A",
                    team_2_name="B",
                )
            )
            await db_session.flush()
            assert await uow.competitions.find_by_id(otra_id) is not None
            raise RuntimeError("se deshace")
    except RuntimeError:
        pass

    assert await uow.competitions.find_by_id(otra_id) is None


async def test_borrar_la_competicion_olvida_sus_rondas(db_session, ronda):  # noqa: F811
    """/code-review: sus rondas caen en cascada en la base de datos, sin pasar por su repositorio."""
    uow = SQLAlchemyCompetitionUnitOfWork(db_session)
    competicion = ronda.competition_id
    assert len(await uow.rounds.find_by_competition(competicion)) == 1

    await uow.competitions.delete(competicion)
    await db_session.flush()

    assert await uow.rounds.find_by_competition(competicion) == []
