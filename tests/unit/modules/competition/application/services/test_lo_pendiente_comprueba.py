"""
Qué comprueba `LoPendiente` al rehacer, y con qué error (21 nov 2026).

En cada campo donde le queda algo por jugar, la barra que jugaría allí tiene que
valer. Si fallan varios, siempre el mismo error, con prioridad fija:

| Falla                                         | Error                                   |
|-----------------------------------------------|-----------------------------------------|
| La fijada en un campo (R1 o R2)               | TEE_NOT_AVAILABLE (TeeNotAvailableError) |
| Si no: la general, al cambiar la general       | TEE_NOT_ON_PENDING_COURSE               |
| Si no: la que quedaría, al quitar R1 o R2      | TEE_NOT_AVAILABLE, texto de quitarla    |

Cambiando la general, los campos donde juega la fijada ni se rehacen ni se miran.
"""

import pytest

from src.modules.competition.application.exceptions import (
    TeeNotAvailableError,
    TeeRemovalLeavesNoValidTeeError,
)
from src.modules.competition.application.services.lo_pendiente import LoPendiente
from src.modules.golf_course.domain.value_objects.tee_color import TeeColor
from src.shared.domain.value_objects.gender import Gender
from tests.unit.modules.competition.application.use_cases.test_change_enrollment_tee_use_case import (
    ALDEAMAYOR,
    _Mundo,
)

pytestmark = pytest.mark.asyncio


async def _dos_campos_que_fallan(play_mode, fijada_primero):
    """
    Dos campos con un partido suyo pendiente en cada uno: en uno su cambio propio
    en verdes (no valen), en el otro juega su general, amarillas (no hay de mujer).
    """
    mundo = await _Mundo().montar(campos=(ALDEAMAYOR, ALDEAMAYOR), play_mode=play_mode)
    campos = list(mundo.campos.por_id)
    con_fijada = campos[0] if fijada_primero else campos[1]
    for indice in (0, 1):
        await mundo.partido([mundo.jugadora], [mundo.otro], campo=indice)
    await mundo.uow.barras_por_campo.fijar_propia(mundo.inscripcion, con_fijada, TeeColor.GREEN)
    return mundo


async def _rehacer(mundo, cambia):
    async with mundo.uow:
        competicion = await mundo.uow.competitions.find_by_id(mundo.competition_id)
        pendiente = LoPendiente(mundo.uow, mundo.campos, mundo.usuarios, None, mundo._reloj)
        await pendiente.rehacer(
            competicion, mundo.jugadora, Gender.FEMALE, TeeColor.YELLOW, cambia=cambia
        )


@pytest.mark.parametrize("play_mode", ["HANDICAP", "SCRATCH"])
@pytest.mark.parametrize("fijada_primero", [True, False])
async def test_rehacer_with_the_set_tee_and_the_general_failing_prefers_the_set_tee(
    play_mode, fijada_primero
):
    """
    Given dos campos pendientes: en uno falla su cambio propio y en el otro su
        general (en cualquier orden de campos)
    When se rehace como al fijar la barra de un campo
    Then siempre TEE_NOT_AVAILABLE de la fijada, nunca el de quitarla
    """
    mundo = await _dos_campos_que_fallan(play_mode, fijada_primero)

    with pytest.raises(TeeNotAvailableError) as error:
        await _rehacer(mundo, "del_campo")

    assert type(error.value) is TeeNotAvailableError


@pytest.mark.parametrize("play_mode", ["HANDICAP", "SCRATCH"])
async def test_rehacer_only_the_remaining_tee_failing_is_the_removal_error(play_mode):
    """
    Given su partido pendiente en Aldeamayor, sin cambios, y amarillas de general
    When se rehace como al fijar la barra de un campo (quitarla)
    Then TEE_NOT_AVAILABLE con el texto de quitarla
    """
    mundo = await _Mundo().montar(play_mode=play_mode)
    await mundo.partido([mundo.jugadora], [mundo.otro])

    with pytest.raises(TeeRemovalLeavesNoValidTeeError):
        await _rehacer(mundo, "del_campo")
