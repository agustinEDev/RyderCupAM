"""Los cambios de barras por campo de una competición (barras por campo, 20 nov 2026)."""

from abc import ABC, abstractmethod

from src.modules.competition.domain.entities.enrollment import Enrollment
from src.modules.competition.domain.value_objects.barras_del_campo import BarrasDelCampo
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.golf_course.domain.value_objects.tee_color import TeeColor
from src.shared.domain.value_objects.gender import Gender


class BarrasPorCampoRepositoryInterface(ABC):
    """
    Dos clases de cambio, únicos por su clave:

    - el propio de una inscripción en un campo (R1): (inscripción, campo) → barra;
    - el del campo para todos los de un género (R2): (competición, campo, género) → barra.
    """

    @abstractmethod
    async def del_campo(
        self, competition_id: CompetitionId, golf_course_id: GolfCourseId
    ) -> BarrasDelCampo:
        """Los cambios de ese campo de la competición (vacíos si no hay ninguno)."""

    @abstractmethod
    async def fijar_propia(
        self, enrollment: Enrollment, golf_course_id: GolfCourseId, tee_color: TeeColor | None
    ) -> None:
        """Fija (o quita, con None) el cambio propio de una inscripción en un campo."""

    @abstractmethod
    async def fijar_del_campo(
        self,
        competition_id: CompetitionId,
        golf_course_id: GolfCourseId,
        genero: Gender,
        tee_color: TeeColor | None,
    ) -> None:
        """Fija (o quita, con None) la barra del campo para todos los de un género."""

    @abstractmethod
    async def borrar_del_campo(
        self, competition_id: CompetitionId, golf_course_id: GolfCourseId
    ) -> None:
        """Borra todos los cambios de ese campo: se quita de la competición."""
