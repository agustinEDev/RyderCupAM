"""
Caso de Uso: Completar Competition.

Permite completar/finalizar una competicion (IN_PROGRESS -> COMPLETED).
Solo el creador puede realizar esta accion.
"""

import logging

from src.modules.competition.application.dto.competition_dto import (
    CompleteCompetitionRequestDTO,
    CompleteCompetitionResponseDTO,
)
from src.modules.competition.application.exceptions import (
    CompetitionNotFoundError,
    NotCompetitionCreatorError,
)
from src.modules.competition.application.ports.tournament_achievements_publisher_interface import (
    TournamentAchievementsPublisherInterface,
)
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.user.domain.value_objects.user_id import UserId

logger = logging.getLogger(__name__)


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

    def __init__(
        self,
        uow: CompetitionUnitOfWorkInterface,
        achievements: TournamentAchievementsPublisherInterface | None = None,
    ):
        """
        Constructor.

        Args:
            uow: Unit of Work para gestionar transacciones
            achievements: Publicador del feed de logros (BE #175). Opcional:
                sin el, cerrar el torneo sigue funcionando y no se publica nada.
        """
        self._uow = uow
        self._achievements = achievements

    async def execute(
        self, request: CompleteCompetitionRequestDTO, user_id: UserId, is_admin: bool = False
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

            # 2. Verificar que el usuario sea el creador (o admin)
            if not is_admin and not competition.is_creator(user_id):
                raise NotCompetitionCreatorError("Solo el creador puede completar la competicion")

            # 3. Los inscritos, para preguntar por su marca previa fuera de aqui
            inscritos = [
                enrollment.user_id
                for enrollment in await self._uow.enrollments.find_by_competition(
                    competition_id
                )
            ]

        # 4. Fuera de la transaccion a proposito: preguntar por el mejor
        # diferencial entra en las estadisticas del jugador, que abren esta misma
        # unidad de trabajo. Anidarla arriba la cerraria antes de guardar el
        # cierre. Y va antes de completar: despues, estas vueltas ya cuentan para
        # sus estadisticas y su marca previa seria imposible de saber
        marca_previa = await self._marca_previa(inscritos)

        async with self._uow:
            competition = await self._uow.competitions.find_by_id(competition_id)
            if not competition:
                raise CompetitionNotFoundError(
                    f"No existe competición con ID {request.competition_id}"
                )

            # 5. Completar la competicion (la entidad valida la transicion)
            competition.complete()

            # 6. Persistir cambios
            await self._uow.competitions.update(competition)

        # 7. Publicar los logros del torneo en el feed de los amigos
        await self._publicar_logros(request.competition_id, marca_previa)

        # 8. Retornar DTO de respuesta
        return CompleteCompetitionResponseDTO(
            id=competition.id.value,
            status=competition.status.value,
            completed_at=competition.updated_at,
        )

    async def _marca_previa(self, inscritos: list[UserId]) -> dict[str, float | None]:
        """El mejor diferencial de cada inscrito, antes de cerrar el torneo."""
        if self._achievements is None:
            return {}

        try:
            return await self._achievements.capture_best_differentials(inscritos)
        except Exception:
            # Sin marca previa se publica todo menos el record personal, que es
            # mejor que no publicar nada
            logger.warning("Could not capture differentials before completing", exc_info=True)
            return {}

    async def _publicar_logros(
        self, competition_id_raw: str, marca_previa: dict[str, float | None]
    ) -> None:
        """
        Publica los logros del torneo sin dejar que un fallo tumbe el cierre.

        El torneo ya esta cerrado y guardado cuando esto corre. El feed es
        accesorio y el resultado del torneo no.
        """
        if self._achievements is None:
            return

        try:
            await self._achievements.publish(competition_id_raw, marca_previa)
        except Exception:
            logger.warning(
                "Could not publish achievements for competition %s",
                competition_id_raw,
                exc_info=True,
            )
