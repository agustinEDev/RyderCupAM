"""
Las barras por campo en stroke play (20 nov 2026).

| Caso                                                         | Resultado                      |
|--------------------------------------------------------------|--------------------------------|
| Generar la foto con la barra del campo para su género (R2)   | Sale en esa                    |
| Generar con su cambio propio (R1), aunque haya una para todas | Sale en la suya               |
| Generar en SCRATCH con la del campo                          | Sale en esa                    |
| Su cambio propio en un campo rehace solo la partida de ese campo | La del otro no cambia      |
| Cambiar su barra general no toca la partida de un campo con R1 | Sigue en la suya             |
"""

import pytest

from src.modules.competition.application.dto.enrollment_dto import (
    ChangeEnrollmentCourseTeeRequestDTO,
)
from src.modules.competition.application.services.jugadores_de_la_partida import (
    JugadoresDeLaPartida,
)
from src.modules.competition.application.use_cases.change_enrollment_course_tee_use_case import (
    ChangeEnrollmentCourseTeeUseCase,
)
from src.modules.competition.domain.value_objects.tournament_type import TournamentType
from src.modules.golf_course.domain.value_objects.tee_color import TeeColor
from src.shared.domain.value_objects.gender import Gender
from tests.unit.modules.competition.application.use_cases.test_change_enrollment_tee_use_case import (
    ALDEAMAYOR,
    _Mundo,
)

pytestmark = pytest.mark.asyncio

# Rojas, azules y blancas de mujer
CON_BLANCAS = [*ALDEAMAYOR, (TeeColor.WHITE, Gender.FEMALE)]


async def _stableford(campos=(CON_BLANCAS,), play_mode="HANDICAP"):
    return await _Mundo().montar(campos=campos, play_mode=play_mode, tipo=TournamentType.STABLEFORD)


async def _foto_al_generar(mundo, campo=0):
    """La foto de la jugadora al generar las partidas de una franja de ese campo."""
    partida = await mundo.partida_con(mundo.jugadora, campo=campo)
    franja = await mundo.uow.rounds.find_by_id((await mundo.la_partida(partida)).round_id)
    competicion = await mundo.uow.competitions.find_by_id(mundo.competition_id)
    fotos = await JugadoresDeLaPartida(mundo.campos, mundo.usuarios).construir(
        mundo.uow, competicion, franja, [mundo.jugadora]
    )
    return fotos[mundo.jugadora]


async def _propia(mundo, campo, color):
    await ChangeEnrollmentCourseTeeUseCase(
        mundo.uow, golf_course_repository=mundo.campos, user_repository=mundo.usuarios
    ).execute(
        ChangeEnrollmentCourseTeeRequestDTO(
            enrollment_id=mundo.inscripcion.id.value, golf_course_id=campo.value, tee_color=color
        ),
        mundo.jugadora,
    )


async def test_generar_partidas_con_la_barra_del_campo_para_su_genero():
    """
    Given un Stableford con azules fijadas para las mujeres en su campo
    When se saca su foto para generar las partidas
    Then sale en azules de mujer (R2), no en sus rojas habituales
    """
    mundo = await _stableford()
    campo = next(iter(mundo.campos.por_id))
    await mundo.uow.barras_por_campo.fijar_del_campo(
        mundo.competition_id, campo, Gender.FEMALE, TeeColor.BLUE
    )

    foto = await _foto_al_generar(mundo)

    assert (foto.tee_color, foto.tee_gender) == (TeeColor.BLUE, Gender.FEMALE)


async def test_generar_partidas_con_su_cambio_propio_gana_a_la_del_campo():
    """
    Given azules para las mujeres en su campo y su cambio propio a blancas
    When se saca su foto
    Then sale en blancas (R1)
    """
    mundo = await _stableford()
    campo = next(iter(mundo.campos.por_id))
    await mundo.uow.barras_por_campo.fijar_del_campo(
        mundo.competition_id, campo, Gender.FEMALE, TeeColor.BLUE
    )
    await mundo.uow.barras_por_campo.fijar_propia(mundo.inscripcion, campo, TeeColor.WHITE)

    foto = await _foto_al_generar(mundo)

    assert foto.tee_color == TeeColor.WHITE


async def test_generar_partidas_en_scratch_con_la_barra_del_campo():
    """
    Given un Stableford SCRATCH con azules para las mujeres en su campo
    When se saca su foto
    Then sale en azules, sin golpes
    """
    mundo = await _stableford(play_mode="SCRATCH")
    campo = next(iter(mundo.campos.por_id))
    await mundo.uow.barras_por_campo.fijar_del_campo(
        mundo.competition_id, campo, Gender.FEMALE, TeeColor.BLUE
    )

    foto = await _foto_al_generar(mundo)

    assert (foto.tee_color, foto.playing_handicap) == (TeeColor.BLUE, 0)


async def test_su_cambio_propio_en_un_campo_rehace_solo_la_partida_de_ese_campo():
    """
    Given la jugadora con una partida pendiente en cada uno de dos campos
    When fija blancas en el segundo
    Then la partida del segundo sale en blancas y la del primero no cambia
    """
    mundo = await _stableford(campos=(ALDEAMAYOR, CON_BLANCAS))
    _, segundo = list(mundo.campos.por_id)
    en_el_primero = await mundo.partida_con(mundo.jugadora, campo=0)
    en_el_segundo = await mundo.partida_con(mundo.jugadora, campo=1)

    await _propia(mundo, segundo, TeeColor.WHITE)

    [del_segundo] = (await mundo.la_partida(en_el_segundo)).jugadores
    [del_primero] = (await mundo.la_partida(en_el_primero)).jugadores
    assert del_segundo.tee_color == TeeColor.WHITE
    assert (del_primero.tee_color, del_primero.playing_handicap) == (TeeColor.YELLOW, 10)


async def test_cambiar_la_general_no_toca_la_partida_de_un_campo_con_su_cambio_propio():
    """
    Given su cambio propio a blancas en el campo de su partida, ya aplicado
    When cambia su barra general a azules
    Then la partida sigue en blancas: en ese campo gana su cambio propio
    """
    mundo = await _stableford()
    campo = next(iter(mundo.campos.por_id))
    partida = await mundo.partida_con(mundo.jugadora)
    await _propia(mundo, campo, TeeColor.WHITE)

    await mundo.cambiar(TeeColor.BLUE)

    [ella] = (await mundo.la_partida(partida)).jugadores
    assert ella.tee_color == TeeColor.WHITE
