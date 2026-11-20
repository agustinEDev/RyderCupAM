"""
Caso de Uso: las barras de una inscripción, campo a campo (barras por campo, 20 nov 2026).

El front no conoce el género de los demás inscritos, así que al organizador o al
capitán el selector no podía saber qué ofrecer. Decidido con Agustín: lo calcula
el back, con la MISMA regla que los cambios (`BarrasDeLaInscripcion`). Por cada
campo de la competición: la barra que juega (su cambio propio, la del campo para
su género o su general, si ese campo la tiene para él; si no, ninguna), de dónde
sale y las que se le pueden fijar. Además, su barra general y la habitual de su
género.

Quién: los mismos que pueden cambiarlas en ese momento, comprobado antes de mirar
el estado. Es una lectura: no bloquea nada. No devuelve el género del jugador,
pero las opciones (barras de un género o mixtas) lo dejan ver a quien puede
cambiar sus barras: por eso solo las ven ellos.
"""

from typing import Literal
from uuid import UUID

from src.modules.competition.application.dto.enrollment_dto import (
    CourseTeesDTO,
    EnrollmentTeesResponseDTO,
)
from src.modules.competition.application.exceptions import (
    CompetitionNotFoundError,
    EnrollmentNotApprovedError,
    EnrollmentNotFoundError,
    TeeChangeClosedError,
)
from src.modules.competition.application.services.barras_de_la_inscripcion import (
    SE_PUEDEN_CAMBIAR,
    BarrasDeLaInscripcion,
)
from src.modules.competition.application.services.course_context import course_context_for
from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.services.barra_del_jugador import barras_por_defecto
from src.modules.competition.domain.value_objects.enrollment_id import EnrollmentId
from src.modules.golf_course.domain.repositories.golf_course_repository import IGolfCourseRepository
from src.modules.golf_course.domain.services.stroke_context import StrokeContext
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.golf_course.domain.value_objects.tee_color import TeeColor
from src.modules.user.domain.repositories.user_repository_interface import UserRepositoryInterface
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.gender import Gender


class GetEnrollmentTeesUseCase:
    """
    Las barras que el propio jugador (antes de empezar), el capitán de su equipo, el
    organizador o un admin pueden elegir para una inscripción.
    """

    def __init__(
        self,
        uow: CompetitionUnitOfWorkInterface,
        golf_course_repository: IGolfCourseRepository,
        user_repository: UserRepositoryInterface,
    ):
        self._uow = uow
        self._campos = golf_course_repository
        self._usuarios = user_repository
        self._reglas = BarrasDeLaInscripcion(uow, golf_course_repository)
        self._contextos: dict[GolfCourseId, StrokeContext] = {}

    async def execute(
        self, enrollment_id: UUID, quien: UserId, is_admin: bool = False
    ) -> EnrollmentTeesResponseDTO:
        """
        Las barras que valen, las de por defecto y las elegidas.

        Raises:
            EnrollmentNotFoundError: Si la inscripción no existe
            CompetitionNotFoundError: Si su competición no existe
            NotCompetitionCreatorError: Si no puede cambiarlas ahora
            EnrollmentNotApprovedError: Si la inscripción no está aprobada
            TeeChangeClosedError: Si la competición terminó o se canceló
        """
        async with self._uow:
            enrollment = await self._uow.enrollments.find_by_id(EnrollmentId(enrollment_id))
            if enrollment is None:
                raise EnrollmentNotFoundError(f"Inscripción no encontrada: {enrollment_id}")
            competition = await self._uow.competitions.find_by_id(enrollment.competition_id)
            if competition is None:
                raise CompetitionNotFoundError(
                    f"Competición no encontrada: {enrollment.competition_id}"
                )
            # Primero quién: a quien no puede no se le dice nada más
            await self._reglas.comprobar_quien(competition, enrollment, quien, is_admin)
            if not enrollment.is_approved():
                raise EnrollmentNotApprovedError("La inscripción no está aprobada")
            if competition.status not in SE_PUEDEN_CAMBIAR:
                raise TeeChangeClosedError(
                    f"No se cambian barras en una competición {competition.status.value}"
                )

            usuario = await self._usuarios.find_by_id(enrollment.user_id)
            genero = usuario.gender if usuario else None
            campos = [
                await self._campo(
                    competition,
                    del_campo.golf_course_id,
                    enrollment.user_id,
                    enrollment.tee_color,
                    genero,
                )
                for del_campo in competition.golf_courses
            ]

        return EnrollmentTeesResponseDTO(
            general_tee=enrollment.tee_color.value if enrollment.tee_color else None,
            # Sin usuario no se sabe cuál tendría
            default_tee=barras_por_defecto(genero).value if usuario else None,
            courses=campos,
        )

    async def _campo(
        self,
        competition: Competition,
        golf_course_id: GolfCourseId,
        user_id: UserId,
        general: TeeColor | None,
        genero: Gender | None,
    ) -> CourseTeesDTO:
        """
        Lo de un campo: la barra que juega (su cambio propio, la del campo para su
        género o su general, si ese campo la tiene para él), de dónde sale y las
        que se le pueden fijar. Un campo que ya no existe sale sin opciones.
        """
        campo = await self._campos.find_by_id(golf_course_id)
        if campo is not None and golf_course_id not in self._contextos:
            self._contextos[golf_course_id] = course_context_for(campo)
        cambios = await self._uow.barras_por_campo.del_campo(competition.id, golf_course_id)
        color = cambios.color_de(user_id, general, genero)
        source: Literal["OWN", "COURSE", "GENERAL", "NONE"]
        if user_id in cambios.propias:
            source = "OWN"
        elif genero is not None and genero in cambios.por_genero:
            source = "COURSE"
        else:
            source = "GENERAL"
        # La habitual de su género si no tiene ninguna: la que jugaría
        jugaria = color or barras_por_defecto(genero)
        valida = await self._reglas.vale_en_el_campo(
            competition, golf_course_id, jugaria, genero, self._contextos
        )
        opciones = await self._reglas.las_que_valen_en_el_campo(
            competition, golf_course_id, genero, self._contextos
        )
        return CourseTeesDTO(
            golf_course_id=golf_course_id.value,
            golf_course_name=campo.name if campo is not None else "",
            tee=jugaria.value if valida else None,
            source=source if valida else "NONE",
            options=[c.value for c in opciones],
        )
