"""
Caso de Uso: Revertir Competition a CLOSED.

Permite revertir una competición de IN_PROGRESS a CLOSED para corregir el schedule.
Solo el creador puede realizar esta acción.
"""

from src.modules.competition.application.dto.competition_dto import (
    RevertCompetitionStatusRequestDTO,
    RevertCompetitionStatusResponseDTO,
)
from src.modules.competition.application.exceptions import (
    CompetitionNotFoundError,
    NotCompetitionCreatorError,
)
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.user.domain.value_objects.user_id import UserId


class RevertCompetitionStatusUseCase:
    """
    Caso de uso para revertir una competición a CLOSED.

    Transición: IN_PROGRESS → CLOSED
    Efecto: El creador puede corregir el schedule (equipos, rondas, matches)

    Restricciones:
    - Solo se puede revertir desde estado IN_PROGRESS
    - Solo el creador puede revertir
    - La competición debe existir

    Orquesta:
    1. Buscar la competición por ID
    2. Verificar que el usuario sea el creador
    3. Revertir la competición (delega validación de estado a la entidad)
    4. Persistir cambios
    5. Commit de la transacción
    """

    def __init__(self, uow: CompetitionUnitOfWorkInterface):
        self._uow = uow

    async def execute(
        self, request: RevertCompetitionStatusRequestDTO, user_id: UserId
    ) -> RevertCompetitionStatusResponseDTO:
        """
        Ejecuta el caso de uso de reversión de competición.

        Args:
            request: DTO con el ID de la competición a revertir
            user_id: ID del usuario que solicita la reversión

        Returns:
            DTO con datos de la competición revertida

        Raises:
            CompetitionNotFoundError: Si la competición no existe
            NotCompetitionCreatorError: Si el usuario no es el creador
            CompetitionStateError: Si la transición de estado no es válida
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
                    "Solo el creador puede revertir la competición"
                )

            # 3. Revertir la competición (la entidad valida la transición)
            competition.revert_to_closed()

            # 4. Persistir cambios
            await self._uow.competitions.update(competition)

        # 5. Retornar DTO de respuesta
        return RevertCompetitionStatusResponseDTO(
            id=competition.id.value,
            status=competition.status.value,
            reverted_at=competition.updated_at,
        )
