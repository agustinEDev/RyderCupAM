"""
Caso de Uso: Activar Competition.

Permite activar una competición (DRAFT → ACTIVE), abriendo las inscripciones.
Solo el creador puede realizar esta acción.
"""

from src.modules.competition.application.dto.competition_dto import (
    ActivateCompetitionRequestDTO,
    ActivateCompetitionResponseDTO,
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


class ActivateCompetitionUseCase:
    """
    Caso de uso para activar una competición.

    Transición: DRAFT → ACTIVE
    Efecto: Abre las inscripciones para jugadores

    Restricciones:
    - Solo se puede activar desde estado DRAFT
    - Solo el creador puede activar
    - La competición debe existir

    Orquesta:
    1. Buscar la competición por ID
    2. Verificar que el usuario sea el creador
    3. Activar la competición (delega validación de estado a la entidad)
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
        self, request: ActivateCompetitionRequestDTO, user_id: UserId
    ) -> ActivateCompetitionResponseDTO:
        """
        Ejecuta el caso de uso de activación de competición.

        Args:
            request: DTO con el ID de la competición a activar
            user_id: ID del usuario que solicita la activación

        Returns:
            DTO con datos de la competición activada

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
                raise NotCompetitionCreatorError("Solo el creador puede activar la competición")

            # 3. Activar la competición (la entidad valida la transición)
            competition.activate()

            # 4. Persistir cambios
            await self._uow.competitions.update(competition)

        # 6. Retornar DTO de respuesta
        return ActivateCompetitionResponseDTO(
            id=competition.id.value,
            status=competition.status.value,
            activated_at=competition.updated_at,
        )
