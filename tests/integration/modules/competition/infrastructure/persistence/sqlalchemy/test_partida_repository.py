"""
Las partidas de stroke play se guardan y se leen igual en Postgres (#251, PR 4).

| Caso                                                         | Resultado                        |
|--------------------------------------------------------------|----------------------------------|
| Partida de 4 con plus, scratch, barras sin género y          | Vuelve idéntica                  |
| marcadores cambiados                                         |                                  |
| Reemplazar una franja                                        | Solo las nuevas; la otra intacta |
| Intercambiar jugadores entre dos partidas                    | Se guarda                        |
| Intercambiar sus números                                     | Se guarda                        |
| Borrar                                                       | Desaparece                       |
| De la franja / de la competición / del jugador               | Lo suyo, por número              |
| existe_con_jugador                                           | Sí / no                          |
| El mismo jugador en dos partidas de la franja                | La base de datos lo rechaza      |
| Borrar a un usuario que juega una partida                    | La base de datos lo rechaza      |
"""

from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.entities.partida import Partida
from src.modules.competition.domain.entities.round import Round
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.competition_name import CompetitionName
from src.modules.competition.domain.value_objects.date_range import DateRange
from src.modules.competition.domain.value_objects.estado_partida import EstadoPartida
from src.modules.competition.domain.value_objects.jugador_de_partida import (
    JugadorDePartida,
)
from src.modules.competition.domain.value_objects.location import Location
from src.modules.competition.domain.value_objects.session_type import SessionType
from src.modules.competition.infrastructure.persistence.sqlalchemy.competition_repository import (
    SQLAlchemyCompetitionRepository,
)
from src.modules.competition.infrastructure.persistence.sqlalchemy.competition_unit_of_work import (
    SQLAlchemyCompetitionUnitOfWork,
)
from src.modules.competition.infrastructure.persistence.sqlalchemy.round_repository import (
    SQLAlchemyRoundRepository,
)
from src.modules.golf_course.domain.value_objects.tee_color import TeeColor
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.country_code import CountryCode
from src.shared.domain.value_objects.gender import Gender
from src.shared.domain.value_objects.match_format import MatchFormat
from src.shared.domain.value_objects.play_mode import PlayMode
from tests.integration.modules.competition.infrastructure.persistence.sqlalchemy.test_envelope_repository import (  # noqa: F401
    BASE_DATE,
    _insert_user,
    jugadores,
    ronda,
)

pytestmark = [pytest.mark.integration]


def _golpes(playing_handicap: int) -> tuple[int, ...]:
    base, resto = divmod(abs(playing_handicap), 18)
    signo = 1 if playing_handicap >= 0 else -1
    return tuple(signo * (base + (1 if hoyo < resto else 0)) for hoyo in range(18))


def _jugador(
    user_id: UserId,
    playing_handicap: int = 10,
    tee_gender: Gender | None = Gender.MALE,
    tee_color: TeeColor = TeeColor.YELLOW,
) -> JugadorDePartida:
    return JugadorDePartida(
        user_id=user_id,
        handicap=Decimal("11.4"),
        playing_handicap=playing_handicap,
        tee_color=tee_color,
        tee_gender=tee_gender,
        golpes_por_hoyo=_golpes(playing_handicap),
    )


def _partida(franja: Round, numero: int, user_ids: list[UserId]) -> Partida:
    return Partida.crear(franja.competition_id, franja.id, numero, [_jugador(u) for u in user_ids])


@pytest_asyncio.fixture
async def otra_franja(db_session, ronda) -> Round:  # noqa: F811
    """La tarde del mismo día, en el mismo campo."""
    entidad = Round.create(
        competition_id=ronda.competition_id,
        golf_course_id=ronda.golf_course_id,
        round_date=BASE_DATE,
        session_type=SessionType.AFTERNOON,
        match_format=MatchFormat.FOURBALL,
    )
    await SQLAlchemyRoundRepository(db_session).add(entidad)
    await db_session.commit()
    return entidad


async def _releer(db_session) -> SQLAlchemyCompetitionUnitOfWork:
    await db_session.commit()
    db_session.expunge_all()
    return SQLAlchemyCompetitionUnitOfWork(db_session)


async def test_a_partida_comes_back_whole(db_session, ronda, jugadores):  # noqa: F811
    a, b, c, d = jugadores
    partida = Partida.crear(
        ronda.competition_id,
        ronda.id,
        3,
        [
            _jugador(a, 18),
            _jugador(b, -2, tee_color=TeeColor.WHITE),
            _jugador(c, 0, tee_gender=None),
            _jugador(d, 36, tee_gender=Gender.FEMALE, tee_color=TeeColor.RED),
        ],
    )
    partida.cambiar_marcadores({a: b, b: a, c: d, d: c})
    uow = SQLAlchemyCompetitionUnitOfWork(db_session)
    await uow.partidas.reemplazar_franja(ronda.id, [partida])

    leida = await (await _releer(db_session)).partidas.find_by_id(partida.id)

    assert leida is not None
    assert leida.competition_id == partida.competition_id
    assert leida.round_id == partida.round_id
    assert leida.numero == 3
    assert leida.estado == EstadoPartida.SCHEDULED
    assert leida.jugadores == partida.jugadores
    assert leida.marcadores == {a: b, b: a, c: d, d: c}


async def test_replacing_a_window_keeps_only_the_new_ones_and_not_the_other_window(
    db_session,
    ronda,  # noqa: F811
    otra_franja,
    jugadores,  # noqa: F811
):
    a, b, c, d = jugadores
    uow = SQLAlchemyCompetitionUnitOfWork(db_session)
    await uow.partidas.reemplazar_franja(ronda.id, [_partida(ronda, 1, [a, b])])
    de_tarde = _partida(otra_franja, 1, [c, d])
    await uow.partidas.reemplazar_franja(otra_franja.id, [de_tarde])
    await db_session.commit()
    nueva = _partida(ronda, 1, [b, a])

    await uow.partidas.reemplazar_franja(ronda.id, [nueva])
    uow = await _releer(db_session)

    assert [p.id for p in await uow.partidas.de_la_franja(ronda.id)] == [nueva.id]
    assert [p.id for p in await uow.partidas.de_la_franja(otra_franja.id)] == [de_tarde.id]


async def test_swapping_players_between_two_groups_is_saved(db_session, ronda, jugadores):  # noqa: F811
    a, b, c, d = jugadores
    primera, segunda = _partida(ronda, 1, [a, b]), _partida(ronda, 2, [c, d])
    uow = SQLAlchemyCompetitionUnitOfWork(db_session)
    await uow.partidas.reemplazar_franja(ronda.id, [primera, segunda])
    await db_session.commit()

    primera.quitar(b)
    segunda.quitar(c)
    primera.meter(_jugador(c), jugadores_por_partida=4)
    segunda.meter(_jugador(b), jugadores_por_partida=4)
    await uow.partidas.guardar([primera, segunda])
    uow = await _releer(db_session)

    leidas = await uow.partidas.de_la_franja(ronda.id)
    assert [p.user_ids for p in leidas] == [[a, c], [d, b]]
    assert [p.marcadores for p in leidas] == [{a: c, c: a}, {d: b, b: d}]


async def test_swapping_their_numbers_is_saved(db_session, ronda, jugadores):  # noqa: F811
    a, b, c, d = jugadores
    primera, segunda = _partida(ronda, 1, [a, b]), _partida(ronda, 2, [c, d])
    uow = SQLAlchemyCompetitionUnitOfWork(db_session)
    await uow.partidas.reemplazar_franja(ronda.id, [primera, segunda])
    await db_session.commit()

    primera.renumerar(2)
    segunda.renumerar(1)
    await uow.partidas.guardar([primera, segunda])
    uow = await _releer(db_session)

    assert [p.id for p in await uow.partidas.de_la_franja(ronda.id)] == [segunda.id, primera.id]


async def test_deleting(db_session, ronda, jugadores):  # noqa: F811
    a, b, c, d = jugadores
    primera, segunda = _partida(ronda, 1, [a, b]), _partida(ronda, 2, [c, d])
    uow = SQLAlchemyCompetitionUnitOfWork(db_session)
    await uow.partidas.reemplazar_franja(ronda.id, [primera, segunda])
    await db_session.commit()

    await uow.partidas.borrar([primera])
    uow = await _releer(db_session)

    assert [p.id for p in await uow.partidas.de_la_franja(ronda.id)] == [segunda.id]
    assert await uow.partidas.find_by_id(primera.id) is None


async def _franja_de_otra_competicion(db_session, ronda, creador: UserId) -> Round:  # noqa: F811
    competition = Competition.create(
        id=CompetitionId(uuid4()),
        creator_id=creador,
        name=CompetitionName(f"Otra Cup {uuid4().hex[:6]}"),
        dates=DateRange(start_date=BASE_DATE, end_date=BASE_DATE + timedelta(days=5)),
        location=Location(main_country=CountryCode("ES")),
        play_mode=PlayMode.SCRATCH,
        team_1_name="Team A",
        team_2_name="Team B",
    )
    await SQLAlchemyCompetitionRepository(db_session).add(competition)
    entidad = Round.create(
        competition_id=competition.id,
        golf_course_id=ronda.golf_course_id,
        round_date=BASE_DATE,
        session_type=SessionType.MORNING,
        match_format=MatchFormat.FOURBALL,
    )
    await SQLAlchemyRoundRepository(db_session).add(entidad)
    await db_session.commit()
    return entidad


async def test_queries(db_session, ronda, otra_franja, jugadores):  # noqa: F811
    a, b, c, d = jugadores
    fuera = UserId.generate()
    await _insert_user(db_session, fuera)
    manana = [_partida(ronda, 2, [c, d]), _partida(ronda, 1, [a, b])]
    tarde = [_partida(otra_franja, 1, [a, c])]
    ajena = await _franja_de_otra_competicion(db_session, ronda, a)
    uow = SQLAlchemyCompetitionUnitOfWork(db_session)
    await uow.partidas.reemplazar_franja(ronda.id, manana)
    await uow.partidas.reemplazar_franja(otra_franja.id, tarde)
    await uow.partidas.reemplazar_franja(ajena.id, [_partida(ajena, 1, [a, b])])
    uow = await _releer(db_session)

    de_la_manana = await uow.partidas.de_la_franja(ronda.id)
    de_la_competicion = await uow.partidas.de_la_competicion(ronda.competition_id)
    de_a = await uow.partidas.del_jugador(ronda.competition_id, a)

    assert [p.numero for p in de_la_manana] == [1, 2]
    assert sorted((str(p.round_id), p.numero) for p in de_la_competicion) == sorted(
        [(str(ronda.id), 1), (str(ronda.id), 2), (str(otra_franja.id), 1)]
    )
    assert {p.id for p in de_a} == {manana[1].id, tarde[0].id}
    assert await uow.partidas.del_jugador(ronda.competition_id, fuera) == []
    assert await uow.partidas.existe_con_jugador(a)
    assert not await uow.partidas.existe_con_jugador(fuera)


async def test_the_same_player_twice_in_a_window_is_refused(db_session, ronda, jugadores):  # noqa: F811
    a, b, c, _ = jugadores
    uow = SQLAlchemyCompetitionUnitOfWork(db_session)
    await uow.partidas.reemplazar_franja(
        ronda.id, [_partida(ronda, 1, [a, b]), _partida(ronda, 2, [a, c])]
    )

    with pytest.raises(IntegrityError):
        await db_session.commit()


async def test_a_user_who_plays_a_group_cannot_be_deleted(db_session, ronda, jugadores):  # noqa: F811
    """RESTRICT: lo jugado no desaparece al borrar a alguien; el borrado lo mira antes."""
    a, b, _, _ = jugadores
    uow = SQLAlchemyCompetitionUnitOfWork(db_session)
    await uow.partidas.reemplazar_franja(ronda.id, [_partida(ronda, 1, [a, b])])
    await db_session.commit()

    with pytest.raises(IntegrityError):
        await db_session.execute(text("DELETE FROM users WHERE id = :id"), {"id": str(b.value)})
        await db_session.commit()


async def test_a_move_that_empties_a_group_and_opens_a_new_one_is_saved(
    db_session,
    ronda,  # noqa: F811
    jugadores,  # noqa: F811
):
    """Borrar la vacía, subir la de detrás y crear la nueva, en la misma transacción (M1, M3)."""
    from datetime import time

    from src.modules.competition.domain.services.movimientos_de_partidas import (
        MovimientosDePartidas,
    )
    from src.modules.competition.domain.value_objects.hoja_de_salidas import HojaDeSalidas

    a, b, c, _ = jugadores
    sola, segunda = _partida(ronda, 1, [a]), _partida(ronda, 2, [b, c])
    uow = SQLAlchemyCompetitionUnitOfWork(db_session)
    await uow.partidas.reemplazar_franja(ronda.id, [sola, segunda])
    await db_session.commit()

    cambios = MovimientosDePartidas.mover(
        [sola, segunda],
        sola.jugadores[0],
        None,
        None,
        HojaDeSalidas(time(9, 0), time(9, 30), 10, 4),
        ronda.competition_id,
        ronda.id,
    )
    await uow.partidas.borrar(cambios.borrar)
    await uow.partidas.guardar(cambios.guardar)
    await uow.partidas.anadir(cambios.crear)
    uow = await _releer(db_session)

    leidas = await uow.partidas.de_la_franja(ronda.id)
    assert [(p.numero, p.user_ids) for p in leidas] == [(1, [b, c]), (2, [a])]
