"""
El cambio propio de barras de una inscripción en un campo (R1, 20 nov 2026).

`PUT /enrollments/{id}/courses/{golf_course_id}/tee`. Mismos permisos y plazos
que el cambio de la barra general (#912):

| Caso                                                  | Resultado                                 |
|-------------------------------------------------------|-------------------------------------------|
| La jugadora fija azules en el segundo campo           | Guardado; su partido de allí, en azules   |
| Su partido del otro campo                             | No cambia                                 |
| El rival de su partido                                | Conserva su foto                          |
| null                                                  | Quita el cambio: vuelve a la general       |
| Una barra que ESE campo no tiene para ella            | 422 TEE_NOT_AVAILABLE                     |
| Un campo que no es de la competición                  | 404 COURSE_NOT_IN_COMPETITION             |
| Otro jugador, el capitán del otro equipo              | 403                                       |
| En curso: ella 403; su capitana, sí                   |                                           |
| Terminada                                             | 409 TEE_CHANGE_CLOSED                     |
| Inscripción no aprobada                               | 409 ENROLLMENT_NOT_APPROVED               |
| Cambiar luego la general no toca ese campo            | R1 gana                                   |
| El log                                                | ids, sin nombres                          |
"""

import logging
from decimal import Decimal
from uuid import uuid4

import pytest

from src.modules.competition.application.dto.enrollment_dto import (
    ChangeEnrollmentCourseTeeRequestDTO,
)
from src.modules.competition.application.exceptions import (
    CourseNotInCompetitionError,
    EnrollmentNotApprovedError,
    NotCompetitionCreatorError,
    TeeChangeClosedError,
    TeeNotAvailableError,
)
from src.modules.competition.application.use_cases.change_enrollment_course_tee_use_case import (
    ChangeEnrollmentCourseTeeUseCase,
)
from src.modules.competition.domain.value_objects.enrollment_status import EnrollmentStatus
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.golf_course.domain.value_objects.tee_color import TeeColor
from src.shared.domain.value_objects.gender import Gender
from tests.unit.modules.competition.application.use_cases.test_change_enrollment_tee_use_case import (
    ALDEAMAYOR,
    _Mundo,
)

pytestmark = pytest.mark.asyncio

SIN_ROJAS = [(TeeColor.YELLOW, Gender.MALE), (TeeColor.BLUE, Gender.FEMALE)]


async def _fijar(mundo, campo, color, quien=None, is_admin=False, inscripcion=None):
    return await ChangeEnrollmentCourseTeeUseCase(
        mundo.uow, golf_course_repository=mundo.campos, user_repository=mundo.usuarios
    ).execute(
        ChangeEnrollmentCourseTeeRequestDTO(
            enrollment_id=(inscripcion or mundo.inscripcion).id.value,
            golf_course_id=campo.value,
            tee_color=color,
        ),
        quien or mundo.jugadora,
        is_admin=is_admin,
    )


async def _propia(mundo, campo):
    return (await mundo.uow.barras_por_campo.del_campo(mundo.competition_id, campo)).propias.get(
        mundo.jugadora
    )


async def _dos_campos():
    mundo = await _Mundo().montar(campos=(ALDEAMAYOR, SIN_ROJAS))
    return mundo, *list(mundo.campos.por_id)


class TestElCambio:
    async def test_course_tee_by_the_player_is_saved_and_rebuilds_that_course_only(self):
        """
        Given la jugadora con un individual programado en cada campo
        When fija azules en el segundo
        Then se guarda su cambio, su partido del segundo campo sale en azules y el del
            primero no cambia
        """
        mundo, _, segundo = await _dos_campos()
        en_el_primero = await mundo.partido([mundo.jugadora], [mundo.otro], campo=0)
        en_el_segundo = await mundo.partido([mundo.jugadora], [mundo.otro], campo=1)

        respuesta = await _fijar(mundo, segundo, TeeColor.BLUE)

        assert respuesta.tee_color == "BLUE"
        assert await _propia(mundo, segundo) == TeeColor.BLUE
        ella = (await mundo.el_partido(en_el_segundo)).find_player(mundo.jugadora)
        assert (ella.tee_color, ella.tee_gender) == (TeeColor.BLUE, Gender.FEMALE)
        assert (await mundo.el_partido(en_el_primero)).find_player(
            mundo.jugadora
        ).tee_color == TeeColor.YELLOW

    async def test_course_tee_keeps_the_rival_snapshot(self):
        """
        Given su individual programado en el segundo campo
        When fija azules allí
        Then el rival conserva su barra y su índice guardados
        """
        mundo, _, segundo = await _dos_campos()
        partido = await mundo.partido([mundo.jugadora], [mundo.otro], campo=1)

        await _fijar(mundo, segundo, TeeColor.BLUE)

        rival = (await mundo.el_partido(partido)).find_player(mundo.otro)
        assert (rival.tee_color, rival.player_handicap) == (TeeColor.YELLOW, Decimal("18.0"))

    async def test_course_tee_null_removes_her_change(self):
        """
        Given su cambio propio a azules en el segundo campo
        When lo quita (null)
        Then ya no hay cambio propio allí
        """
        mundo, _, segundo = await _dos_campos()
        await _fijar(mundo, segundo, TeeColor.BLUE)

        respuesta = await _fijar(mundo, segundo, None)

        assert respuesta.tee_color is None
        assert await _propia(mundo, segundo) is None

    async def test_course_tee_not_available_on_that_course_is_rejected(self):
        """
        Given el segundo campo sin rojas de mujer (el primero sí las tiene)
        When fija rojas en el segundo
        Then 422: cuenta ESE campo
        """
        mundo, _, segundo = await _dos_campos()

        with pytest.raises(TeeNotAvailableError):
            await _fijar(mundo, segundo, TeeColor.RED)

        assert await _propia(mundo, segundo) is None

    async def test_course_tee_on_a_course_of_another_competition_is_not_found(self):
        """
        Given un campo que no es de la competición
        When se fija en él
        Then 404 COURSE_NOT_IN_COMPETITION
        """
        mundo, _, _ = await _dos_campos()

        with pytest.raises(CourseNotInCompetitionError) as error:
            await _fijar(mundo, GolfCourseId(uuid4()), TeeColor.BLUE)

        assert error.value.error_code == "COURSE_NOT_IN_COMPETITION"

    async def test_course_tee_then_a_general_change_leaves_that_course_alone(self):
        """
        Given su cambio propio a azules en el segundo campo y un partido allí
        When cambia su barra general a rojas
        Then en el segundo campo sigue en azules: su cambio propio gana
        """
        mundo, _, segundo = await _dos_campos()
        partido = await mundo.partido([mundo.jugadora], [mundo.otro], campo=1)
        await _fijar(mundo, segundo, TeeColor.BLUE)

        await mundo.cambiar(TeeColor.RED)

        assert (await mundo.el_partido(partido)).find_player(mundo.jugadora).tee_color == (
            TeeColor.BLUE
        )

    async def test_course_tee_logs_who_what_and_where(self, caplog):
        """
        Given la jugadora
        When fija azules en el segundo campo
        Then queda en el log quién, la inscripción, el campo y el cambio, con ids
        """
        mundo, _, segundo = await _dos_campos()

        with caplog.at_level(logging.INFO):
            await _fijar(mundo, segundo, TeeColor.BLUE)

        [registro] = [r for r in caplog.records if "Course tee change" in r.getMessage()]
        mensaje = registro.getMessage()
        for trozo in (
            str(mundo.inscripcion.id.value),
            str(segundo.value),
            str(mundo.jugadora.value),
            "as=player",
            "to=BLUE",
        ):
            assert trozo in mensaje


class TestQuien:
    @pytest.mark.parametrize("quien", ["otro", "capitan_b"])
    async def test_course_tee_by_another_player_or_the_other_captain_is_forbidden(self, quien):
        """
        Given equipos formados
        When otro jugador o el capitán del otro equipo fijan su barra en un campo
        Then 403
        """
        mundo = await (await _Mundo().montar(campos=(ALDEAMAYOR, SIN_ROJAS))).con_equipos()
        segundo = list(mundo.campos.por_id)[1]

        with pytest.raises(NotCompetitionCreatorError):
            await _fijar(mundo, segundo, TeeColor.BLUE, quien=getattr(mundo, quien))

    async def test_course_tee_in_progress_by_her_is_forbidden_by_her_captain_allowed(self):
        """
        Given la competición en curso
        When ella fija su barra en un campo, y luego su capitana
        Then a ella 403, a la capitana sí
        """
        mundo = await (await _Mundo().montar(campos=(ALDEAMAYOR, SIN_ROJAS))).con_equipos()
        segundo = list(mundo.campos.por_id)[1]
        await mundo.empezar()

        with pytest.raises(NotCompetitionCreatorError):
            await _fijar(mundo, segundo, TeeColor.BLUE)
        await _fijar(mundo, segundo, TeeColor.BLUE, quien=mundo.capitana)

        assert await _propia(mundo, segundo) == TeeColor.BLUE

    async def test_course_tee_once_finished_is_closed(self):
        """
        Given una competición terminada
        When el organizador fija una barra en un campo
        Then 409 TEE_CHANGE_CLOSED
        """
        mundo = await (await _Mundo().montar(campos=(ALDEAMAYOR, SIN_ROJAS))).con_equipos()
        segundo = list(mundo.campos.por_id)[1]
        await mundo.empezar()
        await mundo.terminar()

        with pytest.raises(TeeChangeClosedError):
            await _fijar(mundo, segundo, TeeColor.BLUE, quien=mundo.organizador)

    async def test_course_tee_of_an_enrollment_not_approved_is_rejected(self):
        """
        Given una inscripción retirada
        When el organizador le fija una barra en un campo
        Then 409 ENROLLMENT_NOT_APPROVED
        """
        mundo, _, segundo = await _dos_campos()
        retirada = await mundo.inscripcion_en(EnrollmentStatus.WITHDRAWN)

        with pytest.raises(EnrollmentNotApprovedError):
            await _fijar(
                mundo, segundo, TeeColor.BLUE, quien=mundo.organizador, inscripcion=retirada
            )
