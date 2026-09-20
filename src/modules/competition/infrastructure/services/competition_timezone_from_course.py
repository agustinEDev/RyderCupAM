"""
Adaptador: la zona horaria de una competicion sale de su primer campo (BE #319).

La hora de apertura que escribe el organizador es local del campo donde se
juega. El campo ya trae su zona resuelta desde sus coordenadas (BE #305), asi
que aqui solo hay que ir a buscarla.

«El primero» es el de menor `display_order`, que es el orden en que se juegan.
"""

import logging

from src.modules.competition.application.ports.competition_timezone import (
    ICompetitionTimezone,
)
from src.modules.competition.domain.entities.competition import Competition
from src.modules.golf_course.domain.repositories.golf_course_repository import (
    IGolfCourseRepository,
)

logger = logging.getLogger(__name__)


class CompetitionTimezoneFromCourse(ICompetitionTimezone):
    """Resuelve la zona de una competicion mirando el campo que se juega."""

    def __init__(self, golf_course_repository: IGolfCourseRepository):
        self._golf_courses = golf_course_repository

    async def for_competition(self, competition: Competition) -> str | None:
        """La zona del primer campo, o `None` si todavia no hay campo."""
        campos = competition.golf_courses
        if not campos:
            # Se puede crear una competicion, invitar y anadir el campo despues
            # (BE #323): hasta que lo haya, la apertura programada espera
            return None

        primero = min(campos, key=lambda cgc: cgc.display_order)
        campo = await self._golf_courses.find_by_id(primero.golf_course_id)
        if campo is None:
            logger.warning(
                "La competicion %s apunta a un campo que no existe: %s",
                competition.id.value,
                primero.golf_course_id.value,
            )
            return None

        return campo.timezone
