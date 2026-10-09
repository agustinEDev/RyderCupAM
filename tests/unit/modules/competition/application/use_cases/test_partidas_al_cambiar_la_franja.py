"""
Cambiar una franja que ya tiene partidas (#251, PR 4; D9 y G2 del 9 oct 2026).

| Cambio                                          | Resultado                               |
|-------------------------------------------------|-----------------------------------------|
| Primera salida 9:30, intervalo 5                | Mismo número; la hora, de la hoja nueva |
| Partidas de 3 con una de 4                      | FranjaInvalidaError                     |
| Menos salidas que partidas (aunque quepan)      | FranjaInvalidaError                     |
| Otro campo, todos con barras                    | Fotos recalculadas y guardadas          |
| Otro campo, alguien sin barras                  | JugadoresSinBarraError, nada tocado     |
"""

from datetime import time
from decimal import Decimal

import pytest

from src.modules.competition.application.dto.round_match_dto import (
    TeeSheetDTO,
    UpdateRoundRequestDTO,
)
from src.modules.competition.application.exceptions import FranjaInvalidaError
from src.modules.competition.application.services.jugadores_de_la_partida import (
    JugadoresDeLaPartida,
    JugadoresSinBarraError,
)
from src.modules.competition.application.use_cases.partidas_use_case import (
    MoverJugadorUseCase,
    VerPartidasUseCase,
)
from src.modules.competition.application.use_cases.update_round_use_case import (
    UpdateRoundUseCase,
)
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.golf_course.domain.value_objects.tee_color import TeeColor
from src.shared.domain.value_objects.country_code import CountryCode
from src.shared.domain.value_objects.gender import Gender
from tests.unit.modules.competition.application.services.test_jugadores_de_la_partida import (
    _campo,
)
from tests.unit.modules.competition.application.use_cases.test_generar_partidas_use_case import (
    _Escenario,
)

pytestmark = pytest.mark.asyncio


async def _generadas(*handicaps: str) -> _Escenario:
    escenario = _Escenario()
    escenario.competicion.add_golf_course(escenario.manana.golf_course_id, CountryCode("ES"))
    await escenario.guardar()
    for h in handicaps:
        await escenario.con_plaza(h)
    await escenario.generar()
    return escenario


def _cambiar(escenario: _Escenario, **cambios):
    return UpdateRoundUseCase(
        escenario.uow, jugadores=JugadoresDeLaPartida(escenario.campos, escenario.usuarios)
    ).execute(
        UpdateRoundRequestDTO(round_id=escenario.manana.id.value, **cambios),
        escenario.creador,
    )


def _hoja(primera=time(9, 0), ultima=time(10, 0), intervalo=10, tamano=4) -> TeeSheetDTO:
    return TeeSheetDTO(
        first_tee_time=primera,
        last_tee_time=ultima,
        interval_minutes=intervalo,
        group_size=tamano,
    )


async def _vista(escenario: _Escenario):
    return await VerPartidasUseCase(
        uow=escenario.uow,
        zonas=escenario.zonas,
        user_repository=escenario.usuarios,
        reloj=lambda: escenario.ahora,
    ).execute(escenario.manana.id.value)


async def _partidas(escenario: _Escenario):
    return await escenario.uow.partidas.de_la_franja(escenario.manana.id)


async def test_moving_the_first_tee_time_moves_every_group():
    escenario = await _generadas(*[f"{h}.0" for h in range(8, 0, -1)])

    await _cambiar(escenario, tee_sheet=_hoja(primera=time(9, 30), ultima=time(10, 0), intervalo=5))

    vista = await _vista(escenario)
    assert [(g.number, g.tee_time) for g in vista.groups] == [(1, "09:30"), (2, "09:35")]


async def test_groups_of_three_with_one_of_four():
    escenario = await _generadas("4.0", "3.0", "2.0", "1.0")

    with pytest.raises(FranjaInvalidaError):
        await _cambiar(escenario, tee_sheet=_hoja(tamano=3))


async def test_fewer_tee_times_than_groups_even_if_the_places_fit():
    escenario = await _generadas("5.0", "4.0", "3.0", "2.0", "1.0")
    primera, _ = await _partidas(escenario)
    # 3 + 2 -> 2 + 2 + 1: tres partidas para cinco jugadores
    await MoverJugadorUseCase(
        uow=escenario.uow,
        jugadores=JugadoresDeLaPartida(escenario.campos, escenario.usuarios),
        zonas=escenario.zonas,
        user_repository=escenario.usuarios,
        reloj=lambda: escenario.ahora,
    ).execute(
        escenario.manana.id.value,
        primera.user_ids[0].value,
        None,
        None,
        escenario.creador,
        False,
    )

    # Dos salidas de 4: caben las 5 plazas, no las 3 partidas
    with pytest.raises(FranjaInvalidaError):
        await _cambiar(escenario, tee_sheet=_hoja(ultima=time(9, 10)))


def _otro_campo(escenario: _Escenario, barras, course_rating: str) -> GolfCourseId:
    nuevo = GolfCourseId.generate()
    escenario.competicion.add_golf_course(nuevo, CountryCode("ES"))
    campo = _campo(barras)
    for tee in campo.tees:
        tee.course_rating = Decimal(course_rating)
    de_antes = escenario.campos.find_by_id.return_value
    escenario.campos.find_by_id.side_effect = lambda gc: campo if gc == nuevo else de_antes
    return nuevo


async def test_another_course_recalculates_the_groups():
    escenario = await _generadas("10.0", "9.0")
    antes = [j.playing_handicap for j in (await _partidas(escenario))[0].jugadores]
    nuevo = _otro_campo(escenario, ((TeeColor.YELLOW, Gender.MALE),), "74.0")

    await _cambiar(escenario, golf_course_id=nuevo.value)

    despues = [j.playing_handicap for j in (await _partidas(escenario))[0].jugadores]
    assert all(d > a for a, d in zip(antes, despues, strict=True))


async def test_another_course_without_tees_for_someone_is_refused():
    escenario = await _generadas("10.0", "9.0")
    antes = [j.playing_handicap for j in (await _partidas(escenario))[0].jugadores]
    nuevo = _otro_campo(escenario, ((TeeColor.RED, Gender.FEMALE),), "71.2")

    with pytest.raises(JugadoresSinBarraError):
        await _cambiar(escenario, golf_course_id=nuevo.value)

    assert [j.playing_handicap for j in (await _partidas(escenario))[0].jugadores] == antes
