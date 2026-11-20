"""
Caso de Uso: las barras que se pueden elegir para una inscripción (BE #912, 20 nov 2026).

El front no conoce el género de los demás inscritos, así que al organizador o al
capitán el selector de «Cambiar barra» solo podía ofrecer mixtas. Decidido con
Agustín: las calcula el back, con la MISMA regla que el cambio
(`BarrasDeLaInscripcion`), para que el selector no ofrezca nada que el cambio
rechace ni esconda nada que acepte.

Quién: los mismos que pueden cambiarlas en ese momento, comprobado antes de mirar
el estado. Es una lectura: no bloquea nada. El género del jugador no sale.
"""

from uuid import UUID

from src.modules.competition.application.dto.enrollment_dto import EnrollmentTeesResponseDTO
from src.modules.competition.application.exceptions import (
    CompetitionNotFoundError,
    EnrollmentNotFoundError,
)
from src.modules.competition.application.services.barras_de_la_inscripcion import (
    SE_PUEDEN_CAMBIAR,
    BarrasDeLaInscripcion,
)
from src.modules.competition.application.use_cases.change_enrollment_tee_use_case import (
    EnrollmentNotApprovedError,
    TeeChangeClosedError,
)
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.services.barra_del_jugador import barras_por_defecto
from src.modules.competition.domain.value_objects.enrollment_id import EnrollmentId
from src.modules.golf_course.domain.repositories.golf_course_repository import IGolfCourseRepository
from src.modules.user.domain.repositories.user_repository_interface import UserRepositoryInterface
from src.modules.user.domain.value_objects.user_id import UserId


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
        self._usuarios = user_repository
        self._reglas = BarrasDeLaInscripcion(uow, golf_course_repository)

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
            valen = await self._reglas.las_que_valen(competition, genero, {})

        return EnrollmentTeesResponseDTO(
            tees=[color.value for color in valen],
            # Sin usuario no se sabe cuál tendría
            default_tee=barras_por_defecto(genero).value if usuario else None,
            current_tee=enrollment.tee_color.value if enrollment.tee_color else None,
        )
