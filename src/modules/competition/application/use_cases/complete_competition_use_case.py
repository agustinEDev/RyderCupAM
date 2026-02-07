"""
Caso de Uso: Completar Competition.

Permite completar/finalizar una competicion (IN_PROGRESS -> COMPLETED).
Solo el creador puede realizar esta accion.
"""

from src.modules.competition.application.dto.competition_dto import (
    CompleteCompetitionRequestDTO,
    CompleteCompetitionResponseDTO,
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


class CompleteCompetitionUseCase:
    """
    Caso de uso para completar/finalizar una competicion.

    Transicion: IN_PROGRESS -> COMPLETED
    Efecto: El torneo ha terminado, estado final

    Restricciones:
    - Solo se puede completar desde estado IN_PROGRESS
    - Solo el creador puede completar
    - La competicion debe existir

    Orquesta:
    1. Buscar la competicion por ID
    2. Verificar que el usuario sea el creador
    3. Completar la competicion (delega validacion de estado a la entidad)
    4. Persistir cambios
    5. Commit de la transaccion
    """

    def __init__(self, uow: CompetitionUnitOfWorkInterface):
        """
        Constructor.

        Args:
            uow: Unit of Work para gestionar transacciones
        """
        self._uow = uow

    async def execute(
        self, request: CompleteCompetitionRequestDTO, user_id: UserId
    ) -> CompleteCompetitionResponseDTO:
        """
        Ejecuta el caso de uso de completar competicion.

        Args:
            request: DTO con el ID de la competicion a completar
            user_id: ID del usuario que solicita completar

        Returns:
            DTO con datos de la competicion completada

        Raises:
            CompetitionNotFoundError: Si la competicion no existe
            NotCompetitionCreatorError: Si el usuario no es el creador
            CompetitionStateError: Si la transicion de estado no es valida
        """
        async with self._uow:
            # 1. Buscar la competicion
            competition_id = CompetitionId(request.competition_id)
            competition = await self._uow.competitions.find_by_id(competition_id)

            if not competition:
                raise CompetitionNotFoundError(
                    f"No existe competición con ID {request.competition_id}"
                )

            # 2. Verificar que el usuario sea el creador
            if not competition.is_creator(user_id):
                raise NotCompetitionCreatorError("Solo el creador puede completar la competicion")

            # 3. Completar la competicion (la entidad valida la transicion)
            competition.complete()

            # 4. Persistir cambios
            await self._uow.competitions.update(competition)

        # 6. Retornar DTO de respuesta
        return CompleteCompetitionResponseDTO(
            id=competition.id.value,
            status=competition.status.value,
            completed_at=competition.updated_at,
        )
