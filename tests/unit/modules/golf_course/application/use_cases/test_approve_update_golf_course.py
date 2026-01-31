"""
Tests unitarios para ApproveUpdateGolfCourseUseCase.
"""

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.modules.golf_course.application.dtos.golf_course_dtos import (
    ApproveUpdateGolfCourseRequestDTO,
)
from src.modules.golf_course.application.use_cases.approve_update_golf_course_use_case import (
    ApproveUpdateGolfCourseUseCase,
)
from src.modules.golf_course.domain.entities.golf_course import GolfCourse
from src.modules.golf_course.domain.entities.hole import Hole
from src.modules.golf_course.domain.entities.tee import Tee
from src.modules.golf_course.domain.value_objects.approval_status import ApprovalStatus
from src.modules.golf_course.domain.value_objects.course_type import CourseType
from src.modules.golf_course.domain.value_objects.tee_category import TeeCategory
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.country_code import CountryCode

pytestmark = pytest.mark.asyncio


class TestApproveUpdateGolfCourseUseCase:
    """
    Suite de tests para ApproveUpdateGolfCourseUseCase.

    Este use case permite al Admin aprobar un clone de actualización,
    aplicando los cambios al campo original y eliminando el clone.
    """

    @pytest.fixture
    def mock_uow(self):
        """Mock del Unit of Work."""
        uow = AsyncMock()
        uow.__aenter__ = AsyncMock(return_value=uow)
        uow.__aexit__ = AsyncMock(return_value=None)
        uow.golf_courses = AsyncMock()
        uow.commit = AsyncMock()
        return uow

    @pytest.fixture
    def original_and_clone(self):
        """Fixture con campo original APPROVED y su clone PENDING."""
        creator_id = UserId(str(uuid4()))
        tees_original = [
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
        holes_original = [Hole(number=i, par=4, stroke_index=i) for i in range(1, 19)]

        # Original APPROVED
        original = GolfCourse.create(
            name="Original Golf Club",
            country_code=CountryCode("ES"),
            course_type=CourseType.STANDARD_18,
            creator_id=creator_id,
            tees=tees_original,
            holes=holes_original,
        )
        original.approve()
        original.mark_as_pending_update()

        # Clone PENDING con cambios
        tees_clone = [
            Tee(
                category=TeeCategory.CHAMPIONSHIP_MALE,
                identifier="Blue",
                course_rating=74.0,
                slope_rating=135,
            ),
            Tee(
                category=TeeCategory.AMATEUR_MALE,
                identifier="Red",
                course_rating=72.0,
                slope_rating=130,
            ),
        ]
        # Holes con pars válidos (total = 70: 4xpar3 + 10xpar4 + 4xpar5)
        holes_clone = [
            Hole(number=i, par=3, stroke_index=i)
            if i in [3, 7, 12, 17]
            else Hole(number=i, par=5, stroke_index=i)
            if i in [5, 9, 14, 18]
            else Hole(number=i, par=4, stroke_index=i)
            for i in range(1, 19)
        ]

        clone = GolfCourse.create(
            name="Updated Golf Club",
            country_code=CountryCode("FR"),
            course_type=CourseType.STANDARD_18,
            creator_id=creator_id,
            tees=tees_clone,
            holes=holes_clone,
        )

        # Reconstruir clone con original_golf_course_id
        clone_reconstructed = GolfCourse.reconstruct(
            id=clone.id,
            name=clone.name,
            country_code=clone.country_code,
            course_type=clone.course_type,
            creator_id=clone.creator_id,
            tees=clone.tees,
            holes=clone.holes,
            approval_status=ApprovalStatus.PENDING_APPROVAL,
            rejection_reason=None,
            created_at=clone.created_at,
            updated_at=clone.updated_at,
            original_golf_course_id=original.id,  # Link!
            is_pending_update=False,
        )

        return original, clone_reconstructed

    async def test_should_approve_update_and_apply_changes_to_original(
        self, mock_uow, original_and_clone
    ):
        """
        Verifica que Admin puede aprobar clone y aplicar cambios al original.

        Given: Clone válido con original_golf_course_id
        When: Admin aprueba el update
        Then: Cambios del clone se aplican al original, clone eliminado
        """
        # Arrange
        original, clone = original_and_clone

        mock_uow.golf_courses.find_by_id.side_effect = [
            clone,  # Primera llamada: buscar clone
            original,  # Segunda llamada: buscar original
        ]

        request_dto = ApproveUpdateGolfCourseRequestDTO(clone_id=str(clone.id))
        use_case = ApproveUpdateGolfCourseUseCase(mock_uow)

        # Act
        response = await use_case.execute(request_dto)

        # Assert
        assert response.updated_golf_course.name == "Updated Golf Club"
        assert response.updated_golf_course.country_code == "FR"
        assert response.updated_golf_course.approval_status == ApprovalStatus.APPROVED.value
        assert response.updated_golf_course.is_pending_update is False
        assert response.applied_changes_from == str(clone.id)

        # Verificar llamadas
        mock_uow.golf_courses.save.assert_called_once()  # Original actualizado
        mock_uow.golf_courses.delete.assert_called_once_with(clone.id)  # Clone eliminado (por ID)
        mock_uow.commit.assert_called_once()

    async def test_should_raise_error_when_clone_not_found(self, mock_uow):
        """
        Verifica que falla si el clone no existe.

        Given: clone_id inválido
        When: Se ejecuta el use case
        Then: Se lanza ValueError
        """
        # Arrange
        mock_uow.golf_courses.find_by_id.return_value = None

        from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId

        clone_id = GolfCourseId(str(uuid4()))
        request_dto = ApproveUpdateGolfCourseRequestDTO(clone_id=str(clone_id))
        use_case = ApproveUpdateGolfCourseUseCase(mock_uow)

        # Act & Assert
        with pytest.raises(ValueError, match="not found"):
            await use_case.execute(request_dto)

        mock_uow.golf_courses.save.assert_not_called()
        mock_uow.golf_courses.delete.assert_not_called()
        mock_uow.commit.assert_not_called()

    async def test_should_raise_error_when_not_a_clone(self, mock_uow):
        """
        Verifica que falla si el campo no es un clone (no tiene original_golf_course_id).

        Given: Campo normal sin original_golf_course_id
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

        # Campo normal (NO es clone)
        normal_course = GolfCourse.create(
            name="Normal Golf Club",
            country_code=CountryCode("ES"),
            course_type=CourseType.STANDARD_18,
            creator_id=creator_id,
            tees=tees,
            holes=holes,
        )

        mock_uow.golf_courses.find_by_id.return_value = normal_course

        request_dto = ApproveUpdateGolfCourseRequestDTO(clone_id=str(normal_course.id))
        use_case = ApproveUpdateGolfCourseUseCase(mock_uow)

        # Act & Assert
        with pytest.raises(ValueError, match="not a clone"):
            await use_case.execute(request_dto)

        mock_uow.golf_courses.save.assert_not_called()
        mock_uow.golf_courses.delete.assert_not_called()

    async def test_should_raise_error_when_original_not_found(self, mock_uow, original_and_clone):
        """
        Verifica que falla si el campo original no existe.

        Given: Clone válido pero original eliminado
        When: Se ejecuta el use case
        Then: Se lanza ValueError
        """
        # Arrange
        _, clone = original_and_clone

        mock_uow.golf_courses.find_by_id.side_effect = [
            clone,  # Primera llamada: clone encontrado
            None,  # Segunda llamada: original NO encontrado
        ]

        request_dto = ApproveUpdateGolfCourseRequestDTO(clone_id=str(clone.id))
        use_case = ApproveUpdateGolfCourseUseCase(mock_uow)

        # Act & Assert
        with pytest.raises(ValueError, match="Original golf course"):
            await use_case.execute(request_dto)
