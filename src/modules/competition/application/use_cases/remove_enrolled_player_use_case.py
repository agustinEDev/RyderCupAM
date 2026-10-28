"""
Caso de Uso: el organizador quita a un inscrito (release social 2, 27 oct 2026).

Hasta ahora solo el propio jugador podía retirarse. El organizador (o un admin)
puede quitar a un aprobado antes de que empiece la competición, con los mismos
efectos que una retirada, y se le avisa en la app: «el organizador te ha
quitado de X». Después se le puede volver a invitar, o pedir plaza.
"""

from collections.abc import Callable
from datetime import UTC, datetime

from src.modules.competition.application.dto.enrollment_dto import (
    RemoveEnrolledPlayerRequestDTO,
    WithdrawEnrollmentResponseDTO,
)
from src.modules.competition.application.exceptions import (
    CompetitionNotFoundError,
    EnrollmentNotFoundError,
    NotCompetitionCreatorError,
)
from src.modules.competition.application.ports.competition_activity_publisher_interface import (
    CompetitionActivityPublisherInterface,
)
from src.modules.competition.application.ports.competition_timezone import ICompetitionTimezone
from src.modules.competition.application.services.avisos_de_actividad import AvisosDeActividad
from src.modules.competition.application.services.baja_de_la_competicion import (
    DraftInProgressError,
    exigir_sin_draft_abierto,
    sacar_de_la_competicion,
)
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.competition_status import CompetitionStatus
from src.modules.competition.domain.value_objects.enrollment_id import EnrollmentId
from src.modules.user.domain.value_objects.user_id import UserId

# Se reexporta: la ruta lo traduce a su codigo (409)
__all__ = [
    "CannotRemoveOrganizerError",
    "DraftInProgressError",
    "PlayerHasMatchesError",
    "RemovalNotAllowedError",
    "RemoveEnrolledPlayerUseCase",
]

# Antes de empezar (Q3). En juego ya están «Conceder partido» y retirar del fourball
_SE_PUEDE_QUITAR = frozenset(
    {CompetitionStatus.DRAFT, CompetitionStatus.ACTIVE, CompetitionStatus.CLOSED}
)

REMOVAL_NOT_ALLOWED = "REMOVAL_NOT_ALLOWED"
CANNOT_REMOVE_ORGANIZER = "CANNOT_REMOVE_ORGANIZER"
PLAYER_HAS_MATCHES = "PLAYER_HAS_MATCHES"


class RemovalNotAllowedError(Exception):
    """La competición ya empezó (o acabó): no se quita a nadie (Q3)."""

    error_code = REMOVAL_NOT_ALLOWED


class CannotRemoveOrganizerError(Exception):
    """El organizador no se quita a sí mismo (Q5)."""

    error_code = CANNOT_REMOVE_ORGANIZER


class PlayerHasMatchesError(Exception):
    """Ya hay partidos generados en la competición (Q4)."""

    error_code = PLAYER_HAS_MATCHES


class RemoveEnrolledPlayerUseCase:
    """El organizador (o un admin) quita a un inscrito aprobado."""

    def __init__(
        self,
        uow: CompetitionUnitOfWorkInterface,
        zonas: ICompetitionTimezone | None = None,
        reloj: Callable[[], datetime] = lambda: datetime.now(UTC),
        actividad: CompetitionActivityPublisherInterface | None = None,
    ):
        """
        Args:
            uow: Unit of Work para gestionar transacciones
            zonas: Para saber qué partidas ya salieron por su hora (#251)
            reloj: El momento de la baja
            actividad: Los avisos de Actividad; sin ellos, no se avisa
        """
        self._uow = uow
        self._zonas = zonas
        self._reloj = reloj
        self._actividad = AvisosDeActividad(actividad)

    async def execute(
        self, request: RemoveEnrolledPlayerRequestDTO, quien: UserId, is_admin: bool = False
    ) -> WithdrawEnrollmentResponseDTO:
        """
        Le quita de la competición.

        Args:
            request: La inscripción del jugador
            quien: Quien lo pide (el organizador)
            is_admin: Si quien lo pide es administrador

        Returns:
            La inscripción, ya retirada

        Raises:
            EnrollmentNotFoundError: Si la inscripción no existe
            CompetitionNotFoundError: Si su competición no existe
            NotCompetitionCreatorError: Si no es el organizador ni un admin
            CannotRemoveOrganizerError: Si es la del propio organizador
            RemovalNotAllowedError: Si la competición ya empezó
            PlayerHasMatchesError: Si ya hay partidos generados
            DraftInProgressError: Si la sala de draft está abierta
            EnrollmentStateError: Si no estaba aprobada (una solicitud se rechaza)
        """
        enrollment_id = request.enrollment_id
        async with self._uow:
            enrollment = await self._uow.enrollments.find_by_id(EnrollmentId(enrollment_id))
            if enrollment is None:
                raise EnrollmentNotFoundError(f"Inscripción no encontrada: {enrollment_id}")

            # Con su fila bloqueada, en el mismo orden que la retirada (BE #320)
            competition = await self._uow.competitions.find_by_id_for_update(
                enrollment.competition_id
            )
            if competition is None:
                raise CompetitionNotFoundError(
                    f"Competición no encontrada: {enrollment.competition_id}"
                )
            # Releída con el bloqueo: si se retiró mientras se esperaba, aquí ya
            # está retirada y no se le «quita» ni se le avisa (revisor)
            enrollment = await self._uow.enrollments.find_by_id_for_update(
                EnrollmentId(enrollment_id)
            )
            if enrollment is None:
                raise EnrollmentNotFoundError(f"Inscripción no encontrada: {enrollment_id}")
            if not is_admin and not competition.is_creator(quien):
                raise NotCompetitionCreatorError("Solo el organizador puede quitar a un inscrito")
            if enrollment.user_id == competition.creator_id:
                raise CannotRemoveOrganizerError("El organizador no se quita a sí mismo")
            if competition.status not in _SE_PUEDE_QUITAR:
                raise RemovalNotAllowedError(
                    f"No se quita a nadie de una competición en estado {competition.status.value}"
                )
            # Con partidos en cualquier sesión, no se quita a nadie (decidido el
            # 27 oct): los equipos ya no se deshacen y seguiría en el reparto
            if await self._hay_partidos(competition.id):
                raise PlayerHasMatchesError("Ya hay partidos generados")

            await exigir_sin_draft_abierto(self._uow, competition.id)

            # La entidad valida el estado: solo un aprobado
            enrollment.withdraw("removed_by_organizer")
            asignadas: list = []
            fotos = await sacar_de_la_competicion(
                self._uow,
                competition,
                enrollment,
                zonas=self._zonas,
                ahora=self._reloj(),
                asignadas=asignadas,
            )
            await self._uow.enrollments.update(enrollment)

        # Ya guardado: primero se va lo de estar apuntado, y luego su aviso (si
        # fuera al revés, `left` no lo borra, pero el orden lo deja claro)
        await self._actividad.left(enrollment.competition_id, enrollment.user_id)
        await self._actividad.removed(competition, enrollment)
        for round_id, (antes, despues) in fotos.items():
            await self._actividad.salidas_cambiadas(competition, round_id, antes, despues)
        # Y a quien la lista dio su plaza (A3)
        await self._actividad.desde_la_espera(competition, asignadas)

        return WithdrawEnrollmentResponseDTO(
            id=enrollment.id.value,
            competition_id=enrollment.competition_id.value,
            user_id=enrollment.user_id.value,
            status=enrollment.status.value,
            updated_at=enrollment.updated_at,
        )

    async def _hay_partidos(self, competition_id: CompetitionId) -> bool:
        """
        Si ya hay algún partido de Ryder generado (Q4).

        Args:
            competition_id: La competición

        Returns:
            True si alguna de sus sesiones tiene partidos
        """
        for sesion in await self._uow.rounds.find_by_competition(competition_id):
            if await self._uow.matches.find_by_round(sesion.id):
                return True
        return False
