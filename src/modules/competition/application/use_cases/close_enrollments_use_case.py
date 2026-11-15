"""
Caso de Uso: Cerrar Inscripciones de Competition.

Permite cerrar las inscripciones de una competición (ACTIVE → CLOSED).
Solo el creador puede realizar esta acción.
"""

from dataclasses import dataclass

from src.modules.competition.application.dto.competition_dto import (
    CloseEnrollmentsRequestDTO,
    CloseEnrollmentsResponseDTO,
)
from src.modules.competition.application.exceptions import (
    CompetitionNotFoundError,
    NotCompetitionCreatorError,
)
from src.modules.competition.application.ports.competition_activity_publisher_interface import (
    CompetitionActivityPublisherInterface,
)
from src.modules.competition.application.ports.lanzador_de_actualizaciones import (
    LanzadorDeActualizaciones,
)
from src.modules.competition.application.services.actualizaciones_de_handicaps import (
    ActualizacionesDeHandicaps,
)
from src.modules.competition.application.services.avisos_de_actividad import AvisosDeActividad
from src.modules.competition.application.services.franjas_al_cerrar import FranjasAlCerrar
from src.modules.competition.application.services.handicaps_al_cerrar import HandicapsAlCerrar
from src.modules.competition.application.services.invitaciones_al_cerrar import (
    sin_plaza_para_las_pendientes,
)
from src.modules.competition.application.services.plazo_de_inscripcion import (
    PlazoDeInscripcion,
)
from src.modules.competition.domain.entities.actualizacion_de_handicaps import (
    ActualizacionDeHandicaps,
)
from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.entities.enrollment import Enrollment
from src.modules.competition.domain.entities.invitation import Invitation
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.competition_status import CompetitionStatus
from src.modules.user.domain.repositories.user_repository_interface import (
    UserRepositoryInterface,
)
from src.modules.user.domain.value_objects.user_id import UserId


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

    def __init__(
        self,
        uow: CompetitionUnitOfWorkInterface,
        user_repository: UserRepositoryInterface | None = None,
        lanzador: LanzadorDeActualizaciones | None = None,
        actividad: CompetitionActivityPublisherInterface | None = None,
        plazo: PlazoDeInscripcion | None = None,
    ):
        """
        Constructor.

        Args:
            uow: Unit of Work para gestionar transacciones
            plazo: Para cerrar por el plazo (15 nov 2026); a mano no hace falta
        """
        self._uow = uow
        self._plazo = plazo
        # Los avisos de Actividad: las invitaciones que se cierran (22 oct 2026)
        self._actividad = AvisosDeActividad(actividad)
        # Para el hándicap de cada inscrito en un stroke play (#251)
        self._users = user_repository
        # El refresco con la RFEG en segundo plano; sin él, no hay (fuera de producción)
        self._actualizaciones = ActualizacionesDeHandicaps(uow, lanzador)

    async def execute(
        self, request: CloseEnrollmentsRequestDTO, user_id: UserId, is_admin: bool = False
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
            PlayersWithoutHandicapError: Si en un stroke play falta el de alguien
                (no se cierra)
        """
        async with self._uow:
            # 1. Buscar la competición
            competition_id = CompetitionId(request.competition_id)
            # Con la fila bloqueada, como al nombrar capitanes: una aceptación a
            # la vez leería «abierta» y entraría tras el cierre (#710)
            competition = await self._uow.competitions.find_by_id_for_update(competition_id)

            if not competition:
                raise CompetitionNotFoundError(
                    f"No existe competición con ID {request.competition_id}"
                )

            # 2. Verificar que el usuario sea el creador
            if not is_admin and not competition.is_creator(user_id):
                raise NotCompetitionCreatorError("Solo el creador puede cerrar las inscripciones")

            cierre = await self._cerrar(competition, por_el_plazo=False)

        return await self._despues(cierre)

    async def cerrar_por_el_plazo(
        self, competition_id: CompetitionId
    ) -> CloseEnrollmentsResponseDTO | None:
        """
        Las cierra el plazo, a las 12:00 del día anterior (C3, 15 nov 2026): este
        mismo caso de uso, para que pase todo lo que pasa al cerrar a mano.

        Se mira otra vez con la fila bloqueada: entre leerla y cerrarla, el
        organizador puede haberla cerrado, reabierto o movido de fecha.

        Returns:
            La respuesta, o None si ya no le toca (o ya no existe)

        Raises:
            PlayersWithoutTeeWindowError, PlayersWithoutHandicapError: Un stroke
                play que no se puede cerrar (no se cierra, C4)
        """
        if self._plazo is None:
            raise RuntimeError("Hace falta el plazo para cerrar por el plazo")
        async with self._uow:
            competition = await self._uow.competitions.find_by_id_for_update(competition_id)
            if competition is None or not await self._plazo.le_toca_cerrarse(competition):
                return None
            cierre = await self._cerrar(competition, por_el_plazo=True)

        return await self._despues(cierre)

    async def _cerrar(self, competition: Competition, por_el_plazo: bool) -> "_Cierre":
        """Lo que se hace dentro de la transacción, con la competición bloqueada."""
        sin_sitio: list[Enrollment] = []
        # 4. En un Stableford o un Medal se fija el hándicap de cada uno, el de
        #    todo el torneo (7 oct 2026, como la RFEG), y si falta alguno no se
        #    cierra. Solo al cerrar DESDE ABIERTA: este mismo paso devuelve a
        #    cerrada una competición en juego, y ahí no se puede volver a fijar
        #    nada a mitad de torneo. Y antes de cerrar: si no se puede, lo que
        #    hay que decir es el estado
        if competition.stroke_play is not None and competition.status is CompetitionStatus.ACTIVE:
            # Quien sigue solo en espera se queda sin plaza y sale (A4, 28 oct
            # 2026); después, que cada aprobado tenga su franja (8 oct 2026)
            sin_sitio = await FranjasAlCerrar(self._uow, self._usuarios()).al_cerrar(competition)
            await self._handicaps().fijar(competition)

        # 3. Contar inscripciones aprobadas: tras sacar a los que esperaban
        total_enrollments = await self._uow.enrollments.count_approved(competition.id)

        # 4b. Cerrar inscripciones (la entidad valida la transición), diciendo si
        #     las cierra el plazo (C3, R3)
        desde_abierta = competition.status is CompetitionStatus.ACTIVE
        # Con la fila bloqueada: el aviso de «no se puede cerrar» se apunta con
        # ella bloqueada al publicarlo, así que aquí se ve si lo hay (D4, D7)
        estaba_avisada = competition.close_blocked_notified
        competition.close_enrollments(total_enrollments=total_enrollments, by_deadline=por_el_plazo)

        # 4c. Al cerrar desde ABIERTA se pregunta a la RFEG por todos, en segundo
        #     plano: una actualización nueva, y la anterior a medias se corta (#251)
        actualizacion = None
        if desde_abierta:
            actualizacion = await self._actualizaciones.al_cerrar(competition.id)

        # 5. Persistir cambios
        await self._uow.competitions.update(competition)

        # 5b. Las listas de espera solo funcionan con las inscripciones abiertas (#251)
        if desde_abierta:
            await self._uow.esperas.vaciar(competition.id)

        # 6. Las invitaciones pendientes se quedan sin plaza (#710)
        sin_plaza = await sin_plaza_para_las_pendientes(self._uow, competition.id)
        return _Cierre(
            competition,
            total_enrollments,
            sin_sitio,
            sin_plaza,
            actualizacion,
            por_el_plazo,
            estaba_avisada,
        )

    async def _despues(self, cierre: "_Cierre") -> CloseEnrollmentsResponseDTO:
        """Ya guardado: lo que se lanza y se avisa, y la respuesta."""
        competition = cierre.competition
        # 7. Ya guardada, se lanza: la respuesta no espera a la RFEG
        self._actualizaciones.lanzar(cierre.actualizacion)
        # Y las invitaciones cerradas retiran su aviso de invitado (22 oct 2026)
        await self._actividad.invitations_closed(cierre.sin_plaza)
        # Quien se quedó en espera: «no hubo plaza» (A4)
        for inscripcion in cierre.sin_sitio:
            await self._actividad.left(competition.id, inscripcion.user_id)
        await self._actividad.no_place(competition, cierre.sin_sitio)
        # Y al organizador, si las cerró el plazo: «se han cerrado» (C5)
        if cierre.por_el_plazo:
            await self._actividad.enrollments_closed(competition)
        # Y el «no se puede cerrar», si se le dio, ya no pide nada (C4, D7)
        if cierre.estaba_avisada:
            await self._actividad.close_block_withdrawn(competition)

        # 7. Retornar DTO de respuesta
        return CloseEnrollmentsResponseDTO(
            id=competition.id.value,
            status=competition.status.value,
            total_enrollments=cierre.total_enrollments,
            closed_at=competition.updated_at,
        )

    def _usuarios(self) -> UserRepositoryInterface:
        if self._users is None:
            raise RuntimeError("Hace falta el repositorio de usuarios para un stroke play")
        return self._users

    def _handicaps(self) -> HandicapsAlCerrar:
        return HandicapsAlCerrar(self._uow, self._usuarios())


@dataclass(frozen=True)
class _Cierre:
    """Lo que deja hecho el cierre dentro de la transacción, para después."""

    competition: Competition
    total_enrollments: int
    sin_sitio: list[Enrollment]
    sin_plaza: list[Invitation]
    actualizacion: ActualizacionDeHandicaps | None
    por_el_plazo: bool
    estaba_avisada: bool
