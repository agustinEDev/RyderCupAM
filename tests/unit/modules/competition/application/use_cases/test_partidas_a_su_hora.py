"""
Una partida a la que le llegó su hora ya salió, aunque su estado no lo diga (#251, PR 4).

Hasta la PR 5 nadie pasa una partida a IN_PROGRESS: la hora es lo que cuenta
(revisión de la PR 4, 9 oct 2026; D2, D11). Franja de 9:00 cada 10', y son las
9:30 en Madrid.

| Caso                                                  | Resultado                         |
|-------------------------------------------------------|-----------------------------------|
| Se retira el único de la de las 9:00                  | Se queda: ya salió                |
| Se retira el único de la de las 9:40                  | Sale; las de detrás no suben      |
| G1 para uno de la de las 9:00                         | No se recalcula                   |
| Cambiar la hoja de una franja con partidas ya salidas | FranjaInvalidaError               |
"""

from datetime import UTC, datetime, time
from decimal import Decimal

import pytest

from src.modules.competition.application.dto.enrollment_dto import WithdrawEnrollmentRequestDTO
from src.modules.competition.application.dto.round_match_dto import (
    TeeSheetDTO,
    UpdateRoundRequestDTO,
)
from src.modules.competition.application.exceptions import FranjaInvalidaError
from src.modules.competition.application.services.jugadores_de_la_partida import (
    JugadoresDeLaPartida,
)
from src.modules.competition.application.services.partidas_de_la_franja import (
    recalcular_su_handicap,
)
from src.modules.competition.application.use_cases.update_round_use_case import (
    UpdateRoundUseCase,
)
from src.modules.competition.application.use_cases.withdraw_enrollment_use_case import (
    WithdrawEnrollmentUseCase,
)
from src.modules.competition.domain.entities.partida import Partida
from src.modules.competition.domain.value_objects.competition_status import CompetitionStatus
from src.shared.domain.value_objects.country_code import CountryCode
from tests.unit.modules.competition.application.use_cases.test_generar_partidas_use_case import (
    _Escenario,
)

pytestmark = pytest.mark.asyncio

# Las 9:30 de Madrid del viernes 11 oct 2030
A_LAS_NUEVE_Y_MEDIA = datetime(2030, 10, 11, 7, 30, tzinfo=UTC)


async def _de_uno_en_uno(numeros: list[int]) -> tuple[_Escenario, list]:
    """Una partida de 1 en cada número dado (por bajas), y las 9:30 ya."""
    escenario = _Escenario()
    escenario.competicion.add_golf_course(escenario.manana.golf_course_id, CountryCode("ES"))
    await escenario.guardar()
    for h in range(len(numeros) + 1, 0, -1):
        await escenario.con_plaza(f"{h}.0")
    await escenario.generar()
    fotos = [
        j
        for p in await escenario.uow.partidas.de_la_franja(escenario.manana.id)
        for j in p.jugadores
    ]
    montadas = [
        Partida.crear(escenario.competicion.id, escenario.manana.id, n, [foto])
        for n, foto in zip(numeros, fotos, strict=False)
    ]
    await escenario.uow.partidas.reemplazar_franja(escenario.manana.id, montadas)
    escenario.competicion._status = CompetitionStatus.IN_PROGRESS
    escenario.ahora = A_LAS_NUEVE_Y_MEDIA
    return escenario, montadas


async def _retirar(escenario: _Escenario, partida: Partida) -> None:
    (jugador,) = partida.user_ids
    (inscripcion,) = await escenario.uow.enrollments.find_by_user_ids_and_competition(
        [jugador], escenario.competicion.id
    )
    await WithdrawEnrollmentUseCase(
        escenario.uow, zonas=escenario.zonas, reloj=lambda: escenario.ahora
    ).execute(WithdrawEnrollmentRequestDTO(enrollment_id=inscripcion.id.value), jugador)


async def _numeros(escenario: _Escenario) -> list[int]:
    return [p.numero for p in await escenario.uow.partidas.de_la_franja(escenario.manana.id)]


async def test_the_only_one_of_the_nine_oclock_group_stays():
    escenario, (nueve, _) = await _de_uno_en_uno([1, 5])

    await _retirar(escenario, nueve)

    assert await _numeros(escenario) == [1, 5]


async def test_the_only_one_of_the_nine_forty_leaves_and_nobody_moves_up():
    escenario, (_, nueve_cuarenta, _) = await _de_uno_en_uno([1, 5, 6])

    await _retirar(escenario, nueve_cuarenta)

    assert await _numeros(escenario) == [1, 6]


async def test_g1_does_not_touch_a_group_already_out():
    escenario, (nueve, _) = await _de_uno_en_uno([1, 5])
    (jugador,) = nueve.user_ids
    (inscripcion,) = await escenario.uow.enrollments.find_by_user_ids_and_competition(
        [jugador], escenario.competicion.id
    )
    inscripcion.congelar_handicap(Decimal("30.0"), 1)

    await recalcular_su_handicap(
        escenario.uow,
        JugadoresDeLaPartida(escenario.campos, escenario.usuarios),
        escenario.competicion,
        jugador,
        zonas=escenario.zonas,
        ahora=escenario.ahora,
    )

    (despues, _) = await escenario.uow.partidas.de_la_franja(escenario.manana.id)
    assert despues.jugadores == nueve.jugadores


async def test_changing_the_tee_sheet_of_a_window_already_in_play():
    escenario, _ = await _de_uno_en_uno([1, 5])
    escenario.competicion._status = CompetitionStatus.CLOSED

    with pytest.raises(FranjaInvalidaError):
        await UpdateRoundUseCase(
            escenario.uow,
            jugadores=JugadoresDeLaPartida(escenario.campos, escenario.usuarios),
            zonas=escenario.zonas,
            reloj=lambda: escenario.ahora,
        ).execute(
            UpdateRoundRequestDTO(
                round_id=escenario.manana.id.value,
                tee_sheet=TeeSheetDTO(
                    first_tee_time=time(9, 0),
                    last_tee_time=time(10, 0),
                    interval_minutes=5,
                    group_size=4,
                ),
            ),
            escenario.creador,
        )
