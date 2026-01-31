"""
Tests unitarios para CreateDirectGolfCourseUseCase.
"""

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.modules.golf_course.application.dtos.golf_course_dtos import (
    HoleDTO,
    RequestGolfCourseRequestDTO,
    TeeDTO,
)
from src.modules.golf_course.application.use_cases.create_direct_golf_course_use_case import (
    CreateDirectGolfCourseUseCase,
)
from src.modules.golf_course.domain.value_objects.approval_status import ApprovalStatus
from src.modules.golf_course.domain.value_objects.course_type import CourseType
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.entities.country import Country
from src.shared.domain.value_objects.country_code import CountryCode

pytestmark = pytest.mark.asyncio


class TestCreateDirectGolfCourseUseCase:
    """
    Suite de tests para CreateDirectGolfCourseUseCase.

    Este use case permite a los Admins crear campos directamente en estado APPROVED.
    """

    @pytest.fixture
    def mock_uow(self):
        """Mock del Unit of Work."""
        uow = AsyncMock()
        uow.__aenter__ = AsyncMock(return_value=uow)
        uow.commit = AsyncMock()

        # Simulate UoW context manager: commit on successful exit
        async def aexit_side_effect(exc_type, exc, tb):
            if exc_type is None:
                await uow.commit()

        uow.__aexit__ = AsyncMock(side_effect=aexit_side_effect)
        uow.golf_courses = AsyncMock()
        uow.countries = AsyncMock()
        return uow

    @pytest.fixture
    def valid_request_dto(self):
        """DTO válido para crear campo."""
        return RequestGolfCourseRequestDTO(
            name="Real Club de Golf",
            country_code="ES",
            course_type=CourseType.STANDARD_18,
            tees=[
                TeeDTO(
                    tee_category="CHAMPIONSHIP_MALE",
                    identifier="Blanco",
                    course_rating=72.5,
                    slope_rating=130,
                ),
                TeeDTO(
                    tee_category="AMATEUR_MALE",
                    identifier="Amarillo",
                    course_rating=70.0,
                    slope_rating=125,
                ),
            ],
            holes=[
                HoleDTO(hole_number=i, par=4 if i <= 12 else 3, stroke_index=i)
                for i in range(1, 19)
            ],
        )

    async def test_should_create_golf_course_directly_to_approved(
        self, mock_uow, valid_request_dto
    ):
        """
        Verifica que Admin puede crear campo directamente en estado APPROVED.

        Given: Un admin con request válido
        When: Se ejecuta el use case
        Then: El campo se crea en estado APPROVED sin necesidad de aprobación
        """
        # Arrange
        mock_uow.countries.find_by_code.return_value = Country(
            code=CountryCode("ES"), name_en="Spain", name_es="España"
        )
        creator_id = UserId(str(uuid4()))
        use_case = CreateDirectGolfCourseUseCase(mock_uow)

        # Act
        response = await use_case.execute(valid_request_dto, creator_id)

        # Assert
        assert response.golf_course.name == "Real Club de Golf"
        assert response.golf_course.approval_status == ApprovalStatus.APPROVED.value
        assert response.golf_course.country_code == "ES"
        mock_uow.golf_courses.save.assert_called_once()
        mock_uow.commit.assert_called_once()  # UoW context manager calls commit on success

    async def test_should_raise_error_when_country_not_found(self, mock_uow, valid_request_dto):
        """
        Verifica que falla si el país no existe.

        Given: Request con country_code inválido
        When: Se ejecuta el use case
        Then: Se lanza ValueError
        """
        # Arrange
        mock_uow.countries.find_by_code.return_value = None
        creator_id = UserId(str(uuid4()))
        use_case = CreateDirectGolfCourseUseCase(mock_uow)

        # Act & Assert
        with pytest.raises(ValueError, match="Country with code 'ES' not found"):
            await use_case.execute(valid_request_dto, creator_id)

        # No debe guardar ni hacer commit
        mock_uow.golf_courses.save.assert_not_called()
        mock_uow.commit.assert_not_called()
