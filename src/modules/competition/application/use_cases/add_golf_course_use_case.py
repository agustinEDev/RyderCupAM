"""
Caso de Uso: Añadir Campo de Golf a Competición.

Permite asociar un campo de golf aprobado a una competición en estado DRAFT.
Solo el creador puede realizar esta acción.
"""

from datetime import datetime

from src.modules.competition.application.dto.competition_dto import (
    AddGolfCourseRequestDTO,
    AddGolfCourseResponseDTO,
)
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.golf_course.domain.repositories.golf_course_repository import (
    IGolfCourseRepository,
)
from src.modules.golf_course.domain.value_objects.approval_status import ApprovalStatus
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.user.domain.value_objects.user_id import UserId


class CompetitionNotFoundError(Exception):
    """Excepción lanzada cuando la competición no existe."""

    pass


class NotCompetitionCreatorError(Exception):
    """Excepción lanzada cuando el usuario no es el creador de la competición."""

    pass


class CompetitionNotDraftError(Exception):
    """Excepción lanzada cuando la competición no está en estado DRAFT."""

    pass


class GolfCourseNotFoundError(Exception):
    """Excepción lanzada cuando el campo de golf no existe."""

    pass


class GolfCourseNotApprovedError(Exception):
    """Excepción lanzada cuando el campo de golf no está aprobado."""

    pass


class GolfCourseAlreadyAssignedError(Exception):
    """Excepción lanzada cuando el campo de golf ya está asociado a la competición."""

    pass


class IncompatibleCountryError(Exception):
    """Excepción lanzada cuando el país del campo no es compatible con la competición."""

    pass


class AddGolfCourseToCompetitionUseCase:
    """
    Caso de uso para añadir un campo de golf a una competición.

    Restricciones:
    - La competición debe estar en estado DRAFT
    - Solo el creador puede añadir campos
    - El campo debe existir y estar aprobado
    - El país del campo debe ser compatible con la ubicación de la competición
    - El campo no puede estar ya asociado a la competición

    Orquesta:
    1. Buscar la competición por ID
    2. Verificar que el usuario sea el creador
    3. Verificar que esté en estado DRAFT
    4. Buscar el campo de golf por ID
    5. Verificar que el campo esté aprobado
    6. Añadir el campo a la competición (validación de país en el dominio)
    7. Guardar la competición actualizada
    8. Commit de la transacción
    """

    def __init__(
        self,
        uow: CompetitionUnitOfWorkInterface,
        golf_course_repository: IGolfCourseRepository,
    ):
        """
        Constructor.

        Args:
            uow: Unit of Work para gestionar transacciones de Competition
            golf_course_repository: Repositorio de campos de golf (cross-module)
        """
        self._uow = uow
        self._golf_course_repo = golf_course_repository

    async def execute(
        self, request: AddGolfCourseRequestDTO, user_id: UserId
    ) -> AddGolfCourseResponseDTO:
        """
        Ejecuta el caso de uso de añadir campo de golf a competición.

        Args:
            request: DTO con competition_id y golf_course_id
            user_id: ID del usuario que solicita la operación

        Returns:
            DTO con confirmación de adición

        Raises:
            CompetitionNotFoundError: Si la competición no existe
            NotCompetitionCreatorError: Si el usuario no es el creador
            CompetitionNotDraftError: Si la competición no está en estado DRAFT
            GolfCourseNotFoundError: Si el campo de golf no existe
            GolfCourseNotApprovedError: Si el campo no está aprobado
            GolfCourseAlreadyAssignedError: Si el campo ya está asociado
            IncompatibleCountryError: Si el país del campo no es compatible
        """
        async with self._uow:
            # 1. Buscar la competición
            competition_id = CompetitionId(request.competition_id)
            competition = await self._uow.competitions.find_by_id(competition_id)

            if not competition:
                raise CompetitionNotFoundError(
                    f"No existe competición con ID {request.competition_id}"
                )

            # 2. Verificar que el usuario sea el creador
            if not competition.is_creator(user_id):
                raise NotCompetitionCreatorError(
                    "Solo el creador puede añadir campos de golf a la competición"
                )

            # 3. Verificar que esté en estado DRAFT
            if not competition.is_draft():
                raise CompetitionNotDraftError(
                    f"Solo se pueden añadir campos en estado DRAFT. "
                    f"Estado actual: {competition.status.value}"
                )

            # 4. Buscar el campo de golf
            golf_course_id = GolfCourseId(request.golf_course_id)
            golf_course = await self._golf_course_repo.find_by_id(golf_course_id)

            if not golf_course:
                raise GolfCourseNotFoundError(
                    f"No existe campo de golf con ID {request.golf_course_id}"
                )

            # 5. Verificar que el campo esté aprobado
            if golf_course.approval_status != ApprovalStatus.APPROVED:
                raise GolfCourseNotApprovedError(
                    f"El campo de golf '{golf_course.name}' no está aprobado. "
                    f"Estado actual: {golf_course.approval_status.value}"
                )

            # 6. Añadir el campo a la competición (validación de país + duplicados en dominio)
            try:
                competition.add_golf_course(golf_course_id, golf_course.country_code)
            except ValueError as e:
                # Puede ser por país incompatible o campo duplicado
                error_msg = str(e)
                if "país" in error_msg.lower() or "country" in error_msg.lower():
                    raise IncompatibleCountryError(error_msg) from e
                if "duplicado" in error_msg.lower() or "already" in error_msg.lower():
                    raise GolfCourseAlreadyAssignedError(error_msg) from e
                raise  # Re-lanzar si es otro tipo de ValueError

            # 7. Guardar la competición actualizada
            await self._uow.competitions.update(competition)

        # 8. Construir respuesta
        # Buscar el display_order asignado (último en la lista)
        assigned_association = next(
            (
                gc
                for gc in competition.golf_courses
                if gc.golf_course_id == golf_course_id
            ),
            None,
        )

        return AddGolfCourseResponseDTO(
            competition_id=request.competition_id,
            golf_course_id=request.golf_course_id,
            display_order=assigned_association.display_order
            if assigned_association
            else len(competition.golf_courses),
            added_at=datetime.now(),
        )
