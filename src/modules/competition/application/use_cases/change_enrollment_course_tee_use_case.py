"""
Caso de Uso: el cambio propio de barras de una inscripción en un campo (R1, 20 nov 2026).

Decidido con Agustín (barras por campo): en cada campo de la competición, el
cambio propio de un jugador gana a la barra del campo para su género (R2) y a su
barra general (R3). Lo fijan los mismos y en los mismos plazos que la barra
general (#912): antes de empezar, el propio jugador, el capitán de su equipo, el
organizador o un admin; en curso, sin el jugador; terminada o cancelada, nadie.

Solo barras que ESE campo tiene para su género o mixtas (en SCRATCH, también con
tarjeta). Con el cambio se rehace lo que le queda por jugar en ese campo, como en
la #912: las fotos de los demás no se tocan. Sin barras (null) se quita el cambio
y vuelve a contar lo demás.
"""

import logging
from collections.abc import Callable
from datetime import datetime

from src.modules.competition.application.dto.enrollment_dto import (
    ChangeEnrollmentCourseTeeRequestDTO,
    EnrollmentCourseTeeResponseDTO,
)
from src.modules.competition.application.exceptions import (
    CompetitionNotFoundError,
    CourseNotInCompetitionError,
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
from src.modules.competition.domain.value_objects.barras_del_campo import BarrasDelCampo
from src.modules.competition.domain.value_objects.enrollment_id import EnrollmentId
from src.modules.golf_course.domain.repositories.golf_course_repository import IGolfCourseRepository
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.user.domain.repositories.user_repository_interface import UserRepositoryInterface
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.services.instante_utc import ahora_en_utc
from src.shared.domain.value_objects.gender import Gender

logger = logging.getLogger(__name__)


class ChangeEnrollmentCourseTeeUseCase:
    """
    El propio jugador (antes de empezar), el capitán de su equipo, el organizador o
    un admin fija (o quita) el cambio de barras de una inscripción en un campo.
    """

    def __init__(
        self,
        uow: CompetitionUnitOfWorkInterface,
        golf_course_repository: IGolfCourseRepository,
        user_repository: UserRepositoryInterface,
        zonas: ICompetitionTimezone | None = None,
        reloj: Callable[[], datetime] = ahora_en_utc,
    ):
        self._uow = uow
        self._campos = golf_course_repository
        self._usuarios = user_repository
        self._zonas = zonas
        self._reloj = reloj
        self._reglas = BarrasDeLaInscripcion(uow, golf_course_repository)

    async def execute(
        self,
        request: ChangeEnrollmentCourseTeeRequestDTO,
        quien: UserId,
        is_admin: bool = False,
    ) -> EnrollmentCourseTeeResponseDTO:
        """
        Fija o quita el cambio y rehace lo que le queda por jugar en ese campo.

        Raises:
            EnrollmentNotFoundError: Si la inscripción no existe
            CompetitionNotFoundError: Si su competición no existe
            NotCompetitionCreatorError: Si no puede cambiar sus barras ahora
            CourseNotInCompetitionError: Si el campo no es de la competición
            EnrollmentNotApprovedError: Si la inscripción no está aprobada
            TeeChangeClosedError: Si la competición terminó o se canceló
            TeeNotAvailableError: Si ese campo no tiene esas barras para él, o no
                están valoradas en el campo de algo que le queda por jugar
            PendingGameNotRecalculableError: Si algo pendiente no se puede rehacer
                por otra cosa que sus barras
        """
        enrollment_id = EnrollmentId(request.enrollment_id)
        campo = GolfCourseId(request.golf_course_id)
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

            # Con la competición bloqueada, y otra vez quién: el estado pudo cambiar
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

            if not competition.has_golf_course(campo):
                raise CourseNotInCompetitionError("Ese campo no es de la competición")
            if not enrollment.is_approved():
                raise EnrollmentNotApprovedError("La inscripción no está aprobada")
            if competition.status not in SE_PUEDEN_CAMBIAR:
                raise TeeChangeClosedError(
                    f"No se cambian barras en una competición {competition.status.value}"
                )
            usuario = await self._usuarios.find_by_id(enrollment.user_id)
            genero: Gender | None = usuario.gender if usuario else None
            pendiente = LoPendiente(
                self._uow, self._campos, self._usuarios, self._zonas, self._reloj
            )
            if request.tee_color is not None and not await self._reglas.vale_en_el_campo(
                competition, campo, request.tee_color, genero, pendiente.contextos
            ):
                raise TeeNotAvailableError(
                    f"Ese campo no tiene barras {request.tee_color.value} para este jugador"
                )

            # Los cambios de ese campo con el suyo nuevo, y con ellos lo pendiente allí
            guardados = await pendiente.cambios_del_campo(competition, campo)
            propias = {u: t for u, t in guardados.propias.items() if u != enrollment.user_id}
            if request.tee_color is not None:
                propias[enrollment.user_id] = request.tee_color
            nuevos = BarrasDelCampo(propias=propias, por_genero=guardados.por_genero)
            try:
                await pendiente.rehacer(
                    competition,
                    enrollment.user_id,
                    genero,
                    enrollment.tee_color,
                    cambios={campo: nuevos},
                    solo_en=campo,
                )
            except TeeNotRatedForPlayerError as e:
                # Al quitarlo (null) puede fallar su general: lo dice la comprobación
                await pendiente.comprobar_que_vale(
                    competition,
                    enrollment.user_id,
                    genero,
                    enrollment.tee_color,
                    cambios={campo: nuevos},
                    solo_en=campo,
                )
                raise TeeNotAvailableError(
                    "Esas barras no están valoradas en el campo de algo que le queda por jugar"
                ) from e
            # En SCRATCH `rehacer` no valora: al quitarlo, la que pasaría a jugar
            # allí (la del campo, su general o la habitual) tiene que valer
            await pendiente.comprobar_que_vale(
                competition,
                enrollment.user_id,
                genero,
                enrollment.tee_color,
                cambios={campo: nuevos},
                solo_en=campo,
            )

            antes = guardados.propias.get(enrollment.user_id)
            await self._uow.barras_por_campo.fijar_propia(enrollment, campo, request.tee_color)
            await pendiente.guardar()
        partidos, partidas = pendiente.cuantos

        # Sin nombres: quién, de qué inscripción y campo, cómo y cuánto se rehízo (A09)
        logger.info(
            "Course tee change: enrollment=%s course=%s by=%s as=%s from=%s to=%s "
            "matches=%d tee_groups=%d",
            enrollment.id.value,
            campo.value,
            quien.value,
            como,
            antes.value if antes else None,
            request.tee_color.value if request.tee_color else None,
            partidos,
            partidas,
        )
        return EnrollmentCourseTeeResponseDTO(
            enrollment_id=enrollment.id.value,
            golf_course_id=campo.value,
            tee_color=request.tee_color.value if request.tee_color else None,
        )
