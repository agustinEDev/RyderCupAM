"""
Caso de Uso: lo fijado por campo en una competición (tabla del 21 nov 2026, A).

La barra que el organizador fijó en cada campo para todos los de un género (R2),
para que su pantalla la enseñe. Solo el organizador o un admin, los mismos que la
fijan (`comprobar_organizador`), comprobado antes de leer nada más; en cualquier
estado de la competición, también terminada o cancelada: es una lectura y no
bloquea nada. Los cambios propios de cada jugador (R1) no salen: no son del campo.
"""

from uuid import UUID

from src.modules.competition.application.dto.competition_dto import CourseTeeForGenderDTO
from src.modules.competition.application.exceptions import CompetitionNotFoundError
from src.modules.competition.application.services.barras_de_la_inscripcion import (
    BarrasDeLaInscripcion,
)
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.gender import Gender


class GetCompetitionCourseTeesUseCase:
    """El organizador o un admin consulta la barra fijada en cada campo para cada género."""

    def __init__(self, uow: CompetitionUnitOfWorkInterface):
        self._uow = uow

    async def execute(
        self, competition_id: UUID, quien: UserId, is_admin: bool = False
    ) -> list[CourseTeeForGenderDTO]:
        """
        Lo fijado, en el orden de los campos de la competición y por género.

        Raises:
            CompetitionNotFoundError: Si la competición no existe
            NotCompetitionCreatorError: Si no es el organizador ni un admin
        """
        async with self._uow:
            competition = await self._uow.competitions.find_by_id(CompetitionId(competition_id))
            if competition is None:
                raise CompetitionNotFoundError(f"Competición no encontrada: {competition_id}")
            BarrasDeLaInscripcion.comprobar_organizador(competition, quien, is_admin)
            fijadas: list[CourseTeeForGenderDTO] = []
            for del_campo in competition.golf_courses:
                cambios = await self._uow.barras_por_campo.del_campo(
                    competition.id, del_campo.golf_course_id
                )
                fijadas.extend(
                    CourseTeeForGenderDTO(
                        golf_course_id=del_campo.golf_course_id.value,
                        gender=genero.value,
                        tee_color=cambios.por_genero[genero].value,
                    )
                    for genero in Gender
                    if genero in cambios.por_genero
                )
        return fijadas
