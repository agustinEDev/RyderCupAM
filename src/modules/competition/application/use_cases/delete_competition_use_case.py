"""
Caso de Uso: Eliminar Competition (eliminación física).

Permite eliminar físicamente una competición en estado DRAFT.
Solo el creador puede realizar esta acción.
"""

from datetime import datetime

from src.modules.competition.application.dto.competition_dto import (
    DeleteCompetitionRequestDTO,
    DeleteCompetitionResponseDTO,
)
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.user.domain.value_objects.user_id import UserId


class CompetitionNotFoundError(Exception):
    """Excepción lanzada cuando la competición no existe."""

    pass


class NotCompetitionCreatorError(Exception):
    """Excepción lanzada cuando el usuario no es el creador de la competición."""

    pass


class CompetitionNotDeletableError(Exception):
    """Excepción lanzada cuando la competición no está en estado DRAFT."""

    pass


class DeleteCompetitionUseCase:
    """
    Caso de uso para eliminar físicamente una competición.

    Restricciones:
    - Solo se puede eliminar en estado DRAFT
    - Solo el creador puede eliminar
    - Se elimina permanentemente de la BD (incluyendo enrollments si existieran)

    Orquesta:
    1. Buscar la competición por ID
    2. Verificar que el usuario sea el creador
    3. Verificar que esté en estado DRAFT
    4. Eliminar la competición del repositorio
    5. Commit de la transacción
    """

    def __init__(self, uow: CompetitionUnitOfWorkInterface):
        """
        Constructor.

        Args:
            uow: Unit of Work para gestionar transacciones
        """
        self._uow = uow

    async def execute(
        self, request: DeleteCompetitionRequestDTO, user_id: UserId
    ) -> DeleteCompetitionResponseDTO:
        """
        Ejecuta el caso de uso de eliminación de competición.

        Args:
            request: DTO con el ID de la competición a eliminar
            user_id: ID del usuario que solicita la eliminación

        Returns:
            DTO con confirmación de eliminación

        Raises:
            CompetitionNotFoundError: Si la competición no existe
            NotCompetitionCreatorError: Si el usuario no es el creador
            CompetitionNotDeletableError: Si la competición no está en estado DRAFT
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
                raise NotCompetitionCreatorError("Solo el creador puede eliminar la competición")

            # 3. Verificar que esté en estado DRAFT
            if not competition.is_draft():
                raise CompetitionNotDeletableError(
                    f"Solo se pueden eliminar competiciones en estado DRAFT. "
                    f"Estado actual: {competition.status.value}"
                )

            # 4. Guardar datos para el response antes de eliminar
            competition_id_value = competition.id.value
            competition_name = str(competition.name)

            # 5. Eliminar la competición
            await self._uow.competitions.delete(competition_id)

            # 6. Commit de la transacción
            await self._uow.commit()

        # 7. Retornar DTO de respuesta
        return DeleteCompetitionResponseDTO(
            id=competition_id_value,
            name=competition_name,
            deleted=True,
            deleted_at=datetime.now(),
        )
