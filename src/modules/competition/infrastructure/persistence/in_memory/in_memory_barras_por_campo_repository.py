"""Los cambios de barras por campo, en memoria (tests)."""

from src.modules.competition.domain.entities.enrollment import Enrollment
from src.modules.competition.domain.repositories.barras_por_campo_repository_interface import (
    BarrasPorCampoRepositoryInterface,
)
from src.modules.competition.domain.value_objects.barras_del_campo import BarrasDelCampo
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.golf_course.domain.value_objects.tee_color import TeeColor
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.gender import Gender


class InMemoryBarrasPorCampoRepository(BarrasPorCampoRepositoryInterface):
    """Las propias guardan su competición y su jugador, que en SQL salen de la inscripción."""

    def __init__(self) -> None:
        self._propias: dict[tuple[CompetitionId, GolfCourseId, UserId], TeeColor] = {}
        self._del_campo: dict[tuple[CompetitionId, GolfCourseId, Gender], TeeColor] = {}

    async def del_campo(
        self, competition_id: CompetitionId, golf_course_id: GolfCourseId
    ) -> BarrasDelCampo:
        return BarrasDelCampo(
            propias={
                u: t
                for (c, g, u), t in self._propias.items()
                if (c, g) == (competition_id, golf_course_id)
            },
            por_genero={
                s: t
                for (c, g, s), t in self._del_campo.items()
                if (c, g) == (competition_id, golf_course_id)
            },
        )

    async def fijar_propia(
        self, enrollment: Enrollment, golf_course_id: GolfCourseId, tee_color: TeeColor | None
    ) -> None:
        clave = (enrollment.competition_id, golf_course_id, enrollment.user_id)
        if tee_color is None:
            self._propias.pop(clave, None)
        else:
            self._propias[clave] = tee_color

    async def fijar_del_campo(
        self,
        competition_id: CompetitionId,
        golf_course_id: GolfCourseId,
        genero: Gender,
        tee_color: TeeColor | None,
    ) -> None:
        clave = (competition_id, golf_course_id, genero)
        if tee_color is None:
            self._del_campo.pop(clave, None)
        else:
            self._del_campo[clave] = tee_color

    async def borrar_del_campo(
        self, competition_id: CompetitionId, golf_course_id: GolfCourseId
    ) -> None:
        self._propias = {
            k: v
            for k, v in self._propias.items()
            if (k[0], k[1]) != (competition_id, golf_course_id)
        }
        self._del_campo = {
            k: v
            for k, v in self._del_campo.items()
            if (k[0], k[1]) != (competition_id, golf_course_id)
        }
