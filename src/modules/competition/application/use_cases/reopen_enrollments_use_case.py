"""
Caso de Uso: Reabrir Inscripciones.

Permite reabrir inscripciones de una competición (CLOSED → ACTIVE).
Solo el creador puede realizar esta acción.
"""

from src.modules.competition.application.dto.competition_dto import (
    ReopenEnrollmentsRequestDTO,
    ReopenEnrollmentsResponseDTO,
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


class ReopenEnrollmentsUseCase:
    """
    Caso de uso para reabrir inscripciones de una competición.

    Transición: CLOSED → ACTIVE
    Efecto: El creador puede añadir o modificar jugadores

    Restricciones:
    - Solo se puede reabrir desde estado CLOSED
    - Solo el creador puede reabrir
    - La competición debe existir

    Orquesta:
    1. Buscar la competición por ID
    2. Verificar que el usuario sea el creador
    3. Reabrir inscripciones (delega validación de estado a la entidad)
    4. Persistir cambios
    5. Commit de la transacción
    """

    def __init__(self, uow: CompetitionUnitOfWorkInterface):
        self._uow = uow

    async def execute(
        self, request: ReopenEnrollmentsRequestDTO, user_id: UserId
    ) -> ReopenEnrollmentsResponseDTO:
        """
        Ejecuta el caso de uso de reapertura de inscripciones.

        Args:
            request: DTO con el ID de la competición a reabrir
            user_id: ID del usuario que solicita la reapertura

        Returns:
            DTO con datos de la competición reabierta

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
                    "Solo el creador puede reabrir inscripciones"
                )

            # 3. Reabrir inscripciones (la entidad valida la transición)
            competition.reopen_enrollments()

            # 4. Persistir cambios
            await self._uow.competitions.update(competition)

        # 5. Retornar DTO de respuesta
        return ReopenEnrollmentsResponseDTO(
            id=competition.id.value,
            status=competition.status.value,
            reopened_at=competition.updated_at,
        )
