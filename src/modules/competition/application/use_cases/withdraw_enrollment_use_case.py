"""
Caso de Uso: Retirar Inscripción (Withdraw Enrollment).

Permite a un jugador aprobado retirarse de una competición.
"""

from collections.abc import Callable
from datetime import UTC, datetime

from src.modules.competition.application.dto.enrollment_dto import (
    WithdrawEnrollmentRequestDTO,
    WithdrawEnrollmentResponseDTO,
)
from src.modules.competition.application.exceptions import EnrollmentNotFoundError
from src.modules.competition.application.ports.competition_activity_publisher_interface import (
    CompetitionActivityPublisherInterface,
)
from src.modules.competition.application.ports.competition_timezone import ICompetitionTimezone
from src.modules.competition.application.services.avisos_de_actividad import AvisosDeActividad
from src.modules.competition.application.services.baja_de_la_competicion import (
    exigir_sin_draft_abierto,
    sacar_de_la_competicion,
)
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.value_objects.enrollment_id import EnrollmentId
from src.modules.user.domain.value_objects.user_id import UserId


class NotOwnerError(Exception):
    """Excepción lanzada cuando el usuario no es el dueño de la inscripción."""

    pass


class WithdrawEnrollmentUseCase:
    """
    Caso de uso para retirarse de una competición.

    Orquesta:
    1. Validación de existencia del enrollment
    2. Validación de que el solicitante es el dueño
    3. Ejecución del retiro
    4. Persistencia mediante UoW

    Reglas de negocio:
    - Solo el dueño del enrollment puede retirarse
    - Solo se puede retirar desde estado APPROVED
    - Diferencia con cancel: withdraw es después de estar inscrito
    """

    def __init__(
        self,
        uow: CompetitionUnitOfWorkInterface,
        zonas: ICompetitionTimezone | None = None,
        reloj: Callable[[], datetime] = lambda: datetime.now(UTC),
        actividad: CompetitionActivityPublisherInterface | None = None,
    ):
        """
        Constructor.

        Args:
            uow: Unit of Work para gestionar transacciones
            zonas: Para saber qué partidas ya salieron por su hora (#251). Sin ellas,
                solo cuenta el estado de la partida
            reloj: El momento de la retirada
            actividad: Los avisos de Actividad (BE-2); sin el, no se avisa
        """
        self._uow = uow
        self._zonas = zonas
        self._reloj = reloj
        self._actividad = AvisosDeActividad(actividad)

    async def execute(
        self, request: WithdrawEnrollmentRequestDTO, user_id: UserId
    ) -> WithdrawEnrollmentResponseDTO:
        """
        Ejecuta el caso de uso de retiro de inscripción.

        Args:
            request: DTO con enrollment_id y reason opcional
            user_id: ID del usuario que ejecuta la acción (debe ser el dueño)

        Returns:
            DTO con los datos de la inscripción retirada

        Raises:
            EnrollmentNotFoundError: Si la inscripción no existe
            NotOwnerError: Si el solicitante no es el dueño
            EnrollmentStateError: Si no se puede retirar desde el estado actual
        """
        async with self._uow:
            enrollment_id = EnrollmentId(request.enrollment_id)

            # 1. Obtener enrollment
            enrollment = await self._uow.enrollments.find_by_id(enrollment_id)
            if not enrollment:
                raise EnrollmentNotFoundError(f"Inscripción no encontrada: {request.enrollment_id}")

            # 2. Verificar que es el dueño
            if enrollment.user_id != user_id:
                raise NotOwnerError("Solo puedes retirarte de tu propia inscripción")

            # 3. La competicion, con su fila bloqueada ANTES de tocar la
            #    inscripcion: el mismo orden que al nombrar capitanes (BE #320).
            #    Si no, un capitan que se retira a la vez que lo nombran quedaria
            #    nombrado sin jugar
            competition = await self._uow.competitions.find_by_id_for_update(
                enrollment.competition_id
            )
            # Releída con el bloqueo: si el organizador le quitó mientras se
            # esperaba, aquí ya está retirada (revisor, release social 2)
            enrollment = await self._uow.enrollments.find_by_id_for_update(enrollment_id)
            if not enrollment:
                raise EnrollmentNotFoundError(f"Inscripción no encontrada: {request.enrollment_id}")

            # Con la sala de draft abierta nadie sale (decidido el 27 oct 2026)
            if competition is not None:
                await exigir_sin_draft_abierto(self._uow, competition.id)

            # 4. Withdraw (la entidad valida el estado)
            enrollment.withdraw(request.reason)

            # Sale de todo: partidas, franjas, capitanía y, si hace falta, los
            # equipos (release social 2)
            fotos = await sacar_de_la_competicion(
                self._uow, competition, enrollment, zonas=self._zonas, ahora=self._reloj()
            )

            # 5. Persistir cambios
            await self._uow.enrollments.update(enrollment)

        # 6. Ya guardado: sus amigos dejan de verlo apuntado (BE-2), y a quien
        #    se recoloca por su baja se le dice (G3)
        await self._actividad.left(enrollment.competition_id, enrollment.user_id)
        if competition is not None:
            for round_id, (antes, despues) in fotos.items():
                await self._actividad.salidas_cambiadas(competition, round_id, antes, despues)

        # 7. Retornar DTO
        return WithdrawEnrollmentResponseDTO(
            id=enrollment.id.value,
            competition_id=enrollment.competition_id.value,
            user_id=enrollment.user_id.value,
            status=enrollment.status.value,
            updated_at=enrollment.updated_at,
        )
