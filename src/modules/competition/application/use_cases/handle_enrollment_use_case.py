"""
Caso de Uso: Manejar Solicitud de Inscripción (Handle Enrollment).

Permite al creador aprobar o rechazar una solicitud de inscripción.
"""

from src.modules.competition.application.dto.enrollment_dto import (
    HandleEnrollmentRequestDTO,
    HandleEnrollmentResponseDTO,
)
from src.modules.competition.application.exceptions import (
    CompetitionFullError,
    CompetitionNotFoundError,
    EnrollmentNotFoundError,
    NotCreatorError,
)
from src.modules.competition.application.ports.competition_activity_publisher_interface import (
    CompetitionActivityPublisherInterface,
)
from src.modules.competition.application.services.avisos_de_actividad import AvisosDeActividad
from src.modules.competition.application.services.cupo_de_la_competicion import (
    al_entrar_uno,
    exigir_sitio,
)
from src.modules.competition.application.services.equipos_formados import (
    reiniciar_para_que_entre,
)
from src.modules.competition.application.services.genero_obligatorio import exigir_genero
from src.modules.competition.application.services.handicap_obligatorio import exigir_handicap
from src.modules.competition.domain.entities.enrollment import EnrollmentStateError
from src.modules.competition.domain.entities.invitation import Invitation
from src.modules.competition.domain.exceptions.competition_violations import (
    CompetitionFullViolation,
)
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.value_objects.enrollment_id import EnrollmentId
from src.modules.competition.domain.value_objects.enrollment_status import EnrollmentStatus
from src.modules.user.domain.repositories.user_repository_interface import (
    UserRepositoryInterface,
)
from src.modules.user.domain.value_objects.user_id import UserId


class InvalidActionError(Exception):
    """Excepción lanzada cuando la acción no es válida."""

    pass


class HandleEnrollmentUseCase:
    """
    Caso de uso para aprobar o rechazar solicitudes de inscripción.

    Orquesta:
    1. Validación de existencia del enrollment
    2. Validación de existencia de la competición
    3. Validación de que el solicitante es el creador
    4. Ejecución de la acción (approve/reject)
    5. Persistencia mediante UoW

    Reglas de negocio:
    - Solo el creador puede aprobar/rechazar
    - El enrollment debe estar en estado REQUESTED o INVITED
    - Las acciones válidas son APPROVE y REJECT
    """

    def __init__(
        self,
        uow: CompetitionUnitOfWorkInterface,
        user_repository: UserRepositoryInterface,
        actividad: CompetitionActivityPublisherInterface | None = None,
    ):
        """
        Constructor.

        Args:
            uow: Unit of Work para gestionar transacciones
            actividad: Los avisos de Actividad (BE-2); sin el, no se avisa
        """
        self._uow = uow
        # Aprobar tambien exige el genero: la solicitud pudo ser de antes de la
        # regla, o quien la hizo pudo borrarlo luego (#710)
        self._user_repo = user_repository
        self._actividad = AvisosDeActividad(actividad)

    async def execute(
        self, request: HandleEnrollmentRequestDTO, creator_id: UserId, is_admin: bool = False
    ) -> HandleEnrollmentResponseDTO:
        """
        Ejecuta el caso de uso de manejo de inscripción.

        Args:
            request: DTO con enrollment_id y action (APPROVE/REJECT)
            creator_id: ID del usuario que ejecuta la acción (debe ser el creador)

        Returns:
            DTO con los datos de la inscripción actualizada

        Raises:
            EnrollmentNotFoundError: Si la inscripción no existe
            CompetitionNotFoundError: Si la competición no existe
            NotCreatorError: Si el solicitante no es el creador
            InvalidActionError: Si la acción no es válida
            EnrollmentStateError: Si la transición de estado no es válida
        """
        async with self._uow:
            enrollment_id = EnrollmentId(request.enrollment_id)

            # 1. Obtener enrollment
            enrollment = await self._uow.enrollments.find_by_id(enrollment_id)
            if not enrollment:
                raise EnrollmentNotFoundError(f"Inscripción no encontrada: {request.enrollment_id}")

            # 2. Obtener competición con bloqueo de fila (previene TOCTOU en validación de capacidad)
            competition = await self._uow.competitions.find_by_id_for_update(
                enrollment.competition_id
            )
            if not competition:
                raise CompetitionNotFoundError(
                    f"Competición no encontrada: {enrollment.competition_id}"
                )

            # 2b. Releerla ya con el bloqueo: si la competición empezó mientras se
            #     esperaba, la solicitud está rechazada y aprobarla la pisaría
            enrollment = await self._uow.enrollments.find_by_id_for_update(enrollment_id)
            if not enrollment:
                raise EnrollmentNotFoundError(f"Inscripción no encontrada: {request.enrollment_id}")

            # 3. Verificar que es el creador
            if not is_admin and competition.creator_id != creator_id:
                raise NotCreatorError(
                    "Solo el creador de la competición puede aprobar o rechazar inscripciones"
                )

            # 4. Ejecutar acción. Solo una solicitud se avisa como aceptada o
            #    rechazada: una invitación tiene su propio camino
            era_solicitud = enrollment.status == EnrollmentStatus.REQUESTED
            sin_plaza: list[Invitation] = []
            if request.action == "APPROVE":
                # Verificar capacidad antes de aprobar
                # Con franjas, el cupo es de sus plazas (28 oct 2026)
                try:
                    approved_count = await exigir_sitio(self._uow, competition)
                except CompetitionFullViolation as e:
                    raise CompetitionFullError(
                        f"La competición está completa: {competition.max_players} plazas ocupadas."
                    ) from e
                # En un Stableford o un Medal, con las inscripciones cerradas ya no
                # entra nadie: su hándicap y su categoría están fijados (#251)
                if competition.stroke_play is not None and not (
                    competition.status.allows_modifications()
                ):
                    raise EnrollmentStateError(
                        "Las inscripciones están cerradas: para que entre, reábrelas, "
                        "apruébala y vuelve a cerrarlas."
                    )
                await exigir_genero(self._user_repo, enrollment.user_id, es_quien_se_apunta=False)
                await exigir_handicap(
                    self._user_repo,
                    competition,
                    enrollment.user_id,
                    es_quien_se_apunta=False,
                    personalizado=enrollment.custom_handicap,
                )
                # Entra con los equipos formados y sin partidos: se reinician, como
                # al quitar a alguien (27 oct 2026); con partidos, no entra (30 oct)
                await reiniciar_para_que_entre(self._uow, competition)
                enrollment.approve()
                # Si era la última plaza, las invitaciones pendientes se quedan sin
                # ella ya (BE #359)
                sin_plaza = await al_entrar_uno(self._uow, competition, approved_count)
            elif request.action == "REJECT":
                enrollment.reject()
            else:
                raise InvalidActionError(
                    f"Acción no válida: {request.action}. Use 'APPROVE' o 'REJECT'"
                )

            # 5. Persistir cambios
            await self._uow.enrollments.update(enrollment)

        # 6. Ya guardado, a Actividad: aceptado (y sus amigos, si es público) o
        #    rechazado a mano (BE-2)
        if request.action == "APPROVE":
            await self._actividad.enrolled(competition, enrollment, accepted_request=era_solicitud)
            # Las pendientes que se quedaron sin plaza retiran su aviso (22 oct)
            await self._actividad.invitations_closed(sin_plaza)
        elif era_solicitud:
            await self._actividad.request_rejected(competition, enrollment)

        # 7. Retornar DTO
        return HandleEnrollmentResponseDTO(
            id=enrollment.id.value,
            competition_id=enrollment.competition_id.value,
            user_id=enrollment.user_id.value,
            status=enrollment.status.value,
            updated_at=enrollment.updated_at,
        )
