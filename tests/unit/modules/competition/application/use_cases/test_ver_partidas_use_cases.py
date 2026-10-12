"""
Ver las partidas de una franja y las mías (#251, PR 4; D8 del 9 oct 2026).

Cualquiera con sesión, como los partidos de la Ryder. `editable` dice si el
organizador aún puede tocarlas; mirar nunca falla por eso.

| Caso                                                     | Resultado                         |
|----------------------------------------------------------|-----------------------------------|
| Un jugador mira la franja                                | La vista, igual que al generar    |
| Antes de generar                                         | Sin partidas, todos en unassigned |
| Abiertas / tras la 1.ª salida / una empezada / sin zona  | editable: false, sin error        |
| unassigned                                               | Ni retirados ni ya colocados      |
| Una sesión de Ryder / una franja que no existe           | PartidasError / RoundNotFound     |
| Mis partidas, en dos franjas                             | Las dos, por día y hora           |
| Mis partidas, sin ninguna                                | []                                |
"""

from datetime import time

import pytest

from src.modules.competition.application.exceptions import PartidasError, RoundNotFoundError
from src.modules.competition.application.use_cases.partidas_use_case import (
    MisPartidasUseCase,
    VerPartidasUseCase,
)
from src.modules.competition.domain.entities.partida import Partida
from src.modules.competition.domain.entities.round import Round
from src.modules.competition.domain.value_objects.competition_status import CompetitionStatus
from src.modules.competition.domain.value_objects.enrollment_status import EnrollmentStatus
from src.modules.competition.domain.value_objects.estado_partida import EstadoPartida
from src.modules.competition.domain.value_objects.hoja_de_salidas import HojaDeSalidas
from src.modules.competition.domain.value_objects.round_id import RoundId
from src.modules.competition.domain.value_objects.session_type import SessionType
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.match_format import MatchFormat
from tests.unit.modules.competition.application.use_cases.test_generar_partidas_use_case import (
    A_LA_PRIMERA_SALIDA,
    VIERNES,
    _Escenario,
)

pytestmark = pytest.mark.asyncio


def _ver(escenario: _Escenario) -> VerPartidasUseCase:
    return VerPartidasUseCase(
        uow=escenario.uow,
        zonas=escenario.zonas,
        user_repository=escenario.usuarios,
        reloj=lambda: escenario.ahora,
    )


async def _vista(escenario: _Escenario, franja=None):
    return await _ver(escenario).execute((franja or escenario.manana).id.value)


async def test_a_player_sees_the_same_as_the_organiser():
    escenario = _Escenario()
    await escenario.guardar()
    jugadores = [await escenario.con_plaza(f"{h}.0") for h in (3, 2, 1)]
    generada = await escenario.generar()

    vista = await _vista(escenario)

    assert vista == generada
    assert {p.user_id for p in vista.groups[0].players} == {u.value for u in jugadores}


async def test_before_generating_everybody_is_unassigned():
    escenario = _Escenario()
    await escenario.guardar()
    jugadores = [await escenario.con_plaza(f"{h}.0") for h in (3, 2)]

    vista = await _vista(escenario)

    assert vista.groups == []
    assert [p.name for p in vista.unassigned_players] == ["Jugador 3.0", "Jugador 2.0"]
    assert [p.user_id for p in vista.unassigned_players] == [u.value for u in jugadores]
    assert vista.editable


async def test_unassigned_leaves_out_the_withdrawn_and_the_placed():
    escenario = _Escenario()
    await escenario.guardar()
    for h in (3, 2):
        await escenario.con_plaza(f"{h}.0")
    await escenario.generar()
    tarde = await escenario.con_plaza("9.0")
    await escenario.con_plaza("8.0", status=EnrollmentStatus.WITHDRAWN)

    assert [p.user_id for p in (await _vista(escenario)).unassigned_players] == [tarde.value]


@pytest.mark.parametrize(
    ("status", "zona", "ahora"),
    [
        pytest.param(CompetitionStatus.ACTIVE, "Europe/Madrid", None, id="inscripciones abiertas"),
        pytest.param(CompetitionStatus.CLOSED, "Europe/Madrid", A_LA_PRIMERA_SALIDA, id="salió"),
        pytest.param(CompetitionStatus.CLOSED, None, None, id="sin zona"),
    ],
)
async def test_not_editable_without_failing(status, zona, ahora):
    escenario = _Escenario(status=status, zona=zona)
    if ahora:
        escenario.ahora = ahora
    await escenario.guardar()

    vista = await _vista(escenario)

    assert vista.editable is False


async def test_not_editable_once_a_group_started():
    escenario = _Escenario()
    await escenario.guardar()
    for h in (3, 2):
        await escenario.con_plaza(f"{h}.0")
    await escenario.generar()
    (partida,) = await escenario.uow.partidas.de_la_franja(escenario.manana.id)
    await escenario.uow.partidas.guardar(
        [
            Partida(
                id=partida.id,
                competition_id=partida.competition_id,
                round_id=partida.round_id,
                numero=partida.numero,
                jugadores=partida.jugadores,
                marcadores=partida.marcadores,
                estado=EstadoPartida.IN_PROGRESS,
            )
        ]
    )

    vista = await _vista(escenario)

    assert vista.editable is False
    assert vista.groups[0].status == "IN_PROGRESS"


async def test_a_ryder_session_and_a_window_that_does_not_exist():
    escenario = _Escenario()
    await escenario.guardar()
    sesion = Round.create(
        competition_id=escenario.competicion.id,
        golf_course_id=GolfCourseId.generate(),
        round_date=VIERNES,
        session_type=SessionType.EVENING,
        match_format=MatchFormat.SINGLES,
    )
    async with escenario.uow:
        await escenario.uow.rounds.add(sesion)

    with pytest.raises(PartidasError):
        await _vista(escenario, sesion)
    with pytest.raises(RoundNotFoundError):
        await _ver(escenario).execute(RoundId.generate().value)


async def test_my_groups_in_two_windows_by_day_and_time():
    escenario = _Escenario()
    await escenario.guardar()
    yo = await escenario.con_plaza("5.0", franja=escenario.tarde)
    await escenario.con_plaza("6.0", franja=escenario.tarde)
    for h in (3, 2):
        await escenario.con_plaza(f"{h}.0")
    await escenario.generar()
    await escenario.generar(franja=escenario.tarde)
    # Y otra franja, por la mañana, en la que también juega
    temprano = Round.create_franja(
        competition_id=escenario.competicion.id,
        golf_course_id=GolfCourseId.generate(),
        round_date=VIERNES,
        session_type=SessionType.EVENING,
        hoja_de_salidas=HojaDeSalidas(time(7, 0), time(8, 0), 10, 4),
    )
    async with escenario.uow:
        await escenario.uow.rounds.add(temprano)
    tarde_partida = (await escenario.uow.partidas.de_la_franja(escenario.tarde.id))[0]
    yo_jugador = next(j for j in tarde_partida.jugadores if j.user_id == yo)
    otro = next(j for j in tarde_partida.jugadores if j.user_id != yo)
    await escenario.uow.partidas.anadir(
        [Partida.crear(escenario.competicion.id, temprano.id, 1, [yo_jugador, otro])]
    )

    mias = await MisPartidasUseCase(uow=escenario.uow, user_repository=escenario.usuarios).execute(
        escenario.competicion.id.value, yo
    )

    assert [(g.round_id, g.group.tee_time) for g in mias.groups] == [
        (temprano.id.value, "07:00"),
        (escenario.tarde.id.value, "15:00"),
    ]
    assert mias.groups[1].session_type == "AFTERNOON"
    assert {p.user_id for p in mias.groups[1].group.players} == {yo.value, otro.user_id.value}


async def test_my_groups_without_any():
    escenario = _Escenario()
    await escenario.guardar()

    mias = await MisPartidasUseCase(uow=escenario.uow, user_repository=escenario.usuarios).execute(
        escenario.competicion.id.value, UserId.generate()
    )

    assert mias.groups == []
