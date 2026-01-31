"""
Tests unitarios para UpdateGolfCourseUseCase.
"""

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.modules.golf_course.application.dtos.golf_course_dtos import (
    HoleDTO,
    TeeDTO,
    UpdateGolfCourseRequestDTO,
)
from src.modules.golf_course.application.use_cases.update_golf_course_use_case import (
    UpdateGolfCourseUseCase,
)
from src.modules.golf_course.domain.entities.golf_course import GolfCourse
from src.modules.golf_course.domain.entities.hole import Hole
from src.modules.golf_course.domain.entities.tee import Tee
from src.modules.golf_course.domain.value_objects.approval_status import ApprovalStatus
from src.modules.golf_course.domain.value_objects.course_type import CourseType
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.golf_course.domain.value_objects.tee_category import TeeCategory
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.entities.country import Country
from src.shared.domain.value_objects.country_code import CountryCode

pytestmark = pytest.mark.asyncio


class TestUpdateGolfCourseUseCase:
    """
    Suite de tests para UpdateGolfCourseUseCase.

    Workflow (Opción A+):
    - Admin edita APPROVED/PENDING → in-place update
    - Creator edita APPROVED → crea clone
    - Creator edita PENDING → in-place update
    - REJECTED → no editable
    """

    @pytest.fixture
    def mock_uow(self):
        """Mock del Unit of Work."""
        uow = AsyncMock()
        uow.__aenter__ = AsyncMock(return_value=uow)
        uow.__aexit__ = AsyncMock(return_value=None)
        uow.golf_courses = AsyncMock()
        uow.countries = AsyncMock()
        uow.commit = AsyncMock()
        return uow

    @pytest.fixture
    def valid_update_dto(self):
        """DTO válido para actualizar campo."""
        return UpdateGolfCourseRequestDTO(
            name="Updated Golf Club",
            country_code="ES",
            course_type=CourseType.STANDARD_18,
            tees=[
                TeeDTO(
                    tee_category="CHAMPIONSHIP_MALE",
                    identifier="Blanco",
                    course_rating=73.0,
                    slope_rating=135,
                ),
                TeeDTO(
                    tee_category="AMATEUR_MALE",
                    identifier="Amarillo",
                    course_rating=71.0,
                    slope_rating=130,
                ),
            ],
            holes=[
                HoleDTO(hole_number=i, par=4 if i <= 12 else 3, stroke_index=i)
                for i in range(1, 19)
            ],
        )

    @pytest.fixture
    def approved_golf_course(self):
        """Campo de golf APPROVED para tests."""
        creator_id = UserId(str(uuid4()))
        tees = [
            Tee(
                category=TeeCategory.CHAMPIONSHIP_MALE,
                identifier="White",
                course_rating=72.0,
                slope_rating=130,
            ),
            Tee(
                category=TeeCategory.AMATEUR_MALE,
                identifier="Yellow",
                course_rating=70.0,
                slope_rating=125,
            ),
        ]
        holes = [Hole(number=i, par=4, stroke_index=i) for i in range(1, 19)]

        golf_course = GolfCourse.create(
            name="Original Golf Club",
            country_code=CountryCode("ES"),
            course_type=CourseType.STANDARD_18,
            creator_id=creator_id,
            tees=tees,
            holes=holes,
        )
        golf_course.approve()
        return golf_course

    async def test_admin_should_update_approved_course_in_place(
        self, mock_uow, valid_update_dto, approved_golf_course
    ):
        """
        Verifica que Admin actualiza campo APPROVED in-place.

        Given: Admin edita campo APPROVED
        When: Se ejecuta el use case
        Then: Campo actualizado in-place, permanece APPROVED, cambios inmediatos
        """
        # Arrange
        golf_course_id = approved_golf_course.id
        mock_uow.golf_courses.find_by_id.return_value = approved_golf_course
        mock_uow.countries.find_by_code.return_value = Country(
            code=CountryCode("ES"),
            name_en="Spain",
            name_es="España"
        )

        user_id = approved_golf_course.creator_id
        is_admin = True
        use_case = UpdateGolfCourseUseCase(mock_uow)

        # Act
        response = await use_case.execute(
            golf_course_id=golf_course_id,
            request=valid_update_dto,
            user_id=user_id,
            is_admin=is_admin,
        )

        # Assert
        assert response.golf_course.name == "Updated Golf Club"
        assert response.golf_course.approval_status == ApprovalStatus.APPROVED.value
        assert response.pending_update is None  # NO clone
        assert "admin" in response.message.lower()
        mock_uow.golf_courses.save.assert_called_once()
        mock_uow.commit.assert_called_once()

    async def test_creator_should_create_clone_when_editing_approved_course(
        self, mock_uow, valid_update_dto, approved_golf_course
    ):
        """
        Verifica que Creator crea clone al editar campo APPROVED.

        Given: Creator (no admin) edita su campo APPROVED
        When: Se ejecuta el use case
        Then: Se crea clone PENDING, original permanece APPROVED y visible
        """
        # Arrange
        golf_course_id = approved_golf_course.id
        mock_uow.golf_courses.find_by_id.return_value = approved_golf_course
        mock_uow.countries.find_by_code.return_value = Country(
            code=CountryCode("ES"),
            name_en="Spain",
            name_es="España"
        )

        user_id = approved_golf_course.creator_id
        is_admin = False  # Creator (no admin)
        use_case = UpdateGolfCourseUseCase(mock_uow)

        # Act
        response = await use_case.execute(
            golf_course_id=golf_course_id,
            request=valid_update_dto,
            user_id=user_id,
            is_admin=is_admin,
        )

        # Assert
        # Original sin cambios
        assert response.golf_course.name == "Original Golf Club"
        assert response.golf_course.approval_status == ApprovalStatus.APPROVED.value
        assert response.golf_course.is_pending_update is True

        # Clone creado
        assert response.pending_update is not None
        assert response.pending_update.name == "Updated Golf Club"
        assert response.pending_update.approval_status == ApprovalStatus.PENDING_APPROVAL.value
        assert response.pending_update.original_golf_course_id == str(golf_course_id)

        # 2 saves: original + clone
        assert mock_uow.golf_courses.save.call_count == 2
        mock_uow.commit.assert_called_once()

    async def test_creator_should_update_in_place_when_editing_pending_course(
        self, mock_uow, valid_update_dto
    ):
        """
        Verifica que Creator actualiza in-place su campo PENDING.

        Given: Creator edita su campo PENDING_APPROVAL
        When: Se ejecuta el use case
        Then: Campo actualizado in-place, permanece PENDING
        """
        # Arrange
        creator_id = UserId(str(uuid4()))
        tees = [
            Tee(
                category=TeeCategory.CHAMPIONSHIP_MALE,
                identifier="White",
                course_rating=72.0,
                slope_rating=130,
            ),
            Tee(
                category=TeeCategory.AMATEUR_MALE,
                identifier="Yellow",
                course_rating=70.0,
                slope_rating=125,
            ),
        ]
        holes = [Hole(number=i, par=4, stroke_index=i) for i in range(1, 19)]

        pending_course = GolfCourse.create(
            name="Pending Golf Club",
            country_code=CountryCode("ES"),
            course_type=CourseType.STANDARD_18,
            creator_id=creator_id,
            tees=tees,
            holes=holes,
        )
        # No aprobar (queda PENDING_APPROVAL)

        golf_course_id = pending_course.id
        mock_uow.golf_courses.find_by_id.return_value = pending_course
        mock_uow.countries.find_by_code.return_value = Country(
            code=CountryCode("ES"),
            name_en="Spain",
            name_es="España"
        )

        user_id = creator_id
        is_admin = False
        use_case = UpdateGolfCourseUseCase(mock_uow)

        # Act
        response = await use_case.execute(
            golf_course_id=golf_course_id,
            request=valid_update_dto,
            user_id=user_id,
            is_admin=is_admin,
        )

        # Assert
        assert response.golf_course.name == "Updated Golf Club"
        assert response.golf_course.approval_status == ApprovalStatus.PENDING_APPROVAL.value
        assert response.pending_update is None  # NO clone
        mock_uow.golf_courses.save.assert_called_once()
        mock_uow.commit.assert_called_once()

    async def test_should_raise_error_when_course_not_found(
        self, mock_uow, valid_update_dto
    ):
        """
        Verifica que falla si el campo no existe.

        Given: golf_course_id inválido
        When: Se ejecuta el use case
        Then: Se lanza ValueError
        """
        # Arrange
        mock_uow.golf_courses.find_by_id.return_value = None
        golf_course_id = GolfCourseId(str(uuid4()))
        user_id = UserId(str(uuid4()))
        use_case = UpdateGolfCourseUseCase(mock_uow)

        # Act & Assert
        with pytest.raises(ValueError, match="not found"):
            await use_case.execute(
                golf_course_id=golf_course_id,
                request=valid_update_dto,
                user_id=user_id,
                is_admin=False,
            )

    async def test_should_raise_error_when_user_not_owner_and_not_admin(
        self, mock_uow, valid_update_dto, approved_golf_course
    ):
        """
        Verifica que falla si usuario no es creator ni admin.

        Given: Usuario diferente al creator (y no admin)
        When: Se ejecuta el use case
        Then: Se lanza ValueError por permisos
        """
        # Arrange
        golf_course_id = approved_golf_course.id
        mock_uow.golf_courses.find_by_id.return_value = approved_golf_course

        different_user_id = UserId(str(uuid4()))  # Diferente al creator
        is_admin = False
        use_case = UpdateGolfCourseUseCase(mock_uow)

        # Act & Assert
        with pytest.raises(ValueError, match="does not have permission"):
            await use_case.execute(
                golf_course_id=golf_course_id,
                request=valid_update_dto,
                user_id=different_user_id,
                is_admin=is_admin,
            )

    async def test_should_raise_error_when_course_is_rejected(
        self, mock_uow, valid_update_dto
    ):
        """
        Verifica que no se pueden editar campos REJECTED.

        Given: Campo con estado REJECTED
        When: Se ejecuta el use case
        Then: Se lanza ValueError
        """
        # Arrange
        creator_id = UserId(str(uuid4()))
        tees = [
            Tee(
                category=TeeCategory.CHAMPIONSHIP_MALE,
                identifier="White",
                course_rating=72.0,
                slope_rating=130,
            ),
            Tee(
                category=TeeCategory.AMATEUR_MALE,
                identifier="Yellow",
                course_rating=70.0,
                slope_rating=125,
            ),
        ]
        holes = [Hole(number=i, par=4, stroke_index=i) for i in range(1, 19)]

        rejected_course = GolfCourse.create(
            name="Rejected Golf Club",
            country_code=CountryCode("ES"),
            course_type=CourseType.STANDARD_18,
            creator_id=creator_id,
            tees=tees,
            holes=holes,
        )
        rejected_course.reject("Invalid data")

        golf_course_id = rejected_course.id
        mock_uow.golf_courses.find_by_id.return_value = rejected_course

        use_case = UpdateGolfCourseUseCase(mock_uow)

        # Act & Assert
        with pytest.raises(ValueError, match="Cannot edit a REJECTED"):
            await use_case.execute(
                golf_course_id=golf_course_id,
                request=valid_update_dto,
                user_id=creator_id,
                is_admin=False,
            )
