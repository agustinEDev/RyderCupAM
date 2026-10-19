"""
Completar el género de la barra en los partidos de Ryder SCRATCH ya generados
(RyderCupWeb #880).

| Caso | Partidos                                   | Resultado                          |
|------|--------------------------------------------|------------------------------------|
| C1   | SCRATCH / HANDICAP                         | solo SCRATCH                       |
| C2   | jugador ya con género                      | no se toca (repetir no hace nada)  |
| C3   | barra de su género / del otro / sin género | su género / vacío / vacío          |
| C5   | ronda sin campo                            | nada                               |
| C6   | programada, en juego / terminada           | sí / no                            |
| C7   | --dry-run                                  | cuenta sin escribir                |
| C8   | una ronda falla                            | lo dice y sigue                    |
"""

from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.modules.competition.application.use_cases.completar_genero_de_las_barras_use_case import (
    CompletarGeneroDeLasBarrasUseCase,
)
from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.entities.match import Match
from src.modules.competition.domain.entities.round import Round
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.competition_name import CompetitionName
from src.modules.competition.domain.value_objects.date_range import DateRange
from src.modules.competition.domain.value_objects.location import Location
from src.modules.competition.domain.value_objects.match_player import MatchPlayer
from src.modules.competition.domain.value_objects.session_type import SessionType
from src.modules.competition.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.golf_course.domain.value_objects.tee_color import TeeColor
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.country_code import CountryCode
from src.shared.domain.value_objects.gender import Gender
from src.shared.domain.value_objects.match_format import MatchFormat
from src.shared.domain.value_objects.play_mode import PlayMode

pytestmark = pytest.mark.asyncio


def _barra(color, gender):
    tee = MagicMock()
    tee.color = color
    tee.gender = gender
    tee.course_rating = Decimal("71.2")
    tee.slope_rating = 128
    tee.holes = []
    return tee


def _campo(*barras):
    hoyos = []
    for numero in range(1, 19):
        hoyo = MagicMock()
        hoyo.number = numero
        hoyo.par = 4
        hoyo.stroke_index = numero
        hoyos.append(hoyo)
    campo = MagicMock()
    campo.tees = list(barras)
    campo.reference_card = hoyos
    return campo


AMARILLAS_DE_HOMBRE = _campo(
    _barra(TeeColor.YELLOW, Gender.MALE), _barra(TeeColor.RED, Gender.FEMALE)
)


class _Escenario:
    def __init__(self, campo=AMARILLAS_DE_HOMBRE):
        self.uow = InMemoryUnitOfWork()
        self.generos: dict = {}
        self.campos = MagicMock()
        self.campos.find_by_id = AsyncMock(return_value=campo)
        self.usuarios = MagicMock()
        self.usuarios.find_by_ids = AsyncMock(side_effect=self._usuarios)

    async def _usuarios(self, ids):
        return [MagicMock(id=uid, gender=self.generos.get(uid)) for uid in ids]

    def jugador(self, genero_del_perfil, color=TeeColor.YELLOW, tee_gender=None):
        uid = UserId.generate()
        self.generos[uid] = genero_del_perfil
        return MatchPlayer.create(
            user_id=uid,
            playing_handicap=0,
            tee_color=color,
            strokes_received=[],
            tee_gender=tee_gender,
            player_handicap=Decimal("0"),
        )

    async def ronda(
        self, play_mode=PlayMode.SCRATCH, estado="SCHEDULED", jugadores=None, partidos=None
    ):
        competition = Competition.create(
            id=CompetitionId(uuid4()),
            creator_id=UserId.generate(),
            name=CompetitionName(f"Ryder {uuid4().hex[:6]}"),
            dates=DateRange(start_date=date(2026, 6, 1), end_date=date(2026, 6, 3)),
            location=Location(main_country=CountryCode("ES")),
            play_mode=play_mode,
            team_1_name="A",
            team_2_name="B",
        )
        round_entity = Round.create(
            competition_id=competition.id,
            golf_course_id=GolfCourseId(uuid4()),
            round_date=date(2026, 6, 1),
            session_type=SessionType.MORNING,
            match_format=MatchFormat.SINGLES,
        )
        round_entity.mark_teams_assigned()
        round_entity.mark_matches_generated()
        if estado in ("IN_PROGRESS", "COMPLETED"):
            round_entity.start()
        if estado == "COMPLETED":
            round_entity.complete()
        a, b = jugadores or (self.jugador(Gender.MALE), self.jugador(Gender.MALE))
        lados = partidos or [([a], [b])]
        async with self.uow:
            await self.uow.competitions.add(competition)
            await self.uow.rounds.add(round_entity)
            for numero, (lado_a, lado_b) in enumerate(lados, start=1):
                await self.uow.matches.add(
                    Match.create(
                        round_id=round_entity.id,
                        match_number=numero,
                        team_a_players=lado_a,
                        team_b_players=lado_b,
                    )
                )
        return round_entity

    def caso_de_uso(self):
        return CompletarGeneroDeLasBarrasUseCase(self.uow, self.campos, self.usuarios)

    async def generos_de(self, round_entity):
        partidos = sorted(
            await self.uow.matches.find_by_round(round_entity.id), key=lambda m: m.match_number
        )
        return [p.tee_gender for m in partidos for p in (*m.team_a_players, *m.team_b_players)]


async def test_c1_c3_scratch_cada_uno_recibe_el_genero_de_su_barra():
    e = _Escenario()
    ronda = await e.ronda(
        jugadores=(e.jugador(Gender.MALE), e.jugador(Gender.FEMALE, color=TeeColor.RED))
    )

    guardar = AsyncMock(wraps=e.uow.matches.update)
    e.uow.matches.update = guardar

    resumen = await e.caso_de_uso().execute(dry_run=False)

    assert await e.generos_de(ronda) == [Gender.MALE, Gender.FEMALE]
    assert resumen.jugadores == 2
    assert resumen.errores == []
    guardar.assert_awaited_once()


async def test_c1_handicap_no_se_toca():
    e = _Escenario()
    ronda = await e.ronda(play_mode=PlayMode.HANDICAP)

    resumen = await e.caso_de_uso().execute(dry_run=False)

    assert await e.generos_de(ronda) == [None, None]
    assert resumen.jugadores == 0


async def test_c2_quien_ya_tiene_genero_no_cambia_y_repetir_no_hace_nada():
    e = _Escenario()
    ya = e.jugador(Gender.FEMALE, tee_gender=Gender.MALE)
    ronda = await e.ronda(jugadores=(ya, e.jugador(Gender.MALE)))

    primera = await e.caso_de_uso().execute(dry_run=False)
    segunda = await e.caso_de_uso().execute(dry_run=False)

    assert await e.generos_de(ronda) == [Gender.MALE, Gender.MALE]
    assert (primera.jugadores, segunda.jugadores) == (1, 0)


@pytest.mark.parametrize(
    ("genero_del_perfil", "color"),
    [
        pytest.param(Gender.FEMALE, TeeColor.YELLOW, id="la barra es del otro género"),
        pytest.param(None, TeeColor.YELLOW, id="sin género en el perfil"),
        pytest.param(Gender.MALE, TeeColor.BLUE, id="el campo no tiene ese color"),
    ],
)
async def test_c3_sin_barra_de_su_genero_se_queda_vacio(genero_del_perfil, color):
    e = _Escenario()
    ronda = await e.ronda(
        jugadores=(e.jugador(genero_del_perfil, color=color), e.jugador(Gender.MALE))
    )

    await e.caso_de_uso().execute(dry_run=False)

    assert (await e.generos_de(ronda))[0] is None


async def test_c4_el_color_no_cambia():
    e = _Escenario()
    ronda = await e.ronda(
        jugadores=(e.jugador(Gender.FEMALE, color=TeeColor.RED), e.jugador(Gender.MALE))
    )

    await e.caso_de_uso().execute(dry_run=False)

    [match] = await e.uow.matches.find_by_round(ronda.id)
    assert match.team_a_players[0].tee_color == TeeColor.RED


async def test_c5_ronda_sin_campo_nada():
    e = _Escenario(campo=None)
    ronda = await e.ronda()

    resumen = await e.caso_de_uso().execute(dry_run=False)

    assert await e.generos_de(ronda) == [None, None]
    assert resumen.jugadores == 0
    assert resumen.errores == []


async def test_c3_una_barra_sin_valorar_con_tarjeta_da_su_genero():
    """La misma regla que la generación (P12): con tarjeta, aunque no esté valorada."""
    sin_valorar = _barra(TeeColor.YELLOW, Gender.MALE)
    sin_valorar.slope_rating = 10  # fuera de rango: no se puede valorar
    sin_valorar.holes = AMARILLAS_DE_HOMBRE.reference_card
    sin_valorar.par_total = 72
    e = _Escenario(campo=_campo(sin_valorar))
    ronda = await e.ronda()

    await e.caso_de_uso().execute(dry_run=False)

    assert await e.generos_de(ronda) == [Gender.MALE, Gender.MALE]


@pytest.mark.parametrize(
    ("estado", "se_completa"),
    [("SCHEDULED", True), ("IN_PROGRESS", True), ("COMPLETED", False)],
)
async def test_c6_programadas_y_en_juego_si_terminadas_no(estado, se_completa):
    e = _Escenario()
    ronda = await e.ronda(estado=estado)

    await e.caso_de_uso().execute(dry_run=False)

    esperado = [Gender.MALE, Gender.MALE] if se_completa else [None, None]
    assert await e.generos_de(ronda) == esperado


async def test_c7_dry_run_cuenta_sin_escribir():
    e = _Escenario()
    ronda = await e.ronda()

    resumen = await e.caso_de_uso().execute(dry_run=True)

    assert resumen.jugadores == 2
    assert [r.jugadores for r in resumen.rondas] == [2]
    assert await e.generos_de(ronda) == [None, None]


async def test_c7_dry_run_no_cuenta_a_quien_ya_tiene_genero():
    e = _Escenario()
    await e.ronda(
        jugadores=(e.jugador(Gender.MALE, tee_gender=Gender.MALE), e.jugador(Gender.MALE))
    )

    resumen = await e.caso_de_uso().execute(dry_run=True)

    assert resumen.jugadores == 1


async def test_c8_si_una_ronda_falla_lo_dice_y_sigue():
    e = _Escenario()
    mala = await e.ronda()
    buena = await e.ronda()
    reales = e.campos.find_by_id

    async def falla_en_la_mala(golf_course_id):
        if golf_course_id == mala.golf_course_id:
            raise RuntimeError("campo roto")
        return await reales(golf_course_id)

    e.campos.find_by_id = AsyncMock(side_effect=falla_en_la_mala)

    resumen = await e.caso_de_uso().execute(dry_run=False)

    assert await e.generos_de(buena) == [Gender.MALE, Gender.MALE]
    assert len(resumen.errores) == 1
    assert "campo roto" in resumen.errores[0]


async def test_c6_en_una_ronda_en_juego_los_partidos_terminados_no_se_tocan():
    """Agustín: se jugaron con esa tarjeta. Los demás de la ronda, sí."""
    e = _Escenario()
    ronda = await e.ronda(
        estado="IN_PROGRESS",
        partidos=[
            ([e.jugador(Gender.MALE)], [e.jugador(Gender.MALE)]),
            ([e.jugador(Gender.MALE)], [e.jugador(Gender.MALE)]),
        ],
    )
    terminado = sorted(await e.uow.matches.find_by_round(ronda.id), key=lambda m: m.match_number)[0]
    terminado.start()
    terminado.concede(conceding_team="B")

    seco = await e.caso_de_uso().execute(dry_run=True)
    resumen = await e.caso_de_uso().execute(dry_run=False)

    assert await e.generos_de(ronda) == [None, None, Gender.MALE, Gender.MALE]
    assert (seco.jugadores, resumen.jugadores) == (2, 2)


async def test_fourball_cada_uno_de_los_cuatro():
    e = _Escenario()
    ronda = await e.ronda(
        partidos=[
            (
                [e.jugador(Gender.MALE), e.jugador(Gender.FEMALE, color=TeeColor.RED)],
                [e.jugador(Gender.MALE), e.jugador(Gender.MALE)],
            )
        ]
    )

    resumen = await e.caso_de_uso().execute(dry_run=False)

    assert await e.generos_de(ronda) == [Gender.MALE, Gender.FEMALE, Gender.MALE, Gender.MALE]
    assert resumen.jugadores == 4


async def test_c8_si_fallan_las_rondas_de_una_competicion_sigue_con_la_siguiente():
    e = _Escenario()
    mala = await e.ronda()
    buena = await e.ronda()
    reales = e.uow.rounds.find_by_competition

    async def falla_en_la_mala(competition_id):
        if competition_id == mala.competition_id:
            raise RuntimeError("rondas rotas")
        return await reales(competition_id)

    e.uow.rounds.find_by_competition = AsyncMock(side_effect=falla_en_la_mala)

    resumen = await e.caso_de_uso().execute(dry_run=False)

    assert await e.generos_de(buena) == [Gender.MALE, Gender.MALE]
    assert len(resumen.errores) == 1
    assert "rondas rotas" in resumen.errores[0]


async def test_c8_tras_un_fallo_se_deshace_la_ronda():
    e = _Escenario()
    await e.ronda()
    deshacer = AsyncMock(wraps=e.uow.rollback)
    e.uow.rollback = deshacer
    e.usuarios.find_by_ids = AsyncMock(side_effect=RuntimeError("usuarios rotos"))

    resumen = await e.caso_de_uso().execute(dry_run=False)

    assert len(resumen.errores) == 1
    deshacer.assert_awaited()
