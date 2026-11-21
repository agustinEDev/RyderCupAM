"""
OTHER no se elige (barras por campo, tabla del 21 nov 2026, C).

OTHER cubre las salidas del campo cuyo nombre no es un color: sirve para guardar
el campo tal cual, pero nadie sabe qué barra es al elegirla.

| Caso                                                    | Resultado                       |
|---------------------------------------------------------|---------------------------------|
| C11 Inscribirse con OTHER                               | TeeNotSelectableError, sin alta |
| C11 Cambiar la barra general a OTHER                    | TeeNotSelectableError, sin cambio |
| C12 Cambio propio a OTHER en un campo que la tiene      | TeeNotSelectableError, sin cambio |
| C12 La del campo para un género a OTHER, aunque la tenga | TeeNotSelectableError, sin cambio |
| C13 Los demás colores                                   | como hoy                        |
| Opciones de GET /enrollments/{id}/tees                  | nunca OTHER                     |
| Todas son TEE_NOT_AVAILABLE                             | subclase de TeeNotAvailableError |
"""

from datetime import timedelta
from uuid import uuid4

import pytest

from src.modules.competition.application.dto.competition_dto import (
    SetCompetitionCourseTeeRequestDTO,
)
from src.modules.competition.application.dto.enrollment_dto import (
    ChangeEnrollmentCourseTeeRequestDTO,
    RequestEnrollmentRequestDTO,
)
from src.modules.competition.application.exceptions import (
    TeeNotAvailableError,
    TeeNotSelectableError,
)
from src.modules.competition.application.use_cases.change_enrollment_course_tee_use_case import (
    ChangeEnrollmentCourseTeeUseCase,
)
from src.modules.competition.application.use_cases.get_enrollment_tees_use_case import (
    GetEnrollmentTeesUseCase,
)
from src.modules.competition.application.use_cases.request_enrollment_use_case import (
    RequestEnrollmentUseCase,
)
from src.modules.competition.application.use_cases.set_competition_course_tee_use_case import (
    SetCompetitionCourseTeeUseCase,
)
from src.modules.competition.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)
from src.modules.golf_course.domain.value_objects.tee_color import TeeColor
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.gender import Gender
from tests.unit.modules.competition.application.use_cases.test_change_enrollment_tee_use_case import (
    ALDEAMAYOR,
    _Mundo,
)
from tests.unit.modules.competition.application.use_cases.test_request_enrollment_refusals import (
    _CON_GENERO,
    _hoy,
    _publica,
)

pytestmark = pytest.mark.asyncio

# Aldeamayor con unas OTHER valoradas para hombre y para mujer
CON_OTHER = [*ALDEAMAYOR, (TeeColor.OTHER, Gender.FEMALE), (TeeColor.OTHER, Gender.MALE)]


def test_tee_not_selectable_is_tee_not_available():
    """
    Given el error de OTHER
    When se mira su código
    Then es TEE_NOT_AVAILABLE, como el resto de barras que no valen
    """
    assert issubclass(TeeNotSelectableError, TeeNotAvailableError)
    assert TeeNotSelectableError.error_code == "TEE_NOT_AVAILABLE"


class TestInscribirse:
    async def _apuntarse(self, color):
        uow = InMemoryUnitOfWork()
        competicion = await _publica(uow, empieza=_hoy() + timedelta(days=3))
        quien = uuid4()
        respuesta = await RequestEnrollmentUseCase(uow, _CON_GENERO).execute(
            RequestEnrollmentRequestDTO(
                competition_id=competicion.id.value, user_id=quien, tee_color=color
            )
        )
        return uow, competicion, quien, respuesta

    async def test_enrolling_with_other_is_refused_and_nothing_is_saved(self):
        """
        Given una competición pública abierta
        When alguien se apunta con barra OTHER
        Then TeeNotSelectableError, y no queda inscrito
        """
        uow = InMemoryUnitOfWork()
        competicion = await _publica(uow, empieza=_hoy() + timedelta(days=3))
        quien = uuid4()

        with pytest.raises(TeeNotSelectableError):
            await RequestEnrollmentUseCase(uow, _CON_GENERO).execute(
                RequestEnrollmentRequestDTO(
                    competition_id=competicion.id.value, user_id=quien, tee_color="OTHER"
                )
            )
        async with uow:
            assert (
                await uow.enrollments.find_by_user_and_competition(UserId(quien), competicion.id)
                is None
            )

    @pytest.mark.parametrize("color", ["BLUE", None])
    async def test_enrolling_with_any_other_tee_works_as_today(self, color):
        """
        Given una competición pública abierta
        When alguien se apunta con azules o sin barra
        Then entra, con esa barra
        """
        *_, respuesta = await self._apuntarse(color)

        assert respuesta.status == "APPROVED"


class TestBarraGeneral:
    async def test_changing_the_general_tee_to_other_is_refused(self):
        """
        Given la jugadora inscrita, en un campo que tiene OTHER para mujer
        When cambia su barra general a OTHER
        Then TeeNotSelectableError, y su barra sigue sin elegir
        """
        mundo = await _Mundo().montar(campos=(CON_OTHER,))

        with pytest.raises(TeeNotSelectableError):
            await mundo.cambiar(TeeColor.OTHER)
        assert await mundo.barras_guardadas() is None

    async def test_changing_the_general_tee_to_blue_works_as_today(self):
        """
        Given la jugadora inscrita
        When cambia su barra general a azules
        Then quedan guardadas
        """
        mundo = await _Mundo().montar(campos=(CON_OTHER,))

        await mundo.cambiar(TeeColor.BLUE)

        assert await mundo.barras_guardadas() == TeeColor.BLUE


class TestEnUnCampo:
    async def _propio(self, mundo, color):
        (campo,) = list(mundo.campos.por_id)
        return await ChangeEnrollmentCourseTeeUseCase(
            mundo.uow, golf_course_repository=mundo.campos, user_repository=mundo.usuarios
        ).execute(
            ChangeEnrollmentCourseTeeRequestDTO(
                enrollment_id=mundo.inscripcion.id.value,
                golf_course_id=campo.value,
                tee_color=color,
            ),
            mundo.jugadora,
        )

    async def _del_campo(self, mundo, color):
        (campo,) = list(mundo.campos.por_id)
        return await SetCompetitionCourseTeeUseCase(
            mundo.uow, golf_course_repository=mundo.campos, user_repository=mundo.usuarios
        ).execute(
            SetCompetitionCourseTeeRequestDTO(
                competition_id=mundo.competition_id.value,
                golf_course_id=campo.value,
                gender=Gender.FEMALE,
                tee_color=color,
            ),
            mundo.organizador,
        )

    async def _fijado(self, mundo):
        (campo,) = list(mundo.campos.por_id)
        return await mundo.uow.barras_por_campo.del_campo(mundo.competition_id, campo)

    async def test_own_course_tee_other_is_refused_even_if_the_course_has_it(self):
        """
        Given un campo con OTHER valoradas para mujer
        When la jugadora fija OTHER como cambio propio allí
        Then TeeNotSelectableError, y no queda cambio propio
        """
        mundo = await _Mundo().montar(campos=(CON_OTHER,))

        with pytest.raises(TeeNotSelectableError):
            await self._propio(mundo, TeeColor.OTHER)
        assert (await self._fijado(mundo)).propias == {}

    async def test_course_tee_for_a_gender_other_is_refused_even_if_the_course_has_it(self):
        """
        Given un campo con OTHER valoradas para mujer
        When el organizador fija OTHER para las mujeres allí
        Then TeeNotSelectableError, y no queda nada fijado
        """
        mundo = await _Mundo().montar(campos=(CON_OTHER,))

        with pytest.raises(TeeNotSelectableError):
            await self._del_campo(mundo, TeeColor.OTHER)
        assert (await self._fijado(mundo)).por_genero == {}

    async def test_blue_in_a_course_works_as_today(self):
        """
        Given un campo con azules de mujer
        When la jugadora fija azules como cambio propio y el organizador azules para ellas
        Then quedan fijadas las dos
        """
        mundo = await _Mundo().montar(campos=(CON_OTHER,))

        await self._propio(mundo, TeeColor.BLUE)
        await self._del_campo(mundo, TeeColor.BLUE)

        fijado = await self._fijado(mundo)
        assert fijado.propias == {mundo.jugadora: TeeColor.BLUE}
        assert fijado.por_genero == {Gender.FEMALE: TeeColor.BLUE}


class TestOpciones:
    async def test_options_never_offer_other_even_if_the_course_has_it(self):
        """
        Given un campo con OTHER valoradas para mujer, y la competición abierta
        When la jugadora pide sus barras
        Then sus opciones no traen OTHER: el cambio la rechazaría (decidido el 21 nov)
        """
        mundo = await _Mundo().montar(campos=(CON_OTHER,))

        respuesta = await GetEnrollmentTeesUseCase(
            mundo.uow, golf_course_repository=mundo.campos, user_repository=mundo.usuarios
        ).execute(mundo.inscripcion.id.value, mundo.jugadora)

        assert respuesta.courses[0].options == ["RED", "BLUE"]
