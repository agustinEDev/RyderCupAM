"""
Caso de Uso: la barra de un campo para todos los de un género (R2, 20 nov 2026).

Decidido con Agustín (barras por campo): el organizador (o un admin) fija en un
campo de la competición la barra de todos los de un género; pisa su barra
general (R3) pero no el cambio propio de nadie (R1). Se puede también con la
competición en curso (para desbloquear una sesión que se genera ya empezada);
terminada o cancelada, no.

Solo barras que ese campo tiene para ese género o mixtas (en SCRATCH, también
con tarjeta). Se rehace lo que les queda por jugar en ese campo a todos los
inscritos de ese género sin cambio propio allí, como en la #912 (las fotos de
los demás no se tocan), y todo o nada: si a uno no se le puede rehacer, no
cambia nada de nadie.
"""

import logging
from collections.abc import Callable
from datetime import datetime

from src.modules.competition.application.dto.competition_dto import (
    CompetitionCourseTeeResponseDTO,
    SetCompetitionCourseTeeRequestDTO,
)
from src.modules.competition.application.exceptions import (
    CompetitionNotFoundError,
    CourseNotInCompetitionError,
    CourseTeeNotAvailableError,
    TeeChangeClosedError,
    TeeNotSelectableError,
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
from src.modules.competition.domain.services.barra_del_jugador import se_puede_elegir
from src.modules.competition.domain.value_objects.barras_del_campo import BarrasDelCampo
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.enrollment_status import EnrollmentStatus
from src.modules.golf_course.domain.repositories.golf_course_repository import IGolfCourseRepository
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.user.domain.repositories.user_repository_interface import UserRepositoryInterface
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.services.instante_utc import ahora_en_utc

logger = logging.getLogger(__name__)


class SetCompetitionCourseTeeUseCase:
    """El organizador o un admin fija (o quita) la barra de un campo para un género."""

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
        request: SetCompetitionCourseTeeRequestDTO,
        quien: UserId,
        is_admin: bool = False,
    ) -> CompetitionCourseTeeResponseDTO:
        """
        Fija o quita la barra y rehace lo pendiente en ese campo de los afectados.

        Raises:
            CompetitionNotFoundError: Si la competición no existe
            NotCompetitionCreatorError: Si no es el organizador ni un admin
            CourseNotInCompetitionError: Si el campo no es de la competición
            TeeChangeClosedError: Si la competición terminó o se canceló
            TeeNotSelectableError: Si son OTHER, que no se eligen aunque el campo las tenga
            TeeNotAvailableError: Si ese campo no tiene esas barras para ese género,
                o a alguno no le valen en el campo de algo pendiente
            PendingGameNotRecalculableError: Si a alguno no se le puede rehacer lo
                pendiente por otra cosa que las barras
        """
        competition_id = CompetitionId(request.competition_id)
        campo = GolfCourseId(request.golf_course_id)
        genero = request.gender
        async with self._uow:
            # Quién, sin bloquear nada
            competition = await self._uow.competitions.find_by_id(competition_id)
            if competition is None:
                raise CompetitionNotFoundError(f"Competición no encontrada: {competition_id}")
            como = self._reglas.comprobar_organizador(competition, quien, is_admin)

            competition = await self._uow.competitions.find_by_id_for_update(competition_id)
            if competition is None:
                raise CompetitionNotFoundError(f"Competición no encontrada: {competition_id}")
            if not competition.has_golf_course(campo):
                raise CourseNotInCompetitionError("Ese campo no es de la competición")
            if competition.status not in SE_PUEDEN_CAMBIAR:
                raise TeeChangeClosedError(
                    f"No se cambian barras en una competición {competition.status.value}"
                )
            if request.tee_color is not None and not se_puede_elegir(request.tee_color):
                raise TeeNotSelectableError(f"Las barras {request.tee_color.value} no se eligen")
            pendiente = LoPendiente(
                self._uow, self._campos, self._usuarios, self._zonas, self._reloj
            )
            if request.tee_color is not None and not await self._reglas.vale_en_el_campo(
                competition, campo, request.tee_color, genero, pendiente.contextos
            ):
                raise CourseTeeNotAvailableError(
                    f"Ese campo no tiene barras {request.tee_color.value} para ese género"
                )

            guardados = await pendiente.cambios_del_campo(competition, campo)
            por_genero = {g: t for g, t in guardados.por_genero.items() if g != genero}
            if request.tee_color is not None:
                por_genero[genero] = request.tee_color
            nuevos = BarrasDelCampo(propias=guardados.propias, por_genero=por_genero)

            # Los inscritos de ese género; los que tienen cambio propio allí, no
            # cambian (`color_de` ya les da el suyo, y no se rehace nada)
            inscritos = await self._uow.enrollments.find_by_competition_and_status(
                competition_id, EnrollmentStatus.APPROVED
            )
            usuarios = {
                u.id: u for u in await self._usuarios.find_by_ids([i.user_id for i in inscritos])
            }
            afectados = {
                inscripcion.user_id: (genero, inscripcion.tee_color)
                for inscripcion in inscritos
                if (usuario := usuarios.get(inscripcion.user_id)) is not None
                and usuario.gender == genero
                and inscripcion.user_id not in guardados.propias
            }
            # Todos de una vez: en un partido con varios afectados (un fourball con
            # las dos de un género) ninguno se resuelve con la barra guardada de
            # otro que también cambia. Y que nada pendiente quede sin barra válida
            await pendiente.rehacer_varios(
                competition, afectados, cambios={campo: nuevos}, solo_en=campo, cambia="del_campo"
            )

            antes = guardados.por_genero.get(genero)
            await self._uow.barras_por_campo.fijar_del_campo(
                competition_id, campo, genero, request.tee_color
            )
            await pendiente.guardar()
        partidos, partidas = pendiente.cuantos

        # Sin nombres: quién, de qué competición y campo, qué y cuánto se rehízo (A09)
        logger.info(
            "Course tee for gender: competition=%s course=%s gender=%s by=%s as=%s "
            "from=%s to=%s matches=%d tee_groups=%d",
            competition_id.value,
            campo.value,
            genero.value,
            quien.value,
            como,
            antes.value if antes else None,
            request.tee_color.value if request.tee_color else None,
            partidos,
            partidas,
        )
        return CompetitionCourseTeeResponseDTO(
            competition_id=competition_id.value,
            golf_course_id=campo.value,
            gender=genero.value,
            tee_color=request.tee_color.value if request.tee_color else None,
        )
