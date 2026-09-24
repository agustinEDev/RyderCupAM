"""Caso de Uso: Eliminar Ronda/Sesión de competición."""

from datetime import UTC, datetime

from src.modules.competition.application.dto.round_match_dto import (
    DeleteRoundRequestDTO,
    DeleteRoundResponseDTO,
)
from src.modules.competition.application.exceptions import (
    AgendaNotEditableError,
    CompetitionNotFoundError,
    NotCompetitionCreatorError,
    RoundNotFoundError,
    RoundNotModifiableError,
)
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.value_objects.round_id import RoundId
from src.modules.user.domain.value_objects.user_id import UserId


class DeleteRoundUseCase:
    """
    Caso de uso para eliminar una ronda de competición.

    Elimina la ronda y todos sus partidos en cascada.

    Restricciones:
    - La ronda debe existir
    - Solo el creador puede eliminar
    - La competición no puede haber terminado ni estar cancelada (BE #365)
    - La ronda debe estar en estado modificable (PENDING_TEAMS/PENDING_MATCHES)
    """

    def __init__(self, uow: CompetitionUnitOfWorkInterface):
        self._uow = uow

    async def execute(
        self, request: DeleteRoundRequestDTO, user_id: UserId, is_admin: bool = False
    ) -> DeleteRoundResponseDTO:
        async with self._uow:
            # 1. Buscar la ronda
            round_id = RoundId(request.round_id)
            round_entity = await self._uow.rounds.find_by_id(round_id)

            if not round_entity:
                raise RoundNotFoundError(f"No existe ronda con ID {request.round_id}")

            # 2. Buscar la competición
            # Bloqueada, como al generar partidos: comprobar que la sesión no
            # tiene partidos y tocarla tiene que ser una sola cosa
            competition = await self._uow.competitions.find_by_id_for_update(
                round_entity.competition_id
            )

            if not competition:
                raise CompetitionNotFoundError("La competición asociada no existe")

            # Releída tras el bloqueo: si mientras se esperaba otra petición
            # generó sus partidos, se decide con eso y no con lo de antes
            round_entity = await self._uow.rounds.find_by_id_for_update(round_id) or round_entity

            # 3. Verificar creador
            if not is_admin and not competition.is_creator(user_id):
                raise NotCompetitionCreatorError("Solo el creador puede eliminar rondas")

            # La agenda se edita desde que la competición existe (BE #365): lo
            # que se protege es la sesión ya jugada, y eso lo mira la sesión
            if not competition.status.allows_agenda_edits():
                raise AgendaNotEditableError(
                    "La agenda solo se puede cambiar hasta que la competición termina o se cancela. "
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
