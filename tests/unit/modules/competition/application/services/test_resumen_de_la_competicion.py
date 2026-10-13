"""
Lo que el resumen de «Mis competiciones» necesita y la competición no sabe sola
(FE #846): cuántos días se juega y la próxima salida de quien mira.

| Caso                                                    | Resultado                         |
|---------------------------------------------------------|-----------------------------------|
| Stroke play, tres franjas en dos días                   | 2 jornadas                        |
| Stroke play sin franjas                                 | 0 jornadas                        |
| Ryder                                                   | Jornadas null                     |
| Con partida en una franja                               | Su fecha, franja y hora           |
| Con plaza y sin partidas generadas                      | Fecha y franja, sin hora          |
| Su tarjeta de la mañana cerrada (retirado, entregada…)  | La de la tarde                    |
| Sin ninguna por jugar                                   | null                              |
| La más cercana: día antes que franja                    | El sábado por la mañana va antes  |
| Ryder: su partido programado                            | Fecha y sesión, sin hora          |
| Ryder: su partido acabado                               | El siguiente, o null              |
| Quien no juega                                          | null, sin leer nada               |
| Competición terminada o cancelada (13 oct 2026)         | null; las jornadas sí             |
| Ryder: partido por walkover o concedido                 | No cuenta                         |
| Ryder: sesión aún sin partidos (13 oct 2026)            | Esa, sin hora                     |
| Ryder: sesión con partidos y ninguno suyo (descansa)    | No cuenta                         |
| Antes de ayer (13 oct 2026)                             | No cuenta; ayer y hoy, sí         |
"""

from datetime import time, timedelta
from uuid import uuid4

import pytest

from src.modules.competition.application.services.resumen_de_la_competicion import (
    ProximaSalida,
    ResumenDeLaCompeticion,
)
from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.entities.match import Match
from src.modules.competition.domain.entities.plaza_en_franja import PlazaEnFranja
from src.modules.competition.domain.entities.round import Round
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.competition_name import CompetitionName
from src.modules.competition.domain.value_objects.competition_status import CompetitionStatus
from src.modules.competition.domain.value_objects.date_range import DateRange
from src.modules.competition.domain.value_objects.hoja_de_salidas import HojaDeSalidas
from src.modules.competition.domain.value_objects.location import Location
from src.modules.competition.domain.value_objects.match_player import MatchPlayer
from src.modules.competition.domain.value_objects.round_status import RoundStatus
from src.modules.competition.domain.value_objects.session_type import SessionType
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.golf_course.domain.value_objects.tee_color import TeeColor
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.country_code import CountryCode
from src.shared.domain.value_objects.gender import Gender
from src.shared.domain.value_objects.match_format import MatchFormat
from src.shared.domain.value_objects.play_mode import PlayMode
from tests.unit.modules.competition.application.use_cases.test_anotar_hoyo_de_partida_use_case import (
    A_LAS_NUEVE_Y_CINCO,
)
from tests.unit.modules.competition.application.use_cases.test_generar_partidas_use_case import (
    VIERNES,
    _Escenario,
)

pytestmark = pytest.mark.asyncio

SABADO = VIERNES + timedelta(days=1)


async def _resumen(escenario, quien, juega=True, hoy=None):
    return await ResumenDeLaCompeticion.de(
        escenario.competicion, quien, juega, escenario.uow, hoy=hoy
    )


async def _franja_el_sabado(escenario, sesion=SessionType.MORNING, primera=time(8, 0)):
    franja = Round.create_franja(
        competition_id=escenario.competicion.id,
        golf_course_id=GolfCourseId.generate(),
        round_date=SABADO,
        session_type=sesion,
        hoja_de_salidas=HojaDeSalidas(primera, time(primera.hour + 1, 0), 10, 4),
    )
    async with escenario.uow:
        await escenario.uow.rounds.add(franja)
    return franja


async def _su_partida(escenario, franja, user_id):
    return next(
        p for p in await escenario.uow.partidas.de_la_franja(franja.id) if user_id in p.user_ids
    )


# --- Jornadas -------------------------------------------------------------------


async def test_three_windows_on_two_days_are_two_playing_days():
    escenario = _Escenario()
    await escenario.guardar()
    await _franja_el_sabado(escenario)

    assert (await _resumen(escenario, escenario.creador, juega=False)).jornadas == 2


async def test_a_stroke_play_without_windows_has_none_yet():
    escenario = _Escenario()
    async with escenario.uow:
        await escenario.uow.competitions.add(escenario.competicion)

    assert (await _resumen(escenario, escenario.creador, juega=False)).jornadas == 0


async def test_a_ryder_cup_has_no_playing_days():
    ryder = await _Ryder.crear()

    assert (await ryder.resumen(ryder.yo)).jornadas is None


# --- Próxima salida en stroke play --------------------------------------------------


async def test_with_a_group_its_date_window_and_tee_time():
    escenario = _Escenario()
    await escenario.guardar()
    otros = [await escenario.con_plaza(f"{h}.0") for h in range(1, 5)]
    yo = await escenario.con_plaza("9.0")
    await escenario.generar()  # altos primero: yo en la 1.ª (9:00), cuatro en la 2.ª (9:10)

    assert (await _resumen(escenario, yo)).proxima == ProximaSalida(
        VIERNES, SessionType.MORNING, time(9, 0)
    )
    assert (await _resumen(escenario, otros[0])).proxima.hora == time(9, 10)


async def test_with_a_place_and_no_groups_yet_no_tee_time():
    escenario = _Escenario()
    await escenario.guardar()
    yo = await escenario.con_plaza("9.0", franja=escenario.tarde)

    assert (await _resumen(escenario, yo)).proxima == ProximaSalida(
        VIERNES, SessionType.AFTERNOON, None
    )


@pytest.mark.parametrize("cierre", ["retirar", "entregar", "no_presentado"])
async def test_a_closed_card_in_the_morning_goes_on_to_the_afternoon(cierre):
    escenario = _Escenario()
    await escenario.guardar()
    yo = await escenario.con_plaza("9.0")
    await escenario.con_plaza("8.0")
    await escenario.con_plaza("7.0", franja=escenario.tarde)
    async with escenario.uow:
        await escenario.uow.plazas.add(
            PlazaEnFranja.crear(
                escenario.competicion.id, escenario.tarde.id, yo, A_LAS_NUEVE_Y_CINCO
            )
        )
    await escenario.generar()
    await escenario.generar(franja=escenario.tarde)
    manana = await _su_partida(escenario, escenario.manana, yo)
    if cierre == "retirar":
        manana.empezar()
        manana.retirar(yo)
    elif cierre == "entregar":
        # El organizador la cierra completa: queda entregada
        manana.cerrar(completas=[yo])
    else:
        manana.no_presentado(yo, [])
    await escenario.uow.partidas.guardar([manana])

    assert (await _resumen(escenario, yo)).proxima == ProximaSalida(
        VIERNES, SessionType.AFTERNOON, time(15, 0)
    )


async def test_nothing_left_to_play_is_null():
    escenario = _Escenario()
    await escenario.guardar()
    yo = await escenario.con_plaza("9.0")
    await escenario.con_plaza("8.0")
    await escenario.generar()
    manana = await _su_partida(escenario, escenario.manana, yo)
    manana.empezar()
    manana.retirar(yo)
    await escenario.uow.partidas.guardar([manana])

    assert (await _resumen(escenario, yo)).proxima is None


async def test_another_players_place_is_not_mine():
    escenario = _Escenario()
    await escenario.guardar()
    yo = await escenario.con_plaza("9.0")
    await escenario.con_plaza("8.0")
    await escenario.con_plaza("7.0", franja=escenario.tarde)
    await escenario.generar()
    manana = await _su_partida(escenario, escenario.manana, yo)
    manana.empezar()
    manana.retirar(yo)
    await escenario.uow.partidas.guardar([manana])

    assert (await _resumen(escenario, yo)).proxima is None


async def test_a_group_numbered_beyond_the_tee_sheet_has_no_time():
    escenario = _Escenario()
    await escenario.guardar()
    yo = await escenario.con_plaza("9.0")
    await escenario.con_plaza("8.0")
    await escenario.generar()
    partida = await _su_partida(escenario, escenario.manana, yo)
    # Con huecos en la numeración (se movió gente), su número no tiene salida
    partida.renumerar(99)
    await escenario.uow.partidas.guardar([partida])

    assert (await _resumen(escenario, yo)).proxima == ProximaSalida(
        VIERNES, SessionType.MORNING, None
    )


async def test_the_nearest_day_before_the_window_order():
    escenario = _Escenario()
    await escenario.guardar()
    sabado = await _franja_el_sabado(escenario)
    yo = await escenario.con_plaza("9.0", franja=sabado)
    async with escenario.uow:
        await escenario.uow.plazas.add(
            PlazaEnFranja.crear(
                escenario.competicion.id, escenario.tarde.id, yo, A_LAS_NUEVE_Y_CINCO
            )
        )

    # La tarde del viernes antes que la mañana del sábado
    assert (await _resumen(escenario, yo)).proxima == ProximaSalida(
        VIERNES, SessionType.AFTERNOON, None
    )


async def test_morning_before_afternoon_on_the_same_day():
    escenario = _Escenario()
    await escenario.guardar()
    yo = await escenario.con_plaza("9.0", franja=escenario.tarde)
    async with escenario.uow:
        await escenario.uow.plazas.add(
            PlazaEnFranja.crear(
                escenario.competicion.id, escenario.manana.id, yo, A_LAS_NUEVE_Y_CINCO
            )
        )

    assert (await _resumen(escenario, yo)).proxima.sesion == SessionType.MORNING


async def test_who_does_not_play_has_no_next_session():
    escenario = _Escenario()
    await escenario.guardar()
    yo = await escenario.con_plaza("9.0")

    assert (await _resumen(escenario, yo, juega=False)).proxima is None


# --- Próxima salida en la Ryder ---------------------------------------------------------


def _jugador(user_id: UserId) -> MatchPlayer:
    return MatchPlayer.create(
        user_id=user_id,
        playing_handicap=0,
        tee_color=TeeColor.YELLOW,
        strokes_received=[],
        tee_gender=Gender.MALE,
    )


class _Ryder:
    """Una Ryder con dos sesiones: viernes tarde y sábado mañana."""

    def __init__(self):
        self.escenario = _Escenario()
        self.escenario.competicion = Competition.create(
            id=CompetitionId.generate(),
            creator_id=self.escenario.creador,
            name=CompetitionName("Ryder de octubre"),
            dates=DateRange(VIERNES, SABADO),
            location=Location(CountryCode("ES")),
            play_mode=PlayMode.HANDICAP,
            team_1_name="Europa",
            team_2_name="América",
        )
        self.yo = UserId(uuid4())

    @classmethod
    async def crear(cls):
        ryder = cls()
        uow = ryder.escenario.uow
        ryder.viernes = Round.create(
            competition_id=ryder.escenario.competicion.id,
            golf_course_id=GolfCourseId.generate(),
            round_date=VIERNES,
            session_type=SessionType.AFTERNOON,
            match_format=MatchFormat.SINGLES,
        )
        ryder.sabado = Round.create(
            competition_id=ryder.escenario.competicion.id,
            golf_course_id=GolfCourseId.generate(),
            round_date=SABADO,
            session_type=SessionType.MORNING,
            match_format=MatchFormat.SINGLES,
        )
        async with uow:
            await uow.competitions.add(ryder.escenario.competicion)
            await uow.rounds.add(ryder.viernes)
            await uow.rounds.add(ryder.sabado)
        return ryder

    async def partido(self, ronda, con=True, numero=1):
        jugador = self.yo if con else UserId(uuid4())
        partido = Match.create(
            round_id=ronda.id,
            match_number=numero,
            team_a_players=[_jugador(jugador)],
            team_b_players=[_jugador(UserId(uuid4()))],
        )
        async with self.escenario.uow:
            await self.escenario.uow.matches.add(partido)
            # Con partidos, la sesión los tiene generados
            if ronda.status == RoundStatus.PENDING_TEAMS:
                ronda.mark_teams_assigned()
            if ronda.status == RoundStatus.PENDING_MATCHES:
                ronda.mark_matches_generated()
            await self.escenario.uow.rounds.update(ronda)
        return partido

    async def resumen(self, quien, hoy=None):
        return await _resumen(self.escenario, quien, hoy=hoy)


async def test_ryder_its_scheduled_match_date_and_session_without_time():
    ryder = await _Ryder.crear()
    await ryder.partido(ryder.viernes, con=False)
    await ryder.partido(ryder.sabado)

    assert (await ryder.resumen(ryder.yo)).proxima == ProximaSalida(
        SABADO, SessionType.MORNING, None
    )


async def test_ryder_a_finished_match_goes_on_to_the_next():
    ryder = await _Ryder.crear()
    viernes = await ryder.partido(ryder.viernes)
    viernes.start()
    viernes.complete({"winner": "A"})
    await ryder.escenario.uow.matches.update(viernes)
    await ryder.partido(ryder.sabado)

    assert (await ryder.resumen(ryder.yo)).proxima.fecha == SABADO


async def test_ryder_in_play_counts():
    ryder = await _Ryder.crear()
    viernes = await ryder.partido(ryder.viernes)
    viernes.start()
    await ryder.escenario.uow.matches.update(viernes)

    assert (await ryder.resumen(ryder.yo)).proxima.fecha == VIERNES


async def test_ryder_without_matches_left_is_null():
    ryder = await _Ryder.crear()
    await ryder.partido(ryder.sabado, con=False)
    viernes = await ryder.partido(ryder.viernes)
    viernes.start()
    viernes.complete({"winner": "A"})
    await ryder.escenario.uow.matches.update(viernes)

    assert (await ryder.resumen(ryder.yo)).proxima is None


# --- Competición terminada o cancelada (decidido el 13 oct 2026) -----------------------


@pytest.mark.parametrize("estado", [CompetitionStatus.COMPLETED, CompetitionStatus.CANCELLED])
async def test_a_finished_or_cancelled_stroke_play_has_no_next_session(estado):
    escenario = _Escenario(status=estado)
    await escenario.guardar()
    yo = await escenario.con_plaza("9.0")

    resumen = await _resumen(escenario, yo)

    assert (resumen.jornadas, resumen.proxima) == (1, None)


async def test_a_cancelled_ryder_has_no_next_session():
    ryder = await _Ryder.crear()
    await ryder.partido(ryder.viernes)
    ryder.escenario.competicion.cancel()

    assert (await ryder.resumen(ryder.yo)).proxima is None


@pytest.mark.parametrize("cierre", ["walkover", "concedido"])
async def test_ryder_a_walkover_or_conceded_match_does_not_count(cierre):
    ryder = await _Ryder.crear()
    await ryder.partido(ryder.sabado, con=False)
    partido = await ryder.partido(ryder.viernes)
    if cierre == "walkover":
        partido.declare_walkover("A")
    else:
        partido.start()
        partido.concede("B")
    await ryder.escenario.uow.matches.update(partido)

    assert (await ryder.resumen(ryder.yo)).proxima is None


# --- Sesiones sin partidos y días pasados (decidido el 13 oct 2026) ---------------------


async def test_ryder_a_session_without_matches_yet_counts_without_time():
    ryder = await _Ryder.crear()

    assert (await ryder.resumen(ryder.yo)).proxima == ProximaSalida(
        VIERNES, SessionType.AFTERNOON, None
    )


async def test_ryder_resting_in_a_session_with_matches_does_not_count():
    ryder = await _Ryder.crear()
    await ryder.partido(ryder.viernes, con=False)

    # El viernes descansa; el sábado aún no tiene partidos
    assert (await ryder.resumen(ryder.yo)).proxima.fecha == SABADO


@pytest.mark.parametrize(
    ("hoy", "esperado"),
    [
        (SABADO + timedelta(days=1), SABADO),  # el viernes fue antes de ayer
        (SABADO, VIERNES),  # el viernes fue ayer: margen sin zona horaria
        (VIERNES, VIERNES),
    ],
)
async def test_ryder_days_before_yesterday_do_not_count(hoy, esperado):
    ryder = await _Ryder.crear()
    await ryder.partido(ryder.viernes)
    await ryder.partido(ryder.sabado)

    assert (await ryder.resumen(ryder.yo, hoy=hoy)).proxima.fecha == esperado


async def test_stroke_play_a_card_left_open_before_yesterday_does_not_count():
    escenario = _Escenario()
    await escenario.guardar()
    sabado = await _franja_el_sabado(escenario)
    yo = await escenario.con_plaza("9.0")
    await escenario.con_plaza("8.0")
    async with escenario.uow:
        await escenario.uow.plazas.add(
            PlazaEnFranja.crear(escenario.competicion.id, sabado.id, yo, A_LAS_NUEVE_Y_CINCO)
        )
    await escenario.generar()

    # Su tarjeta del viernes sigue JUGANDO, pero fue antes de ayer
    resumen = await _resumen(escenario, yo, hoy=SABADO + timedelta(days=1))

    assert resumen.proxima == ProximaSalida(SABADO, SessionType.MORNING, None)
