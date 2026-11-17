"""
Quién puede ver un campo (re-auditoría F-04).

La regla vivía en la ruta: un campo aprobado lo ve cualquiera; uno pendiente o
rechazado, solo un admin o quien lo propuso. Ahora la aplica el caso de uso, así
que cualquier otra entrada (un script, otra ruta) la cumple también.
"""

from uuid import uuid4

import pytest

from src.modules.golf_course.application.dtos.golf_course_dtos import (
    GetGolfCourseByIdRequestDTO,
)
from src.modules.golf_course.application.exceptions import (
    GolfCourseMissingError,
    GolfCourseViewForbiddenError,
)
from src.modules.golf_course.application.use_cases.get_golf_course_by_id_use_case import (
    GetGolfCourseByIdUseCase,
)
from src.modules.golf_course.domain.entities.golf_course import GolfCourse
from src.modules.golf_course.domain.entities.hole import Hole
from src.modules.golf_course.domain.entities.tee import Tee
from src.modules.golf_course.domain.value_objects.course_type import CourseType
from src.modules.golf_course.domain.value_objects.tee_color import TeeColor
from src.modules.golf_course.infrastructure.persistence.in_memory.in_memory_golf_course_repository import (
    InMemoryGolfCourseRepository,
)
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.country_code import CountryCode
from src.shared.domain.value_objects.gender import Gender

pytestmark = pytest.mark.asyncio

CREADOR = "11111111-2222-4333-8444-555555555555"
OTRO = "99999999-8888-4777-8666-555555555555"


class _Uow:
    def __init__(self) -> None:
        self.golf_courses = InMemoryGolfCourseRepository()

    async def __aenter__(self) -> "_Uow":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None


async def _campo(uow: _Uow, estado: str) -> GolfCourse:
    """Guarda un campo propuesto por CREADOR y lo deja en `estado`."""
    campo = GolfCourse.create(
        name="Campo de prueba",
        country_code=CountryCode("ES"),
        course_type=CourseType.STANDARD_18,
        creator_id=UserId(CREADOR),
        tees=[
            Tee(
                color=TeeColor.WHITE,
                gender=Gender.MALE,
                identifier="Blanco",
                course_rating=73.5,
                slope_rating=135,
            ),
            Tee(
                color=TeeColor.YELLOW,
                gender=Gender.MALE,
                identifier="Amarillo",
                course_rating=71.2,
                slope_rating=128,
            ),
        ],
        holes=[Hole(number=i, par=4, stroke_index=i) for i in range(1, 19)],
    )
    if estado == "APPROVED":
        campo.approve()
    elif estado == "REJECTED":
        campo.reject("Este campo no existe")
    await uow.golf_courses.save(campo)
    return campo


def _pide(campo: GolfCourse, quien: str, es_admin: bool = False) -> GetGolfCourseByIdRequestDTO:
    return GetGolfCourseByIdRequestDTO(
        golf_course_id=str(campo.id.value),
        requester_id=quien,
        requester_is_admin=es_admin,
    )


class TestCampoAprobado:
    async def test_given_an_approved_course_when_anyone_asks_then_they_see_it(self):
        uow = _Uow()
        campo = await _campo(uow, "APPROVED")

        respuesta = await GetGolfCourseByIdUseCase(uow).execute(_pide(campo, OTRO))

        assert respuesta.golf_course.approval_status == "APPROVED"


@pytest.mark.parametrize("estado", ["PENDING_APPROVAL", "REJECTED"])
class TestCampoSinAprobar:
    async def test_given_an_unapproved_course_when_another_player_asks_then_forbidden(self, estado):
        uow = _Uow()
        campo = await _campo(uow, estado)

        with pytest.raises(
            GolfCourseViewForbiddenError,
            match="^You don't have permission to view this golf course$",
        ):
            await GetGolfCourseByIdUseCase(uow).execute(_pide(campo, OTRO))

    async def test_given_an_unapproved_course_when_its_proposer_asks_then_they_see_it(self, estado):
        uow = _Uow()
        campo = await _campo(uow, estado)

        respuesta = await GetGolfCourseByIdUseCase(uow).execute(_pide(campo, CREADOR))

        assert respuesta.golf_course.approval_status == estado

    async def test_given_an_unapproved_course_when_an_admin_asks_then_they_see_it(self, estado):
        uow = _Uow()
        campo = await _campo(uow, estado)

        respuesta = await GetGolfCourseByIdUseCase(uow).execute(_pide(campo, OTRO, es_admin=True))

        assert respuesta.golf_course.approval_status == estado


class TestCampoQueNoEsta:
    async def test_given_no_course_when_asked_then_missing_and_not_a_value_error(self):
        with pytest.raises(GolfCourseMissingError) as error:
            await GetGolfCourseByIdUseCase(_Uow()).execute(
                GetGolfCourseByIdRequestDTO(golf_course_id=str(uuid4()), requester_id=OTRO)
            )

        # Ya no hereda de ValueError: la ruta no lo confunde con un 400
        assert not isinstance(error.value, ValueError)
