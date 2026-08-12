"""
Tests de la ubicación a través de la capa de aplicación.

Comprueban que la ubicación viaja entera desde el DTO de entrada hasta el de
salida, y que un campo sin ubicación la devuelve como null y no como un objeto
con cinco nulos dentro.
"""

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.modules.golf_course.application.dtos.golf_course_dtos import (
    HoleDTO,
    LocationDTO,
    RequestGolfCourseRequestDTO,
    TeeDTO,
)
from src.modules.golf_course.application.mappers.golf_course_mapper import GolfCourseMapper
from src.modules.golf_course.application.use_cases.create_direct_golf_course_use_case import (
    CreateDirectGolfCourseUseCase,
)
from src.modules.golf_course.domain.value_objects.course_type import CourseType
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.entities.country import Country
from src.shared.domain.value_objects.country_code import CountryCode

DERIO_LOCATION = LocationDTO(
    latitude=43.29519,
    longitude=-2.87352,
    address="CALLE EREAGA BIDEA S/N, 48160, DERIO, VIZCAYA",
    city="DERIO",
    province="VIZCAYA",
)


def build_request(location: LocationDTO | None) -> RequestGolfCourseRequestDTO:
    """Construye un alta de campo válida con la ubicación dada."""
    return RequestGolfCourseRequestDTO(
        name="Real Club de Golf",
        country_code="ES",
        course_type=CourseType.STANDARD_18,
        tees=[
            TeeDTO(
                color="WHITE",
                tee_gender="MALE",
                course_rating=72.5,
                slope_rating=130,
            )
        ],
        holes=[
            HoleDTO(hole_number=i, par=4 if i <= 12 else 3, stroke_index=i) for i in range(1, 19)
        ],
        location=location,
    )


@pytest.fixture
def mock_uow():
    """Mock del Unit of Work con un país válido."""
    uow = AsyncMock()
    uow.__aenter__ = AsyncMock(return_value=uow)
    uow.commit = AsyncMock()

    async def aexit_side_effect(exc_type, exc, tb):
        if exc_type is None:
            await uow.commit()

    uow.__aexit__ = AsyncMock(side_effect=aexit_side_effect)
    uow.golf_courses = AsyncMock()
    uow.countries = AsyncMock()
    uow.countries.find_by_code.return_value = Country(
        code=CountryCode("ES"), name_en="Spain", name_es="España"
    )
    return uow


# ============================================================================
# Tests: alta con ubicación
# ============================================================================


@pytest.mark.asyncio
async def test_create_course_with_location_returns_it(mock_uow):
    """
    GIVEN: Un alta de campo con ubicación completa
    WHEN: Se ejecuta el caso de uso
    THEN: La respuesta devuelve la misma ubicación
    """
    use_case = CreateDirectGolfCourseUseCase(mock_uow)

    response = await use_case.execute(build_request(DERIO_LOCATION), UserId(str(uuid4())))

    assert response.golf_course.location is not None
    assert response.golf_course.location.latitude == 43.29519
    assert response.golf_course.location.longitude == -2.87352
    assert response.golf_course.location.city == "DERIO"
    assert response.golf_course.location.province == "VIZCAYA"


@pytest.mark.asyncio
async def test_create_course_without_location_returns_null(mock_uow):
    """
    GIVEN: Un alta de campo sin ubicación
    WHEN: Se ejecuta el caso de uso
    THEN: La respuesta trae location a null, no un objeto vacío
    """
    use_case = CreateDirectGolfCourseUseCase(mock_uow)

    response = await use_case.execute(build_request(None), UserId(str(uuid4())))

    assert response.golf_course.location is None


@pytest.mark.asyncio
async def test_zero_coordinates_are_not_treated_as_missing(mock_uow):
    """
    GIVEN: Un campo situado en latitud y longitud cero
    WHEN: Se ejecuta el caso de uso
    THEN: La respuesta trae las coordenadas, no location a null
    """
    use_case = CreateDirectGolfCourseUseCase(mock_uow)

    response = await use_case.execute(
        build_request(LocationDTO(latitude=0.0, longitude=0.0)), UserId(str(uuid4()))
    )

    assert response.golf_course.location is not None
    assert response.golf_course.location.latitude == 0.0
    assert response.golf_course.location.longitude == 0.0


@pytest.mark.asyncio
async def test_create_course_with_only_city_returns_it(mock_uow):
    """
    GIVEN: Un alta de campo con localidad pero sin coordenadas
    WHEN: Se ejecuta el caso de uso
    THEN: La respuesta trae la localidad y las coordenadas a null
    """
    use_case = CreateDirectGolfCourseUseCase(mock_uow)

    response = await use_case.execute(
        build_request(LocationDTO(city="MARBELLA", province="MÁLAGA")), UserId(str(uuid4()))
    )

    assert response.golf_course.location is not None
    assert response.golf_course.location.city == "MARBELLA"
    assert response.golf_course.location.latitude is None


# ============================================================================
# Tests: validación en el DTO
# ============================================================================


def test_location_dto_rejects_half_coordinates():
    """
    GIVEN: Una ubicación con latitud pero sin longitud
    WHEN: Se valida el DTO
    THEN: Falla antes de llegar al dominio
    """
    with pytest.raises(ValueError, match="must be provided together"):
        LocationDTO(latitude=43.29519)


def test_location_dto_rejects_out_of_range_latitude():
    """
    GIVEN: Una latitud imposible
    WHEN: Se valida el DTO
    THEN: Falla
    """
    with pytest.raises(ValueError):
        LocationDTO(latitude=91.0, longitude=0.0)


# ============================================================================
# Tests: mapeo a dominio
# ============================================================================


def test_mapper_returns_none_when_no_location_is_sent():
    """
    GIVEN: Una petición sin ubicación
    WHEN: Se mapea a dominio
    THEN: Devuelve None, que en una edición significa 'no la toques'
    """
    assert GolfCourseMapper.to_domain_location(None) is None


def test_mapper_returns_empty_value_object_for_an_empty_location():
    """
    GIVEN: Una ubicación enviada con todos sus valores a null
    WHEN: Se mapea a dominio
    THEN: Devuelve un Value Object vacío, que es la forma de borrar la ubicación
    """
    location = GolfCourseMapper.to_domain_location(LocationDTO())

    assert location is not None
    assert location.is_empty is True
