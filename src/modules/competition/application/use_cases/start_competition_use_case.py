"""
Caso de Uso: Iniciar Competition.

Permite iniciar una competición (CLOSED → IN_PROGRESS).
Solo el creador puede realizar esta acción.
"""

from src.modules.competition.application.dto.competition_dto import (
    StartCompetitionRequestDTO,
    StartCompetitionResponseDTO,
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


class StartCompetitionUseCase:
    """
    Caso de uso para iniciar una competición.

    Transición: CLOSED → IN_PROGRESS
    Efecto: La competición comienza, los matches pueden jugarse

    Restricciones:
    - Solo se puede iniciar desde estado CLOSED
    - Solo el creador puede iniciar
    - La competición debe existir

    Orquesta:
    1. Buscar la competición por ID
    2. Verificar que el usuario sea el creador
    3. Iniciar la competición (delega validación de estado a la entidad)
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
        self, request: StartCompetitionRequestDTO, user_id: UserId
    ) -> StartCompetitionResponseDTO:
        """
        Ejecuta el caso de uso de inicio de competición.

        Args:
            request: DTO con el ID de la competición a iniciar
            user_id: ID del usuario que solicita el inicio

        Returns:
            DTO con datos de la competición iniciada

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
                raise NotCompetitionCreatorError("Solo el creador puede iniciar la competición")

            # 3. Iniciar la competición (la entidad valida la transición)
            competition.start()

            # 4. Persistir cambios
            await self._uow.competitions.update(competition)

        # 6. Retornar DTO de respuesta
        return StartCompetitionResponseDTO(
            id=competition.id.value,
            status=competition.status.value,
            started_at=competition.updated_at,
        )
