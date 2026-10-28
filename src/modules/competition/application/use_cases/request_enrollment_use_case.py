"""
Caso de Uso: Apuntarse a una competicion publica (Request Enrollment).

Desde la release social 3 (tabla aprobada el 28 oct 2026) en una publica no se
pide plaza: se entra. En un stroke play con franjas se elige en el mismo paso
la franja con hueco, o la lista de espera de una llena; sin franjas montadas
(o en una Ryder) se entra con la barra y manda el maximo de jugadores.
"""

from datetime import UTC, datetime

from src.modules.competition.application.dto.enrollment_dto import (
    RequestEnrollmentRequestDTO,
    RequestEnrollmentResponseDTO,
)
from src.modules.competition.application.exceptions import (
    CompetitionFullError,
    CompetitionNotFoundError,
    InvalidTeeColorError,
)
from src.modules.competition.application.ports.competition_activity_publisher_interface import (
    CompetitionActivityPublisherInterface,
)
from src.modules.competition.application.ports.competition_timezone import ICompetitionTimezone
from src.modules.competition.application.services import equipos_que_cambian
from src.modules.competition.application.services.avisos_de_actividad import AvisosDeActividad
from src.modules.competition.application.services.baja_de_la_competicion import (
    exigir_sin_draft_abierto,
)
from src.modules.competition.application.services.cupo_de_la_competicion import (
    al_entrar_uno,
    exigir_sitio,
)
from src.modules.competition.application.services.enrollment_opener import EnrollmentOpener
from src.modules.competition.application.services.esperas_de_la_competicion import (
    EsperasDeLaCompeticion,
)
from src.modules.competition.application.services.genero_obligatorio import exigir_genero
from src.modules.competition.application.services.handicap_obligatorio import exigir_handicap
from src.modules.competition.application.services.inscripcion_que_vuelve import (
    guardar_la_inscripcion,
    viva,
)
from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.entities.enrollment import Enrollment
from src.modules.competition.domain.entities.espera_en_franja import EsperaEnFranja
from src.modules.competition.domain.entities.invitation import Invitation
from src.modules.competition.domain.entities.plaza_en_franja import PlazaEnFranja
from src.modules.competition.domain.entities.round import Round
from src.modules.competition.domain.exceptions.competition_violations import (
    CompetitionFullViolation,
    DuplicateEnrollmentViolation,
    EnrollmentPastStartDateViolation,
    InvalidCompetitionStatusViolation,
    InvalidInvitationStatusViolation,
    InvitationExpiredViolation,
    MaxEnrollmentsExceededViolation,
)
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.services.competition_policy import (
    MAX_ENROLLMENTS_PER_USER,
    CompetitionPolicy,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.competition_status import CompetitionStatus
from src.modules.competition.domain.value_objects.enrollment_status import EnrollmentStatus
from src.modules.competition.domain.value_objects.round_id import RoundId
from src.modules.golf_course.domain.value_objects.tee_color import TeeColor
from src.modules.user.domain.repositories.user_repository_interface import (
    UserRepositoryInterface,
)
from src.modules.user.domain.value_objects.user_id import UserId


class CompetitionNotActiveError(Exception):
    """Excepcion lanzada cuando la competicion no esta en estado ACTIVE."""

    pass


class CompetitionIsPrivateError(Exception):
    """En una competicion privada se entra porque el organizador invita.

    Pedir plaza por cuenta propia solo vale en las publicas (BE #318).
    """

    pass


class AlreadyEnrolledError(Exception):
    """Excepcion lanzada cuando el usuario ya tiene una inscripcion en esta competicion."""

    pass


# Los «no» de la política que antes se escapaban sin traducir y llegaban como un
# 500 mudo: sin cabeceras de CORS, el navegador lo ve como un fallo de red y el
# jugador no se entera de nada (BE #372). El de «llena» es compartido con aprobar
class EnrollmentClosedError(Exception):
    """El torneo ya ha empezado: pasado su primer día no se pide plaza."""


class TooManyEnrollmentsError(Exception):
    """Quien pide ya está en el máximo de competiciones a la vez."""


class TeeWindowRequiredError(Exception):
    """En un stroke play con franjas se entra eligiendo una suya (D4, D16)."""


class TeeWindowNotFoundError(Exception):
    """La franja elegida no es una de las de esta competición (D16)."""


class TeeWindowFullError(Exception):
    """La franja elegida está llena y no se pidió su lista de espera (D5)."""


class TeeWindowHasRoomError(Exception):
    """Se pidió la espera de una franja con hueco: que coja plaza (D7)."""


class RequestEnrollmentUseCase:
    """
    Apuntarse a una competicion publica: se entra directamente (28 oct 2026).

    Reglas:
    - Solo en una publica y con las inscripciones abiertas; una programada a la
      que ya le toca se abre aqui mismo (D10).
    - Las de siempre: genero, hándicap en stroke play, sin otra inscripcion
      viva y como mucho en `MAX_ENROLLMENTS_PER_USER` a la vez.
    - Con franjas: plaza en la elegida o su espera si esta llena; el maximo de
      jugadores no se mira (D8). Sin franjas, el maximo de jugadores (D1, D2).
    - Una invitacion pendiente suya a esa competicion queda aceptada (D14).
    """

    def __init__(
        self,
        uow: CompetitionUnitOfWorkInterface,
        user_repository: UserRepositoryInterface,
        zonas: ICompetitionTimezone | None = None,
        actividad: CompetitionActivityPublisherInterface | None = None,
    ):
        """
        Args:
            uow: Unit of Work para gestionar transacciones
            user_repository: El genero, el hándicap y el correo de quien entra
            zonas: Para abrir una programada a la que ya le toca (D10)
            actividad: Los avisos al organizador y a los amigos (A1, A2)
        """
        self._uow = uow
        # El género es obligatorio para apuntarse (#710)
        self._user_repo = user_repository
        self._zonas = zonas
        self._actividad = AvisosDeActividad(actividad)

    async def execute(self, request: RequestEnrollmentRequestDTO) -> RequestEnrollmentResponseDTO:
        """
        Raises:
            CompetitionNotFoundError, CompetitionIsPrivateError,
            CompetitionNotActiveError, CompetitionFullError, AlreadyEnrolledError,
            EnrollmentClosedError, TooManyEnrollmentsError, InvalidTeeColorError,
            TeeWindowRequiredError, TeeWindowNotFoundError, TeeWindowFullError,
            TeeWindowHasRoomError
        """
        async with self._uow:
            competition_id = CompetitionId(request.competition_id)
            user_id = UserId(request.user_id)

            # Con la fila bloqueada, como al empezarla: si no, una inscripción que
            # valida «abierta» mientras otra transacción la cierra entraba tarde
            # (CodeRabbit, BE #624); y dos a la vez por la última plaza, una (D16)
            competition = await self._uow.competitions.find_by_id_for_update(competition_id)
            if not competition:
                raise CompetitionNotFoundError(
                    f"Competicion no encontrada: {request.competition_id}"
                )

            # En una privada se entra porque te invitan (BE #318)
            if not competition.accepts_enrollment_requests():
                raise CompetitionIsPrivateError(
                    f"La competición {request.competition_id} es privada: "
                    f"solo se entra por invitación."
                )

            # La programada a la que ya le toca se abre aquí: si no, quien llega
            # antes que nadie abra la ficha se quedaba fuera (D10)
            await EnrollmentOpener.abrir_las_que_toquen([competition], self._uow, self._zonas)
            # Cerradas las inscripciones nadie entra solo; el organizador sí (D11)
            if competition.status is not CompetitionStatus.ACTIVE:
                raise CompetitionNotActiveError(
                    "Las inscripciones de esta competición no están abiertas."
                )

            # Antes que la franja: a quien ya está se le dice eso (revisor, 28 oct)
            existing_enrollment = await self._uow.enrollments.find_by_user_and_competition(
                user_id, competition_id
            )
            await self._exigir_que_puede(competition, user_id, existing_enrollment)

            franjas = [
                s
                for s in await self._uow.rounds.find_by_competition(competition_id)
                if s.hoja_de_salidas is not None
            ]
            franja = self._la_elegida(request, franjas)
            # Sin franjas manda el máximo de jugadores (D1, D2); con ellas, sus plazas
            try:
                aprobadas_antes = await exigir_sitio(self._uow, competition)
            except CompetitionFullViolation as e:
                raise CompetitionFullError(
                    f"La competición está completa: {competition.max_players} plazas ocupadas."
                ) from e

            # Sin género no se sabe desde qué barras juega (#710)
            await exigir_genero(self._user_repo, user_id, es_quien_se_apunta=True)
            # Y en un Stableford o un Medal, su hándicap: de él sale su categoría (#251)
            await exigir_handicap(self._user_repo, competition, user_id, es_quien_se_apunta=True)

            try:
                tee_color = TeeColor(request.tee_color) if request.tee_color else None
            except ValueError as e:
                raise InvalidTeeColorError(
                    f"Valor de tee_color no válido: '{request.tee_color}'. "
                    f"Valores permitidos: {[c.value for c in TeeColor]}"
                ) from e

            espera = False
            if franja is not None:
                espera = await self._plaza_o_espera(competition, franja, user_id, request)

            enrollment = await self._guardar(
                existing_enrollment, competition_id, user_id, tee_color
            )
            if espera:
                # Entró esperando: si se queda sin plaza ni espera, sale (W2, A4)
                enrollment.entra_esperando()
                await self._uow.enrollments.update(enrollment)
            # Con los equipos formados queda sin equipo (T1, T4, 28 oct 2026)
            # Con la sala de draft abierta no entra nadie: no se enteraría (T6)
            await exigir_sin_draft_abierto(self._uow, competition.id)
            capitanes = await equipos_que_cambian.al_entrar(self._uow, competition)
            aceptada = await self._aceptar_su_invitacion(competition, user_id)
            cerradas = await al_entrar_uno(self._uow, competition, aprobadas_antes)

        # Ya guardado: lo que se le cuenta a cada uno (A1, A2)
        if aceptada is not None:
            await self._actividad.invitation_answered(aceptada)
        await self._actividad.invitations_closed(cerradas)
        await self._actividad.joined(competition, enrollment, franja, espera)
        await self._actividad.teams_changed(competition, capitanes)
        # Solo en espera aún no juega: sus amigos se enteran cuando tenga plaza
        if not espera:
            await self._actividad.enrolled(competition, enrollment, accepted_request=False)

        return RequestEnrollmentResponseDTO(
            id=enrollment.id.value,
            competition_id=enrollment.competition_id.value,
            user_id=enrollment.user_id.value,
            status=enrollment.status.value,
            created_at=enrollment.created_at,
            round_id=franja.id.value if franja is not None else None,
            waiting=espera,
        )

    @staticmethod
    def _la_elegida(request: RequestEnrollmentRequestDTO, franjas: list[Round]) -> Round | None:
        """La franja elegida entre las suyas; con franjas, elegir una es obligatorio (D4)."""
        if request.round_id is None:
            if franjas or request.waiting_list:
                raise TeeWindowRequiredError(
                    "Elige una franja para apuntarte, o la lista de espera de una llena."
                )
            return None
        elegida = RoundId(request.round_id)
        for franja in franjas:
            if franja.id == elegida:
                return franja
        raise TeeWindowNotFoundError("Esa franja no es de esta competición.")

    async def _guardar(
        self,
        existente: Enrollment | None,
        competition_id: CompetitionId,
        user_id: UserId,
        tee_color: TeeColor | None,
    ) -> Enrollment:
        """
        Con su inscripción cerrada, si la tiene (release social 2). Una solicitud
        pendiente de antes de la inscripción directa entra ya (code-review, 28 oct).
        """
        if existente is not None and existente.status is EnrollmentStatus.REQUESTED:
            existente.approve()
            if tee_color is not None:
                existente.set_tee_color(tee_color)
            await self._uow.enrollments.update(existente)
            return existente
        return await guardar_la_inscripcion(
            self._uow,
            existente,
            aprobada=True,
            competition_id=competition_id,
            user_id=user_id,
            tee_color=tee_color,
        )

    async def _exigir_que_puede(self, competition: Competition, user_id: UserId, existente) -> None:
        """Duplicados, límite por jugador y fecha, con los «no» traducidos (BE #372)."""
        user_total_enrollments = await self._uow.enrollments.count_active_by_user(user_id)
        try:
            CompetitionPolicy.can_enroll(
                user_id=user_id,
                competition_id=competition.id,
                # Una cerrada no impide volver: se reutiliza (release social 2); una
                # solicitud pendiente de antes tampoco: entra (code-review, 28 oct)
                existing_enrollment_id=(
                    str(existente.id.value)
                    if viva(existente) and existente.status is not EnrollmentStatus.REQUESTED
                    else None
                ),
                competition_status=competition.status,
                competition_start_date=competition.dates.start_date,
                user_total_enrollments=user_total_enrollments,
            )
        except DuplicateEnrollmentViolation as e:
            raise AlreadyEnrolledError(str(e)) from e
        except InvalidCompetitionStatusViolation as e:
            raise CompetitionNotActiveError(str(e)) from e
        except EnrollmentPastStartDateViolation as e:
            raise EnrollmentClosedError(
                "El torneo ya ha empezado: no se admiten más inscripciones."
            ) from e
        except MaxEnrollmentsExceededViolation as e:
            raise TooManyEnrollmentsError(
                f"Ya estás en {MAX_ENROLLMENTS_PER_USER} competiciones, el máximo a la vez."
            ) from e

    async def _plaza_o_espera(
        self,
        competition: Competition,
        franja: Round,
        user_id: UserId,
        request: RequestEnrollmentRequestDTO,
    ) -> bool:
        """Su plaza en la franja, o su sitio en la espera si está llena (D3, D5-D7)."""
        # Solo llegan franjas con hoja (las filtra `execute`)
        cupo = franja.hoja_de_salidas.cupo if franja.hoja_de_salidas else 0
        plazas = await self._uow.plazas.de_la_competicion(competition.id)
        llena = sum(1 for p in plazas if p.round_id == franja.id) >= cupo
        ahora = datetime.now(UTC)
        if request.waiting_list:
            if not llena:
                raise TeeWindowHasRoomError("Queda sitio en esa franja: coge plaza directamente.")
            await self._uow.esperas.add(
                EsperaEnFranja.crear(competition.id, franja.id, user_id, ahora)
            )
            return True
        if llena:
            raise TeeWindowFullError(
                "Esa franja está llena: apúntate a su lista de espera o elige otra."
            )
        await self._uow.plazas.add(PlazaEnFranja.crear(competition.id, franja.id, user_id, ahora))
        # Con plaza ese día, fuera de las listas de ese día
        await EsperasDeLaCompeticion(self._uow).tras_coger(competition, user_id)
        return False

    async def _aceptar_su_invitacion(
        self, competition: Competition, user_id: UserId
    ) -> Invitation | None:
        """La invitación pendiente que tenía a esa competición queda aceptada (D14)."""
        usuario = await self._user_repo.find_by_id(user_id)
        correo = str(usuario.email.value) if usuario is not None and usuario.email else None
        pendiente = await self._uow.invitations.pendiente_de(
            user_id, correo, competition.id, datetime.now()
        )
        if pendiente is None:
            return None
        invitacion = await self._uow.invitations.find_by_id_for_update(pendiente.id)
        if invitacion is None:
            return None
        try:
            invitacion.accept()
        except (InvitationExpiredViolation, InvalidInvitationStatusViolation):
            # Caducó entre leerla y aceptarla: entra igual, sin ella (code-review)
            return None
        await self._uow.invitations.update(invitacion)
        return invitacion
