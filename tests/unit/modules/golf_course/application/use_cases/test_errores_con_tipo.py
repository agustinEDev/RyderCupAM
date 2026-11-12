"""
Los casos de uso de campos lanzan errores con tipo, con el texto de siempre (G10).

Antes lanzaban `ValueError` con un texto, y la ruta elegía el código HTTP leyendo
ese texto («not found» → 404, «permission» → 403). Ahora el tipo dice qué pasó y
el texto, que es el `detail` que ve el front, no cambia. Los tres heredan de
ValueError, así que cualquier `except ValueError` los sigue capturando.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.modules.golf_course.application.dtos.golf_course_dtos import (
    ApproveGolfCourseRequestDTO,
    ApproveUpdateGolfCourseRequestDTO,
    GetGolfCourseByIdRequestDTO,
    RejectGolfCourseRequestDTO,
    RejectUpdateGolfCourseRequestDTO,
)
from src.modules.golf_course.application.exceptions import (
    CountryNotFoundError,
    GolfCourseEditForbiddenError,
    GolfCourseMissingError,
)
from src.modules.golf_course.application.use_cases.approve_golf_course_use_case import (
    ApproveGolfCourseUseCase,
)
from src.modules.golf_course.application.use_cases.approve_update_golf_course_use_case import (
    ApproveUpdateGolfCourseUseCase,
)
from src.modules.golf_course.application.use_cases.create_direct_golf_course_use_case import (
    CreateDirectGolfCourseUseCase,
)
from src.modules.golf_course.application.use_cases.get_golf_course_by_id_use_case import (
    GetGolfCourseByIdUseCase,
)
from src.modules.golf_course.application.use_cases.reject_golf_course_use_case import (
    RejectGolfCourseUseCase,
)
from src.modules.golf_course.application.use_cases.reject_update_golf_course_use_case import (
    RejectUpdateGolfCourseUseCase,
)
from src.modules.golf_course.application.use_cases.request_golf_course_use_case import (
    RequestGolfCourseUseCase,
)
from src.modules.golf_course.application.use_cases.update_golf_course_use_case import (
    UpdateGolfCourseUseCase,
)
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.user.domain.value_objects.user_id import UserId

pytestmark = pytest.mark.asyncio

CAMPO = "6f1d2c3b-4a5e-4f60-8a7b-9c0d1e2f3a4b"
ORIGINAL = "0a1b2c3d-4e5f-4a6b-8c7d-8e9f0a1b2c3d"
CREADOR = "11111111-2222-4333-8444-555555555555"
OTRO = "99999999-8888-4777-8666-555555555555"


def _uow(campo=None, pais=None):
    """Unidad de trabajo falsa: devuelve `campo` al buscar un campo y `pais` al buscar un país."""
    uow = AsyncMock()
    uow.__aenter__ = AsyncMock(return_value=uow)
    uow.__aexit__ = AsyncMock(return_value=False)
    uow.golf_courses = AsyncMock()
    uow.golf_courses.find_by_id = AsyncMock(return_value=campo)
    uow.countries = AsyncMock()
    uow.countries.find_by_code = AsyncMock(return_value=pais)
    return uow


def _peticion_de_campo():
    """Lo que leen los casos de uso de crear antes de buscar el país."""
    return MagicMock(country_code="ZZ")


class TestCampoQueNoEsta:
    """GolfCourseMissingError con el texto de siempre."""

    async def test_ver_un_campo_que_no_existe(self):
        caso = GetGolfCourseByIdUseCase(_uow())
        with pytest.raises(GolfCourseMissingError) as error:
            await caso.execute(GetGolfCourseByIdRequestDTO(golf_course_id=CAMPO))
        assert str(error.value) == f"Golf course not found: {CAMPO}"

    async def test_aprobar_un_campo_que_no_existe(self):
        caso = ApproveGolfCourseUseCase(_uow())
        with pytest.raises(GolfCourseMissingError) as error:
            await caso.execute(ApproveGolfCourseRequestDTO(golf_course_id=CAMPO))
        assert str(error.value) == f"Golf course not found: {CAMPO}"

    async def test_rechazar_un_campo_que_no_existe(self):
        caso = RejectGolfCourseUseCase(_uow())
        peticion = RejectGolfCourseRequestDTO(golf_course_id=CAMPO, reason="Datos incompletos")
        with pytest.raises(GolfCourseMissingError) as error:
            await caso.execute(peticion)
        assert str(error.value) == f"Golf course not found: {CAMPO}"

    async def test_editar_un_campo_que_no_existe(self):
        caso = UpdateGolfCourseUseCase(_uow())
        with pytest.raises(GolfCourseMissingError) as error:
            await caso.execute(
                golf_course_id=GolfCourseId(CAMPO),
                request=_peticion_de_campo(),
                user_id=UserId(CREADOR),
                is_admin=True,
            )
        assert str(error.value) == f"Golf course with ID {CAMPO} not found"

    @pytest.mark.parametrize(
        ("caso_de_uso", "peticion"),
        [
            (ApproveUpdateGolfCourseUseCase, ApproveUpdateGolfCourseRequestDTO),
            (RejectUpdateGolfCourseUseCase, RejectUpdateGolfCourseRequestDTO),
        ],
    )
    async def test_resolver_una_propuesta_que_no_existe(self, caso_de_uso, peticion):
        caso = caso_de_uso(_uow())
        with pytest.raises(GolfCourseMissingError) as error:
            await caso.execute(peticion(clone_id=CAMPO))
        assert str(error.value) == f"Golf course clone with ID {CAMPO} not found"

    @pytest.mark.parametrize(
        ("caso_de_uso", "peticion"),
        [
            (ApproveUpdateGolfCourseUseCase, ApproveUpdateGolfCourseRequestDTO),
            (RejectUpdateGolfCourseUseCase, RejectUpdateGolfCourseRequestDTO),
        ],
    )
    async def test_resolver_una_propuesta_cuyo_original_falta(self, caso_de_uso, peticion):
        clon = MagicMock(original_golf_course_id=GolfCourseId(ORIGINAL))
        uow = _uow()
        uow.golf_courses.find_by_id = AsyncMock(side_effect=[clon, None])
        caso = caso_de_uso(uow)
        with pytest.raises(GolfCourseMissingError) as error:
            await caso.execute(peticion(clone_id=CAMPO))
        assert str(error.value) == f"Original golf course {ORIGINAL} not found"

    @pytest.mark.parametrize(
        ("caso_de_uso", "peticion"),
        [
            (ApproveUpdateGolfCourseUseCase, ApproveUpdateGolfCourseRequestDTO),
            (RejectUpdateGolfCourseUseCase, RejectUpdateGolfCourseRequestDTO),
        ],
    )
    async def test_lo_que_no_es_una_propuesta_sigue_siendo_un_valueerror_sin_tipo(
        self, caso_de_uso, peticion
    ):
        """«No es un clon» no es «no está»: la ruta lo deja en 400 (G8)."""
        caso = caso_de_uso(_uow(campo=MagicMock(original_golf_course_id=None)))
        with pytest.raises(ValueError, match="is not a clone") as error:
            await caso.execute(peticion(clone_id=CAMPO))
        assert not isinstance(error.value, GolfCourseMissingError)


class TestEditarSinPermiso:
    """GolfCourseEditForbiddenError con el texto de siempre."""

    async def test_quien_no_es_creador_ni_admin(self):
        campo = MagicMock(creator_id=UserId(CREADOR))
        caso = UpdateGolfCourseUseCase(_uow(campo=campo))
        with pytest.raises(GolfCourseEditForbiddenError) as error:
            await caso.execute(
                golf_course_id=GolfCourseId(CAMPO),
                request=_peticion_de_campo(),
                user_id=UserId(OTRO),
                is_admin=False,
            )
        assert str(error.value) == (
            f"User {OTRO} does not have permission to edit golf course {CAMPO}"
        )


class TestPaisQueNoExiste:
    """CountryNotFoundError con el texto de siempre, al editar y al crear."""

    async def test_al_editar(self):
        caso = UpdateGolfCourseUseCase(_uow(campo=MagicMock(creator_id=UserId(CREADOR))))
        with pytest.raises(CountryNotFoundError) as error:
            await caso.execute(
                golf_course_id=GolfCourseId(CAMPO),
                request=_peticion_de_campo(),
                user_id=UserId(CREADOR),
                is_admin=False,
            )
        assert str(error.value) == "Country with code 'ZZ' not found"

    @pytest.mark.parametrize(
        "caso_de_uso", [RequestGolfCourseUseCase, CreateDirectGolfCourseUseCase]
    )
    async def test_al_crear(self, caso_de_uso):
        caso = caso_de_uso(_uow())
        with pytest.raises(CountryNotFoundError) as error:
            await caso.execute(_peticion_de_campo(), UserId(CREADOR))
        assert str(error.value) == "Country with code 'ZZ' not found"


def test_los_tres_siguen_siendo_valueerror():
    """Un `except ValueError` de cualquier sitio los sigue capturando como antes."""
    for clase in (GolfCourseMissingError, CountryNotFoundError, GolfCourseEditForbiddenError):
        assert issubclass(clase, ValueError)
