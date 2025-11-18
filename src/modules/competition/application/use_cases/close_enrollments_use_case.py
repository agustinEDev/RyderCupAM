# -*- coding: utf-8 -*-
"""
Caso de Uso: Cerrar Inscripciones de Competition.

Permite cerrar las inscripciones de una competición (ACTIVE → CLOSED).
Solo el creador puede realizar esta acción.
"""

from src.modules.competition.application.dto.competition_dto import (
    CloseEnrollmentsRequestDTO,
    CloseEnrollmentsResponseDTO,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.entities.competition import CompetitionStateError
from src.modules.user.domain.value_objects.user_id import UserId
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)


class CompetitionNotFoundError(Exception):
    """Excepción lanzada cuando la competición no existe."""
    pass


class NotCompetitionCreatorError(Exception):
    """Excepción lanzada cuando el usuario no es el creador de la competición."""
    pass


class CloseEnrollmentsUseCase:
    """
    Caso de uso para cerrar inscripciones de una competición.

    Transición: ACTIVE → CLOSED
    Efecto: Cierra las inscripciones, ya no se aceptan nuevos jugadores

    Restricciones:
    - Solo se puede cerrar desde estado ACTIVE
    - Solo el creador puede cerrar inscripciones
    - La competición debe existir

    Orquesta:
    1. Buscar la competición por ID
    2. Verificar que el usuario sea el creador
    3. Contar inscripciones aprobadas (del repositorio de enrollments)
    4. Cerrar inscripciones (delega validación de estado a la entidad)
    5. Persistir cambios
    6. Commit de la transacción
    """

    def __init__(self, uow: CompetitionUnitOfWorkInterface):
        """
        Constructor.

        Args:
            uow: Unit of Work para gestionar transacciones
        """
        self._uow = uow

    async def execute(
        self,
        request: CloseEnrollmentsRequestDTO,
        user_id: UserId
    ) -> CloseEnrollmentsResponseDTO:
        """
        Ejecuta el caso de uso de cierre de inscripciones.

        Args:
            request: DTO con el ID de la competición
            user_id: ID del usuario que solicita el cierre

        Returns:
            DTO con datos del cierre de inscripciones

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
                    "Solo el creador puede cerrar las inscripciones"
                )

            # 3. Contar inscripciones aprobadas
            total_enrollments = await self._uow.enrollments.count_approved(competition_id)

            # 4. Cerrar inscripciones (la entidad valida la transición)
            competition.close_enrollments(total_enrollments=total_enrollments)

            # 5. Persistir cambios
            await self._uow.competitions.update(competition)

            # 6. Commit de la transacción
            await self._uow.commit()

        # 7. Retornar DTO de respuesta
        return CloseEnrollmentsResponseDTO(
            id=competition.id.value,
            status=competition.status.value,
            total_enrollments=total_enrollments,
            closed_at=competition.updated_at
        )
