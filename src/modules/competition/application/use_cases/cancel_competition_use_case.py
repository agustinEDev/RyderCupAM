"""
Caso de Uso: Cancelar Competition.

Permite cancelar una competición (cualquier estado → CANCELLED).
Solo el creador puede realizar esta acción.
Es una cancelación lógica, no se elimina físicamente.
"""

from src.modules.competition.application.dto.competition_dto import (
    CancelCompetitionRequestDTO,
    CancelCompetitionResponseDTO,
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


class CancelCompetitionUseCase:
    """
    Caso de uso para cancelar una competición.

    Transición: cualquier estado (excepto finales) → CANCELLED
    Efecto: Cancelación lógica, se mantiene el registro histórico

    Restricciones:
    - No se puede cancelar si ya está en estado final (COMPLETED/CANCELLED)
    - Solo el creador puede cancelar
    - La competición debe existir

    Use cases típicos:
    - Cancelar por mal tiempo
    - Cancelar por falta de participantes
    - Cancelar por razones organizativas

    Orquesta:
    1. Buscar la competición por ID
    2. Verificar que el usuario sea el creador
    3. Cancelar la competición (delega validación de estado a la entidad)
    4. Persistir cambios
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
        self, request: CancelCompetitionRequestDTO, user_id: UserId
    ) -> CancelCompetitionResponseDTO:
        """
        Ejecuta el caso de uso de cancelación de competición.

        Args:
            request: DTO con el ID y razón opcional de cancelación
            user_id: ID del usuario que solicita cancelar

        Returns:
            DTO con datos de la competición cancelada

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
                raise NotCompetitionCreatorError("Solo el creador puede cancelar la competición")

            # 3. Cancelar la competición (la entidad valida la transición)
            competition.cancel(reason=request.reason)

            # 4. Persistir cambios
            await self._uow.competitions.update(competition)

        # 6. Retornar DTO de respuesta
        return CancelCompetitionResponseDTO(
            id=competition.id.value,
            status=competition.status.value,
            reason=request.reason,
            cancelled_at=competition.updated_at,
        )
