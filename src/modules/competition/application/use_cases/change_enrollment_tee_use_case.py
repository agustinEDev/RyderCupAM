"""
Caso de Uso: cambiar las barras de una inscripción (BE #912, 20 nov 2026).

Una jugadora invitada se quedaba en las barras por defecto aunque el campo no
las tuviera valoradas para ella, y nadie podía cambiárselas: la generación de
partidos se bloqueaba sin salida. Decidido con Agustín:

- Antes de empezar: el propio jugador, el capitán de SU equipo, el organizador
  o un admin. Ya empezada: el capitán de su equipo, el organizador o un admin
  (para desbloquear la sesión 2 de una Ryder, que se genera ya empezada); la
  capitana, también las suyas. Terminada o cancelada: nadie. Sin equipos
  formados no hay capitanes, y el subcapitán no cuenta.
- No se cambia lo ya jugado, pero sí lo que queda por jugar. En sus partidos de
  Ryder sin empezar y sus partidas de stroke play que aún no salieron («tienen
  golpes o les llegó su hora», #544) cambia SU barra y lo que depende de ella;
  los demás se quedan como se generaron (su barra y su hándicap índice
  guardados). Lo que se genere después ya sale con las nuevas.
- Si sus barras nuevas no están valoradas en el campo de algo pendiente: 422,
  y no cambia nada. Si lo que falla es de otro (su barra guardada, el campo, la
  franja), 409 con un código fijo, sin datos de nadie.
- Solo barras valoradas para su género, o sin género, en alguno de los campos
  de la competición; en SCRATCH valen también las que solo tienen tarjeta. Sin
  género en el perfil, solo las mixtas.
- Sin barras (null) vuelve a las habituales de su género.

Quién se comprueba antes de bloquear nada, y otra vez tras bloquear (el estado
pudo cambiar). Los bloqueos, en el orden de siempre: la competición, la
inscripción y sus partidos. Todo se calcula antes de escribir: si algo falla,
no se ha tocado nada, y el rollback de la unidad de trabajo cubre el resto.
"""

import logging
from collections.abc import Callable
from datetime import datetime

from src.modules.competition.application.dto.enrollment_dto import (
    ChangeEnrollmentTeeRequestDTO,
    ChangeEnrollmentTeeResponseDTO,
)
from src.modules.competition.application.exceptions import (
    CompetitionNotFoundError,
    EnrollmentNotApprovedError,
    EnrollmentNotFoundError,
    TeeChangeClosedError,
    TeeNotAvailableError,
    TeeNotRatedForPlayerError,
)
from src.modules.competition.application.ports.competition_timezone import ICompetitionTimezone
from src.modules.competition.application.services.barras_de_la_inscripcion import (
    SE_PUEDEN_CAMBIAR,
    BarrasDeLaInscripcion,
)
from src.modules.competition.application.services.lo_pendiente import LoPendiente
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.value_objects.enrollment_id import EnrollmentId
from src.modules.golf_course.domain.repositories.golf_course_repository import IGolfCourseRepository
from src.modules.user.domain.repositories.user_repository_interface import UserRepositoryInterface
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.services.instante_utc import ahora_en_utc
from src.shared.domain.value_objects.gender import Gender

logger = logging.getLogger(__name__)


class ChangeEnrollmentTeeUseCase:
    """
    El propio jugador (antes de empezar), el capitán de su equipo, el organizador o
    un admin cambia las barras de una inscripción, y con ellas lo que le queda por
    jugar.
    """

    def __init__(
        self,
        uow: CompetitionUnitOfWorkInterface,
        golf_course_repository: IGolfCourseRepository,
        user_repository: UserRepositoryInterface,
        zonas: ICompetitionTimezone | None = None,
        reloj: Callable[[], datetime] = ahora_en_utc,
    ):
        """
        Args:
            zonas: La zona de cada campo, para saber qué partidas ya salieron por su
                hora; sin ellas cuentan solo las que tienen golpes
            reloj: El momento del cambio
        """
        self._uow = uow
        self._campos = golf_course_repository
        self._usuarios = user_repository
        self._zonas = zonas
        self._reloj = reloj
        # Quién y qué barras: la misma regla que ofrece el selector (GET .../tees)
        self._reglas = BarrasDeLaInscripcion(uow, golf_course_repository)

    async def execute(
        self, request: ChangeEnrollmentTeeRequestDTO, quien: UserId, is_admin: bool = False
    ) -> ChangeEnrollmentTeeResponseDTO:
        """
        Cambia las barras y rehace lo que le queda por jugar.

        Args:
            request: La inscripción y sus barras nuevas (o None)
            quien: Quien lo pide
            is_admin: Si quien lo pide es administrador

        Raises:
            EnrollmentNotFoundError: Si la inscripción no existe
            CompetitionNotFoundError: Si su competición no existe
            NotCompetitionCreatorError: Si no es el jugador (antes de empezar), el
                capitán de su equipo, el organizador ni un admin
            EnrollmentNotApprovedError: Si la inscripción no está aprobada
            TeeChangeClosedError: Si la competición terminó o se canceló
            TeeNotAvailableError: Si esas barras no valen para él
            PendingGameNotRecalculableError: Si algo pendiente no se puede rehacer
                por otra cosa que sus barras
        """
        enrollment_id = EnrollmentId(request.enrollment_id)
        async with self._uow:
            # Quién, sin bloquear nada: a quien no puede no se le dice nada más
            enrollment = await self._uow.enrollments.find_by_id(enrollment_id)
            if enrollment is None:
                raise EnrollmentNotFoundError(f"Inscripción no encontrada: {enrollment_id}")
            competition = await self._uow.competitions.find_by_id(enrollment.competition_id)
            if competition is None:
                raise CompetitionNotFoundError(
                    f"Competición no encontrada: {enrollment.competition_id}"
                )
            await self._reglas.comprobar_quien(competition, enrollment, quien, is_admin)

            # Con la competición bloqueada, como la baja, la generación y la
            # reasignación; y otra vez quién, que el estado pudo cambiar
            competition = await self._uow.competitions.find_by_id_for_update(
                enrollment.competition_id
            )
            if competition is None:
                raise CompetitionNotFoundError(
                    f"Competición no encontrada: {enrollment.competition_id}"
                )
            enrollment = await self._uow.enrollments.find_by_id_for_update(enrollment_id)
            if enrollment is None:
                raise EnrollmentNotFoundError(f"Inscripción no encontrada: {enrollment_id}")
            como = await self._reglas.comprobar_quien(competition, enrollment, quien, is_admin)

            if not enrollment.is_approved():
                raise EnrollmentNotApprovedError("La inscripción no está aprobada")
            if competition.status not in SE_PUEDEN_CAMBIAR:
                raise TeeChangeClosedError(
                    f"No se cambian barras en una competición {competition.status.value}"
                )
            usuario = await self._usuarios.find_by_id(enrollment.user_id)
            genero: Gender | None = usuario.gender if usuario else None
            # Cada campo, leído una vez en toda la ejecución, y el mismo contexto para
            # comprobar y para calcular: que no diverjan
            pendiente = LoPendiente(
                self._uow, self._campos, self._usuarios, self._zonas, self._reloj
            )
            if request.tee_color is not None and not await self._reglas.la_tiene_algun_campo(
                competition, request.tee_color, genero, pendiente.contextos
            ):
                raise TeeNotAvailableError(
                    f"Ningún campo de la competición tiene barras {request.tee_color.value} "
                    "valoradas para este jugador"
                )

            # Todo calculado antes de escribir nada: en cada campo su barra efectiva
            # (su cambio propio, la del campo para su género, o esta general)
            try:
                await pendiente.rehacer(competition, enrollment.user_id, genero, request.tee_color)
            except TeeNotRatedForPlayerError as e:
                raise TeeNotAvailableError(
                    "Sus barras nuevas no están valoradas en el campo de algo que le "
                    "queda por jugar"
                ) from e

            antes = enrollment.tee_color
            enrollment.set_tee_color(request.tee_color)
            await self._uow.enrollments.update(enrollment)
            await pendiente.guardar()
        partidos, partidas = pendiente.cuantos

        # Sin nombres: quién, de qué inscripción, cómo y cuánto se rehízo (A09)
        logger.info(
            "Tee change: enrollment=%s by=%s as=%s from=%s to=%s matches=%d tee_groups=%d",
            enrollment.id.value,
            quien.value,
            como,
            antes.value if antes else None,
            request.tee_color.value if request.tee_color else None,
            partidos,
            partidas,
        )
        return ChangeEnrollmentTeeResponseDTO(
            id=enrollment.id.value,
            competition_id=enrollment.competition_id.value,
            user_id=enrollment.user_id.value,
            tee_color=enrollment.tee_color.value if enrollment.tee_color else None,
            updated_at=enrollment.updated_at,
        )
