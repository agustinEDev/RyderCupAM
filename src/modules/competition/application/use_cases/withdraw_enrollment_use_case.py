"""
Caso de Uso: Retirar Inscripción (Withdraw Enrollment).

Permite a un jugador aprobado retirarse de una competición.
"""

from datetime import UTC, datetime

from src.modules.competition.application.dto.enrollment_dto import (
    WithdrawEnrollmentRequestDTO,
    WithdrawEnrollmentResponseDTO,
)
from src.modules.competition.application.exceptions import EnrollmentNotFoundError
from src.modules.competition.application.services.esperas_de_la_competicion import (
    EsperasDeLaCompeticion,
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

    def __init__(self, uow: CompetitionUnitOfWorkInterface):
        """
        Constructor.

        Args:
            uow: Unit of Work para gestionar transacciones
        """
        self._uow = uow

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

            # 4. Withdraw (la entidad valida el estado)
            enrollment.withdraw(request.reason)

            # Y suelta sus plazas en las franjas de un stroke play, si aún no se
            # juega: empezada, son las del historial de lo jugado (#251)
            if competition is not None and competition.status.allows_tee_window_edits():
                suyas = [
                    p.round_id
                    for p in await self._uow.plazas.de_la_competicion(enrollment.competition_id)
                    if p.user_id == enrollment.user_id
                ]
                await self._uow.plazas.quitar_del_jugador(
                    enrollment.competition_id, enrollment.user_id
                )
                # Fuera de las listas, y sus plazas para los que esperan
                esperas = EsperasDeLaCompeticion(self._uow)
                await esperas.sacar_de_todas(competition, enrollment.user_id)
                for round_id in suyas:
                    await esperas.rellenar(competition, round_id, datetime.now(UTC))

            #    Si era capitan, su puesto queda libre
            if competition and competition.handle_withdrawal(enrollment.user_id):
                await self._uow.competitions.update(competition)

            # 5. Persistir cambios
            await self._uow.enrollments.update(enrollment)

        # 6. Retornar DTO
        return WithdrawEnrollmentResponseDTO(
            id=enrollment.id.value,
            competition_id=enrollment.competition_id.value,
            user_id=enrollment.user_id.value,
            status=enrollment.status.value,
            updated_at=enrollment.updated_at,
        )
