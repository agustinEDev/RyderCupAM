"""
Caso de Uso: Reabrir Inscripciones.

Permite reabrir inscripciones de una competición (CLOSED → ACTIVE).
Solo el creador puede realizar esta acción.
"""

from collections.abc import Callable
from datetime import datetime

from src.modules.competition.application.dto.competition_dto import (
    ReopenEnrollmentsRequestDTO,
    ReopenEnrollmentsResponseDTO,
)
from src.modules.competition.application.exceptions import (
    CompetitionNotFoundError,
    NotCompetitionCreatorError,
)
from src.modules.competition.application.ports.competition_activity_publisher_interface import (
    CompetitionActivityPublisherInterface,
)
from src.modules.competition.application.ports.competition_timezone import ICompetitionTimezone
from src.modules.competition.application.ports.invitation_email_service_interface import (
    IInvitationEmailService,
)
from src.modules.competition.application.services.avisos_de_actividad import AvisosDeActividad
from src.modules.competition.application.services.reapertura import Reapertura
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.services.instante_utc import ahora_en_utc


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
        reloj: Callable[[], datetime] = ahora_en_utc,
        actividad: CompetitionActivityPublisherInterface | None = None,
        correos: IInvitationEmailService | None = None,
        user_uow: UserUnitOfWorkInterface | None = None,
    ):
        """
        Args:
            zonas: Para no borrar las partidas que ya salieron por su hora (#251).
                Sin ellas, solo cuenta el estado de la partida
            actividad: Para retirar los avisos de salida de las partidas que se
                borran (G4); sin el, no se avisa
        """
        self._uow = uow
        self._zonas = zonas
        self._reloj = reloj
        self._actividad = AvisosDeActividad(actividad)
        # El correo de invitación otra vez a quien no tiene cuenta (O2, 15 nov 2026)
        self._correos = correos
        self._user_uow = user_uow

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
            DraftInProgressError: Con la sala de draft abierta (O1)
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

            # 3. Reabrir inscripciones (la entidad valida la transición), con lo
            #    que arrastra: hándicaps a medias y partidas sin salir (#251, D1)
            reapertura = self._reapertura()
            borradas = await reapertura.reabrir(competition)

            # 4. Persistir cambios
            await self._uow.competitions.update(competition)

        # Sin partida no hay salida: se retiran sus avisos (G4)
        # y los de hándicaps con la RFEG dejan de ser ciertos (CodeRabbit, #864)
        await reapertura.avisar(competition, borradas)

        # 5. Retornar DTO de respuesta
        return ReopenEnrollmentsResponseDTO(
            id=competition.id.value,
            status=competition.status.value,
            reopened_at=competition.updated_at,
        )

    def _reapertura(self) -> Reapertura:
        return Reapertura(
            self._uow,
            self._zonas,
            self._reloj,
            self._actividad,
            correos=self._correos,
            user_uow=self._user_uow,
        )
