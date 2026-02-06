"""Caso de Uso: Eliminar Ronda/Sesión de competición."""

from datetime import UTC, datetime

from src.modules.competition.application.dto.round_match_dto import (
    DeleteRoundRequestDTO,
    DeleteRoundResponseDTO,
)
from src.modules.competition.application.exceptions import (
    CompetitionNotFoundError,
)
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.value_objects.competition_status import CompetitionStatus
from src.modules.competition.domain.value_objects.round_id import RoundId
from src.modules.user.domain.value_objects.user_id import UserId


class RoundNotFoundError(Exception):
    """La ronda no existe."""

    pass


class NotCompetitionCreatorError(Exception):
    """El usuario no es el creador de la competición."""

    pass


class RoundNotModifiableError(Exception):
    """La ronda no puede eliminarse en su estado actual."""

    pass


class CompetitionNotClosedError(Exception):
    """La competición no está en estado CLOSED."""

    pass


class DeleteRoundUseCase:
    """
    Caso de uso para eliminar una ronda de competición.

    Elimina la ronda y todos sus partidos en cascada.

    Restricciones:
    - La ronda debe existir
    - Solo el creador puede eliminar
    - La competición debe estar en estado CLOSED
    - La ronda debe estar en estado modificable (PENDING_TEAMS/PENDING_MATCHES)
    """

    def __init__(self, uow: CompetitionUnitOfWorkInterface):
        self._uow = uow

    async def execute(
        self, request: DeleteRoundRequestDTO, user_id: UserId
    ) -> DeleteRoundResponseDTO:
        async with self._uow:
            # 1. Buscar la ronda
            round_id = RoundId(request.round_id)
            round_entity = await self._uow.rounds.find_by_id(round_id)

            if not round_entity:
                raise RoundNotFoundError(
                    f"No existe ronda con ID {request.round_id}"
                )

            # 2. Buscar la competición
            competition = await self._uow.competitions.find_by_id(
                round_entity.competition_id
            )

            if not competition:
                raise CompetitionNotFoundError("La competición asociada no existe")

            # 3. Verificar creador
            if not competition.is_creator(user_id):
                raise NotCompetitionCreatorError(
                    "Solo el creador puede eliminar rondas"
                )

            # 4. Verificar competición CLOSED
            if competition.status != CompetitionStatus.CLOSED:
                raise CompetitionNotClosedError(
                    f"La competición debe estar en estado CLOSED. "
                    f"Estado actual: {competition.status.value}"
                )

            # 5. Verificar ronda modificable
            if not round_entity.can_modify():
                raise RoundNotModifiableError(
                    f"No se puede eliminar la ronda en estado {round_entity.status.value}. "
                    f"Solo PENDING_TEAMS o PENDING_MATCHES"
                )

            # 6. Eliminar partidos asociados en cascada
            matches = await self._uow.matches.find_by_round(round_id)
            matches_deleted = 0
            for match in matches:
                await self._uow.matches.delete(match.id)
                matches_deleted += 1

            # 7. Eliminar la ronda
            await self._uow.rounds.delete(round_id)

        return DeleteRoundResponseDTO(
            id=request.round_id,
            deleted=True,
            matches_deleted=matches_deleted,
            deleted_at=datetime.now(UTC).replace(tzinfo=None),
        )
