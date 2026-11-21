"""
Al generar, cada uno juega la barra que le toca en ESE campo (barras por campo, 20 nov 2026).

| #  | Caso                                                      | Resultado                      |
|----|-----------------------------------------------------------|--------------------------------|
| R2 | Barra del campo para las mujeres (azules)                 | Bea sale en azules             |
| R1 | Su cambio propio (blancas) aunque haya una para mujeres   | Bea sale en blancas            |
| R2 | La de las mujeres no toca a los hombres                   | Ellos en sus amarillas         |
| R4 | Su barra (rojas) no está en el campo y no hay cambios     | Bloqueo «TEE_COLOR», con RED   |
| R4 | Con la del campo para las mujeres, se desbloquea          | Partidos                       |

En SCRATCH, el mismo criterio que el selector (`GET /enrollments/{id}/tees`): le
vale su barra valorada o con tarjeta, de su género o mixta. Sin ella (R4), se
bloquea igual que con hándicap (pasada del Kind del 21 nov 2026: se generaban).

| #  | SCRATCH: campo sin amarillas ni verdes de mujer                  | Resultado                         |
|----|------------------------------------------------------------------|-----------------------------------|
| G1 | Dos mujeres con general amarillas y verdes, sin R1 ni R2         | Bloqueo con las dos, sin partidos |
| G2 | La del campo para las mujeres (rojas)                            | Partidos, ellas en rojas de mujer |
| G3 | Su cambio propio (rojas)                                         | Partidos                          |
| G4 | Las rojas de mujer solo con tarjeta, sin valorar                 | Partidos, en rojas de mujer       |
| G5 | Amarillas mixtas                                                 | Partidos, en amarillas sin género |
| G7 | El reintento a mano con emparejamientos                          | El error de siempre, sin partidos |
| G8 | Regenerar cuando ya no tienen barra                              | El error; los partidos siguen     |
"""

import pytest

from src.modules.competition.application.dto.round_match_dto import (
    GenerateMatchesRequestDTO,
    ManualPairingDTO,
)
from src.modules.competition.application.services.match_players_builder import TeeColorNotFoundError
from src.modules.golf_course.domain.value_objects.tee_color import TeeColor
from src.shared.domain.value_objects.gender import Gender
from src.shared.domain.value_objects.play_mode import PlayMode
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


# Como Aldeamayor: amarillas y verdes solo de hombre, y rojas de mujer
SIN_AMARILLAS_NI_VERDES_DE_MUJER = [
    (TeeColor.YELLOW, Gender.MALE),
    (TeeColor.GREEN, Gender.MALE),
    (TeeColor.RED, Gender.FEMALE),
]


async def _scratch_con_dos_mujeres(barras=None):
    """
    Una Ryder SCRATCH: Bea (A2) con general amarillas y Dani (B2) con general verdes;
    Ana (A1) y Carla (B1), hombres sin barra elegida (amarillas de hombre).
    """
    torneo = await _montar(
        barras=barras or SIN_AMARILLAS_NI_VERDES_DE_MUJER,
        sexos=[Gender.MALE, Gender.FEMALE, Gender.MALE, Gender.FEMALE],
        modo=PlayMode.SCRATCH,
    )
    generales = {torneo.equipo_a[1]: TeeColor.YELLOW, torneo.equipo_b[1]: TeeColor.GREEN}
    async with torneo.uow:
        for inscripcion in await torneo.uow.enrollments.find_by_competition(torneo.comp_id):
            if inscripcion.user_id in generales:
                inscripcion.set_tee_color(generales[inscripcion.user_id])
                await torneo.uow.enrollments.update(inscripcion)
    return torneo


def _ellas(torneo):
    return [torneo.equipo_a[1], torneo.equipo_b[1]]


def _emparejamientos(torneo):
    return [
        ManualPairingDTO(
            team_a_player_ids=[torneo.equipo_a[i].value],
            team_b_player_ids=[torneo.equipo_b[i].value],
        )
        for i in range(2)
    ]


class TestEnScratch:
    async def test_g1_sin_barra_valida_se_bloquea_con_las_dos(self):
        """
        Given una Ryder SCRATCH en un campo sin amarillas ni verdes de mujer, y dos
              mujeres con esas generales, sin cambio propio ni barra del campo
        When se abren los sobres
        Then no hay partidos: las dos en el aviso, cada una con su color (R4)
        """
        torneo = await _scratch_con_dos_mujeres()
        await torneo.entregan_los_dos()

        await torneo.abrir().execute(torneo.ronda_id.value, torneo.organizador)

        assert await torneo.partidos() == []
        bloqueo = (await torneo.ronda()).match_generation_block
        assert bloqueo.reason == "PLAYERS_WITHOUT_TEE"
        assert {(p.user_id, p.missing, p.tee_color) for p in bloqueo.players} == {
            (torneo.equipo_a[1], "TEE_COLOR", "YELLOW"),
            (torneo.equipo_b[1], "TEE_COLOR", "GREEN"),
        }

    async def test_g2_con_la_del_campo_para_las_mujeres_se_generan(self):
        """
        Given el mismo campo con rojas fijadas para las mujeres (R2)
        When se abren los sobres
        Then hay partidos, y ellas en rojas de mujer
        """
        torneo = await _scratch_con_dos_mujeres()
        await torneo.uow.barras_por_campo.fijar_del_campo(
            torneo.comp_id, await _campo(torneo), Gender.FEMALE, TeeColor.RED
        )
        await torneo.entregan_los_dos()

        await torneo.abrir().execute(torneo.ronda_id.value, torneo.organizador)

        for ella in _ellas(torneo):
            assert await _barra_de(torneo, ella) == (TeeColor.RED, Gender.FEMALE)

    async def test_g3_con_su_cambio_propio_se_generan(self):
        """
        Given el mismo campo y las dos con un cambio propio a rojas (R1)
        When se abren los sobres
        Then hay partidos, y ellas en rojas de mujer
        """
        torneo = await _scratch_con_dos_mujeres()
        campo = await _campo(torneo)
        for inscripcion in await torneo.uow.enrollments.find_by_competition(torneo.comp_id):
            if inscripcion.user_id in _ellas(torneo):
                await torneo.uow.barras_por_campo.fijar_propia(inscripcion, campo, TeeColor.RED)
        await torneo.entregan_los_dos()

        await torneo.abrir().execute(torneo.ronda_id.value, torneo.organizador)

        for ella in _ellas(torneo):
            assert await _barra_de(torneo, ella) == (TeeColor.RED, Gender.FEMALE)

    async def test_g4_una_barra_solo_con_tarjeta_de_su_genero_vale(self):
        """
        Given rojas para las mujeres (R2) y esas rojas de mujer con tarjeta pero sin
              valoración: en SCRATCH no hace falta
        When se abren los sobres
        Then hay partidos, y ellas en rojas de mujer
        """
        torneo = await _scratch_con_dos_mujeres()
        rojas = torneo.campos.campo.tees[2]
        rojas.slope_rating = 10  # fuera de rango: no se puede valorar
        rojas.holes = torneo.campos.campo.reference_card
        rojas.par_total = 72
        await torneo.uow.barras_por_campo.fijar_del_campo(
            torneo.comp_id, await _campo(torneo), Gender.FEMALE, TeeColor.RED
        )
        await torneo.entregan_los_dos()

        await torneo.abrir().execute(torneo.ronda_id.value, torneo.organizador)

        for ella in _ellas(torneo):
            assert await _barra_de(torneo, ella) == (TeeColor.RED, Gender.FEMALE)

    async def test_g5_una_barra_mixta_vale(self):
        """
        Given un campo con amarillas mixtas y verdes también mixtas
        When se abren los sobres
        Then hay partidos, y ellas en su general, sin género
        """
        torneo = await _scratch_con_dos_mujeres(
            barras=[(TeeColor.YELLOW, None), (TeeColor.GREEN, None)]
        )
        await torneo.entregan_los_dos()

        await torneo.abrir().execute(torneo.ronda_id.value, torneo.organizador)

        assert await _barra_de(torneo, torneo.equipo_a[1]) == (TeeColor.YELLOW, None)
        assert await _barra_de(torneo, torneo.equipo_b[1]) == (TeeColor.GREEN, None)

    async def test_g7_el_reintento_a_mano_da_el_error_de_siempre(self):
        """
        Given el caso del Kind (G1)
        When el organizador genera a mano con emparejamientos
        Then el error de siempre (un 400 con el aviso), y ningún partido
        """
        torneo = await _scratch_con_dos_mujeres()

        with pytest.raises(TeeColorNotFoundError):
            await torneo.generador().execute(
                GenerateMatchesRequestDTO(
                    round_id=torneo.ronda_id.value, manual_pairings=_emparejamientos(torneo)
                ),
                torneo.organizador,
            )

        assert await torneo.partidos() == []
        bloqueo = (await torneo.ronda()).match_generation_block
        assert {p.tee_color for p in bloqueo.players} == {"YELLOW", "GREEN"}

    async def test_g8_regenerar_sin_barra_no_toca_los_partidos(self):
        """
        Given partidos generados con rojas para las mujeres (R2), y luego se quita
        When se regeneran (el script, que reabre la sesión)
        Then el error de siempre, y los partidos siguen como estaban
        """
        torneo = await _scratch_con_dos_mujeres()
        campo = await _campo(torneo)
        await torneo.uow.barras_por_campo.fijar_del_campo(
            torneo.comp_id, campo, Gender.FEMALE, TeeColor.RED
        )
        await torneo.generador().execute(
            GenerateMatchesRequestDTO(round_id=torneo.ronda_id.value), torneo.organizador
        )
        antes = {p.id for p in await torneo.partidos()}
        await torneo.uow.barras_por_campo.fijar_del_campo(
            torneo.comp_id, campo, Gender.FEMALE, None
        )

        with pytest.raises(TeeColorNotFoundError):
            await torneo.generador().execute(
                GenerateMatchesRequestDTO(round_id=torneo.ronda_id.value),
                torneo.organizador,
                allow_regeneration=True,
            )

        assert {p.id for p in await torneo.partidos()} == antes
