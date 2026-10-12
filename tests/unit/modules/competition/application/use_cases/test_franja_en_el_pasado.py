"""
Una franja cuya primera salida ya ha pasado (QA del 11 oct 2026, decidido con Agustín).

Se podía crear y colocar jugadores en ella, pero ya no admitía partidas: se
quedaban atrapados y fuera de la clasificación.

| Caso                                                 | Resultado                    |
|------------------------------------------------------|------------------------------|
| Crear con la primera salida pasada (hora del campo)  | FranjaEnElPasadoError        |
| Crear justo a su hora                                | FranjaEnElPasadoError        |
| Crear un minuto después de ahora                     | Se crea                      |
| Crear con el campo sin zona horaria                  | Se crea: no se sabe          |
| Cambiar la primera salida a una pasada               | FranjaEnElPasadoError        |
| Moverla a un día pasado                              | FranjaEnElPasadoError        |
| Ya empezada, cambiar solo la última salida           | Se cambia, como hasta ahora  |
| Moverla a un campo de otra zona, ya pasada allí      | FranjaEnElPasadoError        |
| Moverla a un campo de otra zona, aún por llegar allí | Se mueve (cuenta su zona)    |
| Una hora que no existe por el cambio de hora         | FranjaInvalidaError (CodeRabbit) |
| La de después del cambio de hora                     | Se crea                      |
| Una salida que no es la primera cae en la hora que no existe (QA 2) | FranjaInvalidaError |
| Todas antes del salto (01:00-01:50)                  | Se crea                      |
| La última justo en el salto (01:00-02:00)            | FranjaInvalidaError          |
| Sin zona, salidas en el salto                        | Se crea: no se sabe          |
| Cambiarla para que una salida caiga en el salto      | FranjaInvalidaError          |
| Moverla al día del cambio con salidas en el salto    | FranjaInvalidaError          |
"""

from datetime import UTC, date, datetime

import pytest

from src.modules.competition.application.dto.round_match_dto import (
    CreateRoundRequestDTO,
    UpdateRoundRequestDTO,
)
from src.modules.competition.application.exceptions import (
    FranjaEnElPasadoError,
    FranjaInvalidaError,
)
from src.modules.competition.application.use_cases.create_round_use_case import (
    CreateRoundUseCase,
)
from src.modules.competition.application.use_cases.update_round_use_case import (
    UpdateRoundUseCase,
)
from src.modules.competition.domain.entities.competition_golf_course import (
    CompetitionGolfCourse,
)
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from tests.unit.modules.competition.application.use_cases.test_franjas_use_cases import (
    SABADO,
    _Escenario,
    _hoja,
)

pytestmark = pytest.mark.asyncio

# El sábado a las 9:30 en Madrid (UTC+2)
NUEVE_Y_MEDIA = datetime(2030, 10, 12, 7, 30, tzinfo=UTC)
VIERNES = date(2030, 10, 11)


class _Zonas:
    def __init__(self, zonas):
        self._zonas = zonas

    async def for_course(self, campo):
        return self._zonas.get(campo)


class _ConReloj(_Escenario):
    def __init__(self, zona="Europe/Madrid"):
        super().__init__()
        self.ahora = NUEVE_Y_MEDIA
        self.zonas = {self.campo: zona}

    async def crear(self, hoja=None, sesion="MORNING", dia=SABADO, formato=None, campo=None):
        return await CreateRoundUseCase(
            self.uow, zonas=_Zonas(self.zonas), reloj=lambda: self.ahora
        ).execute(
            CreateRoundRequestDTO(
                competition_id=self.competicion.id.value,
                golf_course_id=(campo or self.campo).value,
                round_date=dia,
                session_type=sesion,
                match_format=formato,
                tee_sheet=hoja,
            ),
            self.creador,
        )

    async def cambiar(self, round_id, **campos):
        return await UpdateRoundUseCase(
            self.uow, zonas=_Zonas(self.zonas), reloj=lambda: self.ahora
        ).execute(UpdateRoundRequestDTO(round_id=round_id, **campos), self.creador)


async def _torneo(e, dias=(SABADO, SABADO)):
    competicion = await e.torneo()
    competicion._dates = type(competicion.dates)(*dias)
    async with e.uow:
        await e.uow.competitions.update(competicion)


async def test_creating_with_the_first_tee_time_gone():
    e = _ConReloj()
    await _torneo(e)

    with pytest.raises(FranjaEnElPasadoError):
        await e.crear(_hoja("09:00", "12:00"))


async def test_it_is_still_a_tee_window_error():
    assert issubclass(FranjaEnElPasadoError, FranjaInvalidaError)


async def test_creating_right_at_its_time():
    e = _ConReloj()
    await _torneo(e)

    with pytest.raises(FranjaEnElPasadoError):
        await e.crear(_hoja("09:30", "12:00"))


async def test_creating_a_minute_ahead():
    e = _ConReloj()
    await _torneo(e)

    creada = await e.crear(_hoja("09:31", "12:00"))

    assert creada.id


async def test_creating_without_a_time_zone():
    e = _ConReloj(zona=None)
    await _torneo(e)

    creada = await e.crear(_hoja("09:00", "12:00"))

    assert creada.id


async def test_moving_the_first_tee_time_to_one_gone():
    e = _ConReloj()
    await _torneo(e)
    creada = await e.crear(_hoja("10:00", "12:00"))

    with pytest.raises(FranjaEnElPasadoError):
        await e.cambiar(creada.id, tee_sheet=_hoja("09:00", "12:00"))


async def test_moving_it_to_a_past_day():
    e = _ConReloj()
    await _torneo(e, (VIERNES, SABADO))
    creada = await e.crear(_hoja("10:00", "12:00"))

    with pytest.raises(FranjaEnElPasadoError):
        await e.cambiar(creada.id, round_date=VIERNES)


async def test_already_started_changing_only_the_last_tee_time():
    e = _ConReloj()
    await _torneo(e)
    e.ahora = datetime(2030, 10, 12, 6, 0, tzinfo=UTC)
    creada = await e.crear(_hoja("09:00", "12:00"))
    e.ahora = NUEVE_Y_MEDIA

    await e.cambiar(creada.id, tee_sheet=_hoja("09:00", "12:30"))

    assert (await e.sesion(creada.id)).hoja_de_salidas.ultima_salida.minute == 30


async def _con_canarias(e):
    """A las 10:30 de Madrid, una franja de las 10:45 y un campo en Canarias (una hora menos)."""
    await _torneo(e)
    e.ahora = datetime(2030, 10, 12, 8, 30, tzinfo=UTC)
    creada = await e.crear(_hoja("10:45", "12:00"))
    canarias = GolfCourseId.generate()
    e.zonas[canarias] = "Atlantic/Canary"
    e.competicion._golf_courses.append(
        CompetitionGolfCourse.create(
            competition_id=e.competicion.id, golf_course_id=canarias, display_order=2
        )
    )
    async with e.uow:
        await e.uow.competitions.update(e.competicion)
    return creada, canarias


async def test_moving_it_to_a_course_where_it_is_still_ahead():
    e = _ConReloj()
    creada, canarias = await _con_canarias(e)

    # Las 9:45 de Canarias son las 10:45 de Madrid: aún no ha llegado
    await e.cambiar(creada.id, golf_course_id=canarias.value, tee_sheet=_hoja("09:45", "12:00"))

    assert (await e.sesion(creada.id)).golf_course_id == canarias


async def test_moving_it_to_a_course_where_it_is_already_gone():
    e = _ConReloj()
    creada, canarias = await _con_canarias(e)

    with pytest.raises(FranjaEnElPasadoError):
        await e.cambiar(creada.id, golf_course_id=canarias.value, tee_sheet=_hoja("09:15", "12:00"))


# El 31 de marzo de 2030 Madrid pasa de las 2:00 a las 3:00
CAMBIO_DE_HORA = date(2030, 3, 31)


async def test_a_first_tee_time_that_does_not_exist_that_day():
    e = _ConReloj()
    await _torneo(e, (CAMBIO_DE_HORA, CAMBIO_DE_HORA))
    e.ahora = datetime(2030, 3, 30, 12, 0, tzinfo=UTC)

    with pytest.raises(FranjaInvalidaError, match="no existe"):
        await e.crear(_hoja("02:30", "12:00"), dia=CAMBIO_DE_HORA)


async def test_the_first_tee_time_right_after_the_change():
    e = _ConReloj()
    await _torneo(e, (CAMBIO_DE_HORA, CAMBIO_DE_HORA))
    e.ahora = datetime(2030, 3, 30, 12, 0, tzinfo=UTC)

    creada = await e.crear(_hoja("03:00", "12:00"), dia=CAMBIO_DE_HORA)

    assert creada.id


async def test_a_later_tee_time_that_does_not_exist_that_day():
    e = _ConReloj()
    await _torneo(e, (CAMBIO_DE_HORA, CAMBIO_DE_HORA))
    e.ahora = datetime(2030, 3, 30, 12, 0, tzinfo=UTC)

    with pytest.raises(FranjaInvalidaError, match="no existe"):
        await e.crear(_hoja("01:50", "04:00"), dia=CAMBIO_DE_HORA)


async def test_every_tee_time_before_the_change():
    e = _ConReloj()
    await _torneo(e, (CAMBIO_DE_HORA, CAMBIO_DE_HORA))
    e.ahora = datetime(2030, 3, 30, 12, 0, tzinfo=UTC)

    creada = await e.crear(_hoja("01:00", "01:50"), dia=CAMBIO_DE_HORA)

    assert creada.id


async def test_the_last_tee_time_right_on_the_change():
    e = _ConReloj()
    await _torneo(e, (CAMBIO_DE_HORA, CAMBIO_DE_HORA))
    e.ahora = datetime(2030, 3, 30, 12, 0, tzinfo=UTC)

    with pytest.raises(FranjaInvalidaError, match="no existe"):
        await e.crear(_hoja("01:00", "02:00"), dia=CAMBIO_DE_HORA)


async def test_tee_times_on_the_change_without_a_time_zone():
    e = _ConReloj(zona=None)
    await _torneo(e, (CAMBIO_DE_HORA, CAMBIO_DE_HORA))
    e.ahora = datetime(2030, 3, 30, 12, 0, tzinfo=UTC)

    creada = await e.crear(_hoja("01:50", "04:00"), dia=CAMBIO_DE_HORA)

    assert creada.id


async def test_changing_it_so_a_tee_time_falls_on_the_change():
    e = _ConReloj()
    await _torneo(e, (CAMBIO_DE_HORA, CAMBIO_DE_HORA))
    e.ahora = datetime(2030, 3, 30, 12, 0, tzinfo=UTC)
    creada = await e.crear(_hoja("01:00", "01:50"), dia=CAMBIO_DE_HORA)

    with pytest.raises(FranjaInvalidaError, match="no existe"):
        await e.cambiar(creada.id, tee_sheet=_hoja("01:00", "04:00"))


async def test_moving_it_to_the_day_of_the_change():
    e = _ConReloj()
    await _torneo(e, (date(2030, 3, 30), CAMBIO_DE_HORA))
    e.ahora = datetime(2030, 3, 29, 12, 0, tzinfo=UTC)
    creada = await e.crear(_hoja("01:50", "04:00"), dia=date(2030, 3, 30))

    with pytest.raises(FranjaInvalidaError, match="no existe"):
        await e.cambiar(creada.id, round_date=CAMBIO_DE_HORA)
