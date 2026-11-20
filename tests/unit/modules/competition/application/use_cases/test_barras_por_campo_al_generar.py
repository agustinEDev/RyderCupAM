"""
Al generar, cada uno juega la barra que le toca en ESE campo (barras por campo, 20 nov 2026).

| #  | Caso                                                      | Resultado                      |
|----|-----------------------------------------------------------|--------------------------------|
| R2 | Barra del campo para las mujeres (azules)                 | Bea sale en azules             |
| R1 | Su cambio propio (blancas) aunque haya una para mujeres   | Bea sale en blancas            |
| R2 | La de las mujeres no toca a los hombres                   | Ellos en sus amarillas         |
| R4 | Su barra (rojas) no está en el campo y no hay cambios     | Bloqueo «TEE_COLOR», con RED   |
| R4 | Con la del campo para las mujeres, se desbloquea          | Partidos                       |
"""

import pytest

from src.modules.golf_course.domain.value_objects.tee_color import TeeColor
from src.shared.domain.value_objects.gender import Gender
from tests.unit.modules.competition.application.use_cases.test_partidos_al_abrir_los_sobres import (
    _montar,
)

pytestmark = pytest.mark.asyncio

# Amarillas de hombre, y azules y blancas de mujer: sin las rojas habituales de ellas
SIN_ROJAS = [
    (TeeColor.YELLOW, Gender.MALE),
    (TeeColor.BLUE, Gender.FEMALE),
    (TeeColor.WHITE, Gender.FEMALE),
]


async def _torneo_con_bea():
    """Bea (A2) es mujer; los otros tres, hombres."""
    return await _montar(
        barras=SIN_ROJAS, sexos=[Gender.MALE, Gender.FEMALE, Gender.MALE, Gender.MALE]
    )


async def _campo(torneo):
    return (await torneo.ronda()).golf_course_id


async def _barra_de(torneo, user_id):
    for partido in await torneo.partidos():
        foto = partido.find_player(user_id)
        if foto is not None:
            return foto.tee_color, foto.tee_gender
    raise AssertionError("no juega")


async def test_generar_sin_su_barra_en_el_campo_se_bloquea():
    """
    Given Bea sin barra elegida (rojas, las habituales) en un campo sin rojas de mujer
    When se abren los sobres
    Then no hay partidos: le falta su color, RED (R4, no se elige otra sola)
    """
    torneo = await _torneo_con_bea()
    await torneo.entregan_los_dos()

    await torneo.abrir().execute(torneo.ronda_id.value, torneo.organizador)

    assert await torneo.partidos() == []
    [bea] = (await torneo.ronda()).match_generation_block.players
    assert (bea.missing, bea.tee_color) == ("TEE_COLOR", "RED")


async def test_generar_con_la_barra_del_campo_para_mujeres_la_usa():
    """
    Given el mismo campo con azules fijadas para las mujeres
    When se abren los sobres
    Then hay partidos: Bea en azules de mujer (R2), y los hombres en sus amarillas
    """
    torneo = await _torneo_con_bea()
    await torneo.uow.barras_por_campo.fijar_del_campo(
        torneo.comp_id, await _campo(torneo), Gender.FEMALE, TeeColor.BLUE
    )
    await torneo.entregan_los_dos()

    await torneo.abrir().execute(torneo.ronda_id.value, torneo.organizador)

    assert await _barra_de(torneo, torneo.equipo_a[1]) == (TeeColor.BLUE, Gender.FEMALE)
    assert await _barra_de(torneo, torneo.equipo_a[0]) == (TeeColor.YELLOW, Gender.MALE)


async def test_generar_con_su_cambio_propio_gana_a_la_del_campo():
    """
    Given azules para las mujeres en el campo y Bea con un cambio propio a blancas
    When se abren los sobres
    Then Bea en blancas (R1 gana a R2)
    """
    torneo = await _torneo_con_bea()
    campo = await _campo(torneo)
    await torneo.uow.barras_por_campo.fijar_del_campo(
        torneo.comp_id, campo, Gender.FEMALE, TeeColor.BLUE
    )
    [bea] = [
        i
        for i in await torneo.uow.enrollments.find_by_competition(torneo.comp_id)
        if i.user_id == torneo.equipo_a[1]
    ]
    await torneo.uow.barras_por_campo.fijar_propia(bea, campo, TeeColor.WHITE)
    await torneo.entregan_los_dos()

    await torneo.abrir().execute(torneo.ronda_id.value, torneo.organizador)

    assert await _barra_de(torneo, torneo.equipo_a[1]) == (TeeColor.WHITE, Gender.FEMALE)
