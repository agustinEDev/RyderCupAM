"""
Caso de Uso: Reabrir Inscripciones.

Permite reabrir inscripciones de una competición (CLOSED → ACTIVE).
Solo el creador puede realizar esta acción.
"""

from collections.abc import Callable
from datetime import UTC, datetime

from src.modules.competition.application.dto.competition_dto import (
    ReopenEnrollmentsRequestDTO,
    ReopenEnrollmentsResponseDTO,
)
from src.modules.competition.application.exceptions import (
    CompetitionNotFoundError,
    NotCompetitionCreatorError,
)
from src.modules.competition.application.ports.competition_timezone import ICompetitionTimezone
from src.modules.competition.application.services.actualizaciones_de_handicaps import (
    ActualizacionesDeHandicaps,
)
from src.modules.competition.application.services.partidas_del_jugador import (
    salidas_por_hora,
)
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.partida_id import PartidaId
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

    def __init__(
        self,
        uow: CompetitionUnitOfWorkInterface,
        zonas: ICompetitionTimezone | None = None,
        reloj: Callable[[], datetime] = lambda: datetime.now(UTC),
    ):
        """
        Args:
            zonas: Para no borrar las partidas que ya salieron por su hora (#251).
                Sin ellas, solo cuenta el estado de la partida
        """
        self._uow = uow
        self._zonas = zonas
        self._reloj = reloj

    async def execute(
        self, request: ReopenEnrollmentsRequestDTO, user_id: UserId, is_admin: bool = False
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
            # Bloqueada, como las demás que tocan partidas y plazas (#251)
            competition = await self._uow.competitions.find_by_id_for_update(competition_id)

            if not competition:
                raise CompetitionNotFoundError(
                    f"No existe competición con ID {request.competition_id}"
                )

            # 2. Verificar que el usuario sea el creador (o admin)
            if not is_admin and not competition.is_creator(user_id):
                raise NotCompetitionCreatorError("Solo el creador puede reabrir inscripciones")

            # 3. Reabrir inscripciones (la entidad valida la transición)
            competition.reopen_enrollments()

            # La actualización de hándicaps que esté a medias se corta: al volver
            # a cerrar empieza otra (#251)
            await ActualizacionesDeHandicaps(self._uow, None).cortar(competition.id)

            # Las partidas que no han salido se borran: pueden entrar y salir
            # jugadores, y se vuelven a generar al cerrar. Las que salieron (por su
            # estado o por su hora: hasta la PR 5 nadie las pasa a IN_PROGRESS) se
            # quedan: lo jugado no se borra (D1, #251)
            await self._borrar_las_que_no_salieron(competition.id)

            # 4. Persistir cambios
            await self._uow.competitions.update(competition)

        # 5. Retornar DTO de respuesta
        return ReopenEnrollmentsResponseDTO(
            id=competition.id.value,
            status=competition.status.value,
            reopened_at=competition.updated_at,
        )

    async def _borrar_las_que_no_salieron(self, competition_id: CompetitionId) -> None:
        partidas = await self._uow.partidas.de_la_competicion(competition_id)
        ahora = self._reloj()
        salidas: set[PartidaId] = set()
        for round_id in {p.round_id for p in partidas}:
            franja = await self._uow.rounds.find_by_id(round_id)
            if franja is not None:
                de_la_franja = [p for p in partidas if p.round_id == round_id]
                salidas |= await salidas_por_hora(franja, de_la_franja, self._zonas, ahora)
        await self._uow.partidas.borrar(
            [p for p in partidas if not p.empezada and p.id not in salidas]
        )
